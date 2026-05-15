"""Shared FastAPI dependency providers.

All `Depends()` callables live here so they can be imported without
creating circular imports across the rest of the codebase.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Annotated, AsyncGenerator

import redis.asyncio as aioredis
import structlog
from fastapi import Depends, Header, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

from app.config import settings
from app.core.constants import UserRole
from app.core.exceptions import AuthException
from app.core.security import decode_access_token, is_token_blacklisted

log = structlog.get_logger(__name__)

# ─── Database ─────────────────────────────────────────────────────────────────

_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


def get_db_engine() -> AsyncEngine:
    """Return (or create) the SQLAlchemy async engine singleton."""
    global _engine
    if _engine is None:
        _engine = create_async_engine(
            settings.DATABASE_URL,
            echo=False,
            pool_size=10,
            max_overflow=20,
            pool_pre_ping=True,
            pool_recycle=3600,
            connect_args={
                "statement_cache_size": 0,   # required for pgbouncer
                "prepared_statement_cache_size": 0,
            },
        )
    return _engine


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    """Return (or create) the async session factory singleton."""
    global _session_factory
    if _session_factory is None:
        _session_factory = async_sessionmaker(
            bind=get_db_engine(),
            class_=AsyncSession,
            expire_on_commit=False,
            autoflush=False,
            autocommit=False,
        )
    return _session_factory


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency: yield an async DB session per request."""
    factory = get_session_factory()
    async with factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


DBSession = Annotated[AsyncSession, Depends(get_db)]

# ─── Redis ────────────────────────────────────────────────────────────────────

_redis_client: aioredis.Redis | None = None


def get_redis_client() -> aioredis.Redis:
    """Return (or create) the Redis client singleton."""
    global _redis_client
    if _redis_client is None:
        _redis_client = aioredis.from_url(
            settings.REDIS_URL,
            encoding="utf-8",
            decode_responses=True,
            max_connections=50,
        )
    return _redis_client


async def get_redis() -> aioredis.Redis:
    """FastAPI dependency: return the Redis client."""
    return get_redis_client()


RedisClient = Annotated[aioredis.Redis, Depends(get_redis)]

# ─── Authentication ───────────────────────────────────────────────────────────

_bearer_scheme = HTTPBearer(auto_error=False)


async def get_current_user_payload(
    request: Request,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer_scheme)],
    redis: RedisClient,
) -> dict:
    """Validate JWT and return its payload.

    Token resolution order:
      1. HttpOnly cookie ``access_token`` (browser auth — most secure)
      2. ``Authorization: Bearer <token>`` header (API clients, Swagger UI)

    Raises AuthException if neither source provides a valid token.
    """
    token: str | None = None

    # 1) Cookie (set by login endpoint)
    token = request.cookies.get("access_token")

    # 2) Authorization header fallback
    if not token and credentials is not None:
        token = credentials.credentials

    if not token:
        raise AuthException("Authentication required. Please log in.")

    payload = decode_access_token(token)

    # Check token blacklist (logout invalidation) — skip if Redis is down
    jti = payload.get("jti")
    if jti:
        try:
            if await is_token_blacklisted(redis, jti):
                raise AuthException("Token has been revoked. Please log in again.")
        except AuthException:
            raise
        except Exception:
            # Redis unavailable — skip blacklist check (JWT signature still valid)
            pass

    return payload


CurrentUserPayload = Annotated[dict, Depends(get_current_user_payload)]


async def get_current_user(
    payload: CurrentUserPayload,
    db: DBSession,
):
    """Return the User ORM instance for the authenticated request."""
    from app.models.user import User
    from app.repositories.user_repo import UserRepository

    user_id = payload.get("sub")
    if not user_id:
        raise AuthException("Invalid token payload.")

    repo = UserRepository(db)
    user = await repo.get(user_id)
    if user is None:
        raise AuthException("User no longer exists.")
    if not user.is_active:
        raise AuthException("User account is deactivated.")

    return user


# Import User here at module level for the Annotated alias
# This is safe because dependencies.py is loaded after models
from app.models.user import User as _User  # noqa: E402

CurrentUser = Annotated[_User, Depends(get_current_user)]


def require_role(*roles: UserRole):
    """Dependency factory: require the current user to have one of the given roles."""

    async def _check_role(user: CurrentUser):
        if user.role not in [r.value for r in roles]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions for this action.",
            )
        return user

    return _check_role


def require_admin():
    """Shortcut: require system_admin role."""
    return require_role(UserRole.SYSTEM_ADMIN)
