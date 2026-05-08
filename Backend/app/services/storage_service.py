"""Storage service — abstraction over local/MinIO/S3 for file upload/download/delete.

The backend is selected by the STORAGE_BACKEND config var:
  - "local"     → filesystem under Backend/storage/  (default for development)
  - "s3"/"minio → S3Client backed by boto3 (staging/production)
"""

from __future__ import annotations

import io
import uuid
from pathlib import Path

import structlog

from app.config import settings
from app.core.exceptions import StorageException

log = structlog.get_logger(__name__)

# Both clients expose the same async interface
_client = None


def get_storage_client():
    """Return a storage client based on STORAGE_BACKEND setting.

    Returns either a LocalStorageClient or S3Client — both share the same
    async method signatures (upload, download, delete, etc.)
    """
    global _client
    if _client is not None:
        return _client

    backend = settings.STORAGE_BACKEND.lower()

    if backend == "local":
        from app.integrations.storage.local_client import LocalStorageClient
        root = settings.LOCAL_STORAGE_ROOT or None
        _client = LocalStorageClient(root_dir=root)
        log.info("storage_backend_selected", backend="local")
    elif backend in ("s3", "minio"):
        from app.integrations.storage.s3_client import S3Client
        _client = S3Client(
            endpoint_url=settings.S3_ENDPOINT_URL or None,
            bucket=settings.S3_BUCKET_NAME,
            access_key=settings.effective_s3_access_key,
            secret_key=settings.effective_s3_secret_key,
            region=settings.AWS_REGION,
            use_ssl=settings.S3_USE_SSL,
        )
        log.info("storage_backend_selected", backend=backend)
    else:
        raise ValueError(
            f"Unknown STORAGE_BACKEND '{backend}'. "
            f"Expected one of: local, s3, minio"
        )

    return _client


class StorageService:
    """Abstract file storage operations. Callers never reference S3/MinIO directly."""

    def __init__(self) -> None:
        self.client = get_storage_client()

    def _make_key(self, user_id: uuid.UUID, filename: str) -> str:
        """Generate object key: resumes/{user_id}/{uuid}_{filename}"""
        safe_name = Path(filename).name.replace(" ", "_")
        return f"resumes/{user_id}/{uuid.uuid4()}_{safe_name}"

    async def upload_resume(
        self,
        user_id: uuid.UUID,
        file_bytes: bytes,
        filename: str,
        content_type: str,
    ) -> str:
        """Upload resume file to storage. Returns the object key."""
        key = self._make_key(user_id, filename)
        try:
            await self.client.upload(
                key=key,
                data=io.BytesIO(file_bytes),
                content_type=content_type,
                metadata={"user_id": str(user_id), "original_name": filename},
            )
            log.info("resume_uploaded", key=key, size=len(file_bytes))
            return key
        except Exception as exc:
            log.error("resume_upload_failed", filename=filename, error=str(exc))
            raise StorageException(f"Failed to upload file: {exc}") from exc

    async def download_resume(self, key: str) -> bytes:
        """Download a resume file from storage. Returns raw bytes."""
        try:
            return await self.client.download(key)
        except Exception as exc:
            raise StorageException(f"Failed to download file '{key}': {exc}") from exc

    async def get_presigned_url(self, key: str, expires_in: int = 900) -> str:
        """Return a presigned URL valid for `expires_in` seconds (default 15 min)."""
        try:
            return await self.client.generate_presigned_url(key, expires_in=expires_in)
        except Exception as exc:
            raise StorageException(f"Failed to generate presigned URL: {exc}") from exc

    async def delete_resume(self, key: str) -> None:
        """Delete a resume file from storage."""
        try:
            await self.client.delete(key)
            log.info("resume_deleted", key=key)
        except Exception as exc:
            log.warning("resume_delete_failed", key=key, error=str(exc))
