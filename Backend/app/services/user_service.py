"""User service — registration, profile, role management."""

from __future__ import annotations

import uuid

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictException, ResourceNotFoundException
from app.core.security import hash_password
from app.repositories.user_repo import UserRepository
from app.schemas.user import UserAdminUpdate, UserCreate, UserUpdate

log = structlog.get_logger(__name__)


class UserService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.repo = UserRepository(db)

    async def get_by_id(self, user_id: uuid.UUID):
        user = await self.repo.get(user_id)
        if not user:
            raise ResourceNotFoundException(f"User '{user_id}' not found.")
        return user

    async def update_profile(self, user_id: uuid.UUID, payload: UserUpdate):
        user = await self.get_by_id(user_id)
        updates = {}
        if payload.email:
            if await self.repo.email_exists(payload.email.lower()):
                raise ConflictException("Email already in use.")
            updates["email"] = payload.email.lower()
        if payload.password:
            updates["password_hash"] = hash_password(payload.password)
        if not updates:
            return user
        return await self.repo.update(user, updates)

    async def admin_update(self, user_id: uuid.UUID, payload: UserAdminUpdate):
        user = await self.get_by_id(user_id)
        updates = payload.model_dump(exclude_none=True)
        if "role" in updates:
            updates["role"] = updates["role"].value
        if "plan_tier" in updates:
            updates["plan_tier"] = updates["plan_tier"].value
        return await self.repo.update(user, updates)

    async def list_users(self, *, limit: int = 50, offset: int = 0) -> list:
        return await self.repo.get_multi(limit=limit, offset=offset)
