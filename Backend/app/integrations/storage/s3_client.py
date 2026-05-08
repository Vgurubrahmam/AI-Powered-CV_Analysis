"""S3 / MinIO client — async wrapper around boto3 for object storage.

Supports both AWS S3 and MinIO (via custom endpoint_url).
All operations are run in a thread executor to avoid blocking the event loop,
since boto3 is synchronous.

Features:
  - Upload bytes with content-type detection
  - Presigned download URL generation
  - Object deletion
  - Lifecycle tagging (e.g. marking files for expiry)
  - Async download of file bytes
"""

from __future__ import annotations

import asyncio
import io
import mimetypes
import os
from dataclasses import dataclass
from functools import cached_property
from typing import Any, Optional

import structlog

log = structlog.get_logger(__name__)


@dataclass
class UploadResult:
    """Result of an S3 upload operation."""
    storage_key: str
    bucket: str
    url: str
    size_bytes: int
    content_type: str


class S3Client:
    """Async S3/MinIO client backed by boto3 in thread executor.

    Args:
        bucket: S3 bucket name.
        region: AWS region.
        access_key: Access key ID.
        secret_key: Secret access key.
        endpoint_url: Custom endpoint for MinIO/LocalStack. None for real AWS.
        use_ssl: Whether to use HTTPS for the custom endpoint.
    """

    def __init__(
        self,
        bucket: str,
        region: str,
        access_key: str,
        secret_key: str,
        endpoint_url: str | None = None,
        use_ssl: bool = False,
    ) -> None:
        self._bucket = bucket
        self._region = region
        self._access_key = access_key
        self._secret_key = secret_key
        self._endpoint_url = endpoint_url or None
        self._use_ssl = use_ssl
        self._client = None

    def _get_boto_client(self):
        """Lazily initialize the boto3 S3 client."""
        if self._client is None:
            import boto3
            from botocore.config import Config

            kwargs: dict[str, Any] = {
                "region_name": self._region,
                "aws_access_key_id": self._access_key,
                "aws_secret_access_key": self._secret_key,
                "config": Config(
                    retries={"max_attempts": 3, "mode": "adaptive"},
                    max_pool_connections=10,
                ),
            }
            if self._endpoint_url:
                kwargs["endpoint_url"] = self._endpoint_url
                kwargs["use_ssl"] = self._use_ssl

            self._client = boto3.client("s3", **kwargs)
        return self._client

    async def upload(
        self,
        key: str,
        data: bytes | io.BytesIO,
        content_type: str | None = None,
        metadata: dict[str, str] | None = None,
        tags: dict[str, str] | None = None,
    ) -> UploadResult:
        """Upload bytes to S3.

        Args:
            key: Object key (path in bucket).
            data: File bytes or BytesIO stream.
            content_type: MIME type. Auto-detected from key extension if None.
            metadata: Optional user-defined metadata (x-amz-meta-* headers).
            tags: Optional object tags (key-value pairs).

        Returns:
            UploadResult with storage_key, bucket, url.
        """
        # Normalise to raw bytes so len() and BytesIO wrapping always work
        if isinstance(data, io.BytesIO):
            raw_bytes = data.getvalue()
        else:
            raw_bytes = data

        if content_type is None:
            content_type = mimetypes.guess_type(key)[0] or "application/octet-stream"

        extra_args: dict[str, Any] = {"ContentType": content_type}
        if metadata:
            extra_args["Metadata"] = metadata
        if tags:
            tag_str = "&".join(f"{k}={v}" for k, v in tags.items())
            extra_args["Tagging"] = tag_str

        def _upload():
            s3 = self._get_boto_client()
            s3.upload_fileobj(
                io.BytesIO(raw_bytes),
                self._bucket,
                key,
                ExtraArgs=extra_args,
            )

        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, _upload)

        # Build URL
        if self._endpoint_url:
            url = f"{self._endpoint_url}/{self._bucket}/{key}"
        else:
            url = f"https://{self._bucket}.s3.{self._region}.amazonaws.com/{key}"

        log.info("s3_upload_complete", key=key, bucket=self._bucket, size=len(raw_bytes))
        return UploadResult(
            storage_key=key,
            bucket=self._bucket,
            url=url,
            size_bytes=len(raw_bytes),
            content_type=content_type,
        )

    async def download(self, key: str) -> bytes:
        """Download an object from S3 and return bytes.

        Args:
            key: Object key.

        Returns:
            Raw bytes of the object.

        Raises:
            RuntimeError: If the object does not exist or download fails.
        """
        def _download() -> bytes:
            s3 = self._get_boto_client()
            buf = io.BytesIO()
            s3.download_fileobj(self._bucket, key, buf)
            return buf.getvalue()

        loop = asyncio.get_event_loop()
        try:
            data = await loop.run_in_executor(None, _download)
            log.debug("s3_download_complete", key=key, size=len(data))
            return data
        except Exception as exc:
            raise RuntimeError(f"S3 download failed for key '{key}': {exc}") from exc

    async def generate_presigned_url(
        self,
        key: str,
        expires_in: int = 3600,
        method: str = "get_object",
    ) -> str:
        """Generate a presigned URL for temporary access.

        Args:
            key: Object key.
            expires_in: URL expiry in seconds (default 1 hour).
            method: S3 operation ('get_object' or 'put_object').

        Returns:
            Presigned URL string.
        """
        def _generate() -> str:
            s3 = self._get_boto_client()
            return s3.generate_presigned_url(
                ClientMethod=method,
                Params={"Bucket": self._bucket, "Key": key},
                ExpiresIn=expires_in,
            )

        loop = asyncio.get_event_loop()
        url = await loop.run_in_executor(None, _generate)
        log.debug("presigned_url_generated", key=key, expires_in=expires_in)
        return url

    async def delete(self, key: str) -> None:
        """Delete an object from S3.

        Args:
            key: Object key to delete.
        """
        def _delete():
            s3 = self._get_boto_client()
            s3.delete_object(Bucket=self._bucket, Key=key)

        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, _delete)
        log.info("s3_object_deleted", key=key, bucket=self._bucket)

    async def tag_object(self, key: str, tags: dict[str, str]) -> None:
        """Apply lifecycle tags to an existing object.

        Used for marking objects for expiry or retention policies.

        Args:
            key: Object key.
            tags: Tag key-value dict (e.g. {"expiry": "90days"}).
        """
        tag_set = [{"Key": k, "Value": v} for k, v in tags.items()]

        def _tag():
            s3 = self._get_boto_client()
            s3.put_object_tagging(
                Bucket=self._bucket,
                Key=key,
                Tagging={"TagSet": tag_set},
            )

        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, _tag)
        log.debug("s3_object_tagged", key=key, tags=tags)

    async def object_exists(self, key: str) -> bool:
        """Check if an object exists without downloading it."""
        def _exists() -> bool:
            try:
                s3 = self._get_boto_client()
                s3.head_object(Bucket=self._bucket, Key=key)
                return True
            except Exception:
                return False

        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, _exists)


# ─── Factory ──────────────────────────────────────────────────────────────────

def get_s3_client() -> S3Client:
    """Return an S3Client configured from application settings."""
    from app.config import settings
    return S3Client(
        bucket=settings.S3_BUCKET_NAME,
        region=settings.AWS_REGION,
        access_key=settings.effective_s3_access_key,
        secret_key=settings.effective_s3_secret_key,
        endpoint_url=settings.S3_ENDPOINT_URL or None,
        use_ssl=settings.S3_USE_SSL,
    )
