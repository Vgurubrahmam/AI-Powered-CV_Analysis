"""JWT security helpers: encode/decode tokens, password hashing, blacklist check."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import redis.asyncio as aioredis
from jose import JWTError, jwt
from passlib.context import CryptContext

from app.config import settings
from app.core.exceptions import AuthException

# ─── Password hashing ─────────────────────────────────────────────────────────

_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(plain: str) -> str:
    """Return bcrypt hash of the plaintext password."""
    return _pwd_context.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    """Return True if plain matches the bcrypt hash."""
    return _pwd_context.verify(plain, hashed)


# ─── JWT helpers ──────────────────────────────────────────────────────────────

def _build_token(
    subject: str,
    token_type: str,
    extra: dict[str, Any],
    expire_delta: timedelta,
) -> tuple[str, str]:
    """Build a signed JWT. Returns (encoded_token, jti)."""
    jti = str(uuid.uuid4())
    now = datetime.now(UTC)
    payload = {
        "sub": subject,
        "type": token_type,
        "jti": jti,
        "iat": now,
        "exp": now + expire_delta,
        **extra,
    }
    encoded = jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)
    return encoded, jti


def create_access_token(
    user_id: str,
    email: str,
    role: str,
    plan_tier: str,
) -> tuple[str, str]:
    """Return (access_token, jti). Token expires in ACCESS_TOKEN_EXPIRE_MINUTES."""
    return _build_token(
        subject=user_id,
        token_type="access",
        extra={"email": email, "role": role, "plan": plan_tier},
        expire_delta=timedelta(minutes=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES),
    )


def create_refresh_token(user_id: str) -> tuple[str, str]:
    """Return (refresh_token, jti). Token expires in REFRESH_TOKEN_EXPIRE_DAYS."""
    return _build_token(
        subject=user_id,
        token_type="refresh",
        extra={},
        expire_delta=timedelta(days=settings.JWT_REFRESH_TOKEN_EXPIRE_DAYS),
    )


def decode_access_token(token: str) -> dict[str, Any]:
    """Decode and verify a JWT. Raises AuthException on any failure."""
    try:
        payload = jwt.decode(
            token,
            settings.JWT_SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM],
        )
    except JWTError as exc:
        raise AuthException(f"Invalid or expired token: {exc}") from exc

    if payload.get("type") != "access":
        raise AuthException("Token type mismatch — expected access token.")

    return payload


def decode_refresh_token(token: str) -> dict[str, Any]:
    """Decode and verify a refresh token. Raises AuthException on failure."""
    try:
        payload = jwt.decode(
            token,
            settings.JWT_SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM],
        )
    except JWTError as exc:
        raise AuthException(f"Invalid or expired refresh token: {exc}") from exc

    if payload.get("type") != "refresh":
        raise AuthException("Token type mismatch — expected refresh token.")

    return payload


# ─── Token blacklist (Redis) ──────────────────────────────────────────────────

def _blacklist_key(jti: str) -> str:
    return f"token:blacklist:{jti}"


async def blacklist_token(redis: aioredis.Redis, jti: str, ttl_seconds: int) -> None:
    """Add a JWT ID to the blacklist with the remaining TTL of the token."""
    await redis.setex(_blacklist_key(jti), ttl_seconds, "1")


async def is_token_blacklisted(redis: aioredis.Redis, jti: str) -> bool:
    """Return True if the JWT ID is in the blacklist."""
    result = await redis.get(_blacklist_key(jti))
    return result is not None
