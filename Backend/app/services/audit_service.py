"""Audit service — convenience wrapper to log write events."""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.audit_repo import AuditRepository


class AuditService:
    def __init__(self, db: AsyncSession) -> None:
        self.repo = AuditRepository(db)

    async def log(
        self,
        action: str,
        *,
        user_id: uuid.UUID | None = None,
        resource: str | None = None,
        resource_id: uuid.UUID | None = None,
        request: Request | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        ip = None
        user_agent = None
        if request:
            ip = request.client.host if request.client else None
            user_agent = request.headers.get("user-agent")

        await self.repo.log(
            action=action,
            user_id=user_id,
            resource=resource,
            resource_id=resource_id,
            ip_address=ip,
            user_agent=user_agent,
            metadata=metadata,
        )
