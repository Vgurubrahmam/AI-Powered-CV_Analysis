"""Crypto utilities — hashing, token generation."""

from __future__ import annotations

import hashlib
import secrets
import uuid


def sha256_hex(data: str | bytes) -> str:
    """Return SHA-256 hex digest of the input."""
    if isinstance(data, str):
        data = data.encode("utf-8")
    return hashlib.sha256(data).hexdigest()


def sha256_cache_key(*parts: str) -> str:
    """Build a SHA-256 cache key from multiple string parts."""
    combined = "|".join(parts)
    return sha256_hex(combined)


def generate_token(length: int = 32) -> str:
    """Generate a cryptographically secure random hex token."""
    return secrets.token_hex(length)


def generate_uuid() -> str:
    return str(uuid.uuid4())
