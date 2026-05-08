"""File utilities — MIME type detection, size validation, extension checking."""

from __future__ import annotations

import mimetypes
from pathlib import Path

# Attempt to use python-magic for reliable MIME detection (magic bytes)
try:
    import magic as _magic

    def detect_mime_type(data: bytes) -> str:
        """Detect MIME type from file bytes (magic bytes — not file extension)."""
        return _magic.from_buffer(data, mime=True)

except (ImportError, Exception):
    # Fallback: best-effort detection using struct analysis
    def detect_mime_type(data: bytes) -> str:  # type: ignore[misc]
        """Fallback MIME detection by magic bytes inspection."""
        # PDF: %PDF
        if data[:4] == b"%PDF":
            return "application/pdf"
        # DOCX (ZIP-based): PK\x03\x04
        if data[:2] == b"PK":
            return "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        # Attempt UTF-8 decode → plain text
        try:
            data[:1024].decode("utf-8")
            return "text/plain"
        except UnicodeDecodeError:
            return "application/octet-stream"


def get_file_extension(filename: str) -> str:
    """Return the file extension in lowercase without the leading dot."""
    return Path(filename).suffix.lstrip(".").lower()


def is_allowed_extension(filename: str, allowed: set[str] | None = None) -> bool:
    """Check if the file has an allowed extension."""
    if allowed is None:
        allowed = {"pdf", "docx", "txt"}
    return get_file_extension(filename) in allowed


def human_readable_size(size_bytes: int) -> str:
    """Convert bytes to human-readable string (KB, MB, etc.)."""
    for unit in ("B", "KB", "MB", "GB"):
        if size_bytes < 1024:
            return f"{size_bytes:.1f}{unit}"
        size_bytes //= 1024
    return f"{size_bytes:.1f}TB"
