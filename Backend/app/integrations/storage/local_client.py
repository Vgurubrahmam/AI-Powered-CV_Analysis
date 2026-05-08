"""Local filesystem storage client — drop-in replacement for S3Client in dev.

Files are stored under a configurable root directory with the same key
structure used by S3 (e.g.  resumes/{user_id}/{uuid}_{filename}).

Presigned URLs are replaced by file:// URIs (sufficient for local testing).
"""

from __future__ import annotations

import io
import mimetypes
import shutil
from dataclasses import dataclass, field
from pathlib import Path

import structlog

log = structlog.get_logger(__name__)


# Re-use the same UploadResult type for interface compatibility
from app.integrations.storage.s3_client import UploadResult


class LocalStorageClient:
    """Filesystem-based storage that mirrors the S3Client async interface.

    Args:
        root_dir: Absolute path to the local storage root.
                  Defaults to ``<project>/storage`` next to the Backend folder.
    """

    def __init__(self, root_dir: str | Path | None = None) -> None:
        if root_dir is None:
            # Default: <Backend>/storage
            root_dir = Path(__file__).resolve().parents[3] / "storage"
        self._root = Path(root_dir)
        self._root.mkdir(parents=True, exist_ok=True)
        log.info("local_storage_initialized", root=str(self._root))

    # ── Upload ────────────────────────────────────────────────────────────

    async def upload(
        self,
        key: str,
        data: bytes | io.BytesIO,
        content_type: str | None = None,
        metadata: dict[str, str] | None = None,
        tags: dict[str, str] | None = None,
    ) -> UploadResult:
        """Write bytes to the local filesystem under ``root_dir/key``."""
        # Normalise to raw bytes
        if isinstance(data, io.BytesIO):
            raw_bytes = data.getvalue()
        else:
            raw_bytes = data

        if content_type is None:
            content_type = mimetypes.guess_type(key)[0] or "application/octet-stream"

        dest = self._root / key
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(raw_bytes)

        url = dest.as_uri()               # file:///...
        log.info("local_upload_complete", key=key, size=len(raw_bytes))
        return UploadResult(
            storage_key=key,
            bucket="local",
            url=url,
            size_bytes=len(raw_bytes),
            content_type=content_type,
        )

    # ── Download ──────────────────────────────────────────────────────────

    async def download(self, key: str) -> bytes:
        """Read file bytes from local storage."""
        path = self._root / key
        if not path.exists():
            raise RuntimeError(f"Local file not found: {key}")
        data = path.read_bytes()
        log.debug("local_download_complete", key=key, size=len(data))
        return data

    # ── Presigned URL ─────────────────────────────────────────────────────

    async def generate_presigned_url(
        self,
        key: str,
        expires_in: int = 3600,
        method: str = "get_object",
    ) -> str:
        """Return a file:// URI — sufficient for local dev testing."""
        path = self._root / key
        if not path.exists():
            raise RuntimeError(f"Local file not found: {key}")
        return path.as_uri()

    # ── Delete ────────────────────────────────────────────────────────────

    async def delete(self, key: str) -> None:
        """Delete a file from local storage."""
        path = self._root / key
        if path.exists():
            path.unlink()
            log.info("local_file_deleted", key=key)
        else:
            log.warning("local_delete_skipped_not_found", key=key)

    # ── Tag / Exists ──────────────────────────────────────────────────────

    async def tag_object(self, key: str, tags: dict[str, str]) -> None:
        """No-op for local storage — tags are an S3 concept."""
        log.debug("local_tag_noop", key=key, tags=tags)

    async def object_exists(self, key: str) -> bool:
        """Check if a file exists on local disk."""
        return (self._root / key).exists()
