"""Auth service — login, token issuance, refresh, logout."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.constants import PlanTier
from app.core.exceptions import AuthException, ConflictException
from app.core.security import (
    blacklist_token,
    create_access_token,
    create_refresh_token,
    decode_refresh_token,
    hash_password,
    verify_password,
)
from app.repositories.audit_repo import AuditRepository
from app.repositories.user_repo import UserRepository
from app.schemas.auth import LoginRequest, TokenPair
from app.schemas.user import UserCreate

log = structlog.get_logger(__name__)


class AuthService:
    def __init__(self, db: AsyncSession, redis=None) -> None:
        self.db = db
        self.redis = redis
        self.user_repo = UserRepository(db)
        self.audit_repo = AuditRepository(db)

    async def register(self, payload: UserCreate, ip: str = "") -> "User":  # type: ignore[name-defined]
        """Create a new user. Raises ConflictException if email already exists."""
        if await self.user_repo.email_exists(payload.email.lower()):
            raise ConflictException(f"An account with email '{payload.email}' already exists.")

        user = await self.user_repo.create(
            {
                "email": payload.email.lower(),
                "password_hash": hash_password(payload.password),
                "role": payload.role.value,
                "plan_tier": PlanTier.FREE.value,
                "is_active": True,
            }
        )
        await self.audit_repo.log(
            "user.registered", user_id=user.id, resource="user", resource_id=user.id, ip_address=ip
        )
        log.info("user_registered", user_id=str(user.id), email=user.email)
        return user

    async def login(
        self, email: str, password: str, ip: str = ""
    ) -> TokenPair:
        """Validate credentials and return access + refresh tokens."""
        user = await self.user_repo.get_active_by_email(email.lower())
        if user is None or not verify_password(password, user.password_hash):
            raise AuthException("Invalid email or password.")
        if not user.is_active:
            raise AuthException("Account is deactivated. Contact support.")

        access_token, access_jti = create_access_token(
            user_id=str(user.id),
            email=user.email,
            role=user.role,
            plan_tier=user.plan_tier,
        )
        refresh_token, _ = create_refresh_token(user_id=str(user.id))

        await self.audit_repo.log(
            "user.login", user_id=user.id, resource="user", resource_id=user.id, ip_address=ip
        )
        log.info("user_logged_in", user_id=str(user.id))

        return TokenPair(
            access_token=access_token,
            refresh_token=refresh_token,
            expires_in=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        )

    async def refresh(self, refresh_token: str) -> TokenPair:
        """Issue new access token using a valid refresh token."""
        payload = decode_refresh_token(refresh_token)
        user_id = payload.get("sub")

        user = await self.user_repo.get(user_id)
        if user is None or not user.is_active:
            raise AuthException("User not found or deactivated.")

        access_token, _ = create_access_token(
            user_id=str(user.id),
            email=user.email,
            role=user.role,
            plan_tier=user.plan_tier,
        )
        new_refresh_token, _ = create_refresh_token(user_id=str(user.id))

        return TokenPair(
            access_token=access_token,
            refresh_token=new_refresh_token,
            expires_in=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        )

    async def logout(self, user_payload: dict) -> None:
        """Blacklist the access token's JTI so it can't be reused."""
        access_jti = user_payload.get("jti", "")
        ttl_seconds = settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60
        await blacklist_token(self.redis, access_jti, ttl_seconds)
        log.info("user_logged_out", jti=access_jti)
