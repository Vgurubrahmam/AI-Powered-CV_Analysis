"""Audit log repository — append only, no update/delete."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import select

from app.models.audit import AuditLog
from app.repositories.base import BaseRepository


class AuditRepository(BaseRepository[AuditLog]):
    model = AuditLog

    async def log(
        self,
        action: str,
        *,
        user_id: uuid.UUID | None = None,
        resource: str | None = None,
        resource_id: uuid.UUID | None = None,
        ip_address: str | None = None,
        user_agent: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> AuditLog:
        """Append an audit event. Never update or delete audit records."""
        # Pack user_agent + any extra metadata into the details JSONB column
        details: dict[str, Any] = {}
        if user_agent:
            details["user_agent"] = user_agent
        if metadata:
            details.update(metadata)

        return await self.create(
            {
                "user_id": user_id,
                "action": action,          # mapped → event_type column
                "resource": resource,      # mapped → resource_type column
                "resource_id": str(resource_id) if resource_id else None,
                "ip_address": ip_address,
                "extra_data": details or None,   # mapped → details column
            }
        )

    # ── Explicitly remove mutating methods ────────────────────────────────
    async def update(self, *args, **kwargs):  # type: ignore[override]
        raise NotImplementedError("Audit logs are immutable — updates are not permitted.")

    async def delete(self, *args, **kwargs):  # type: ignore[override]
        raise NotImplementedError("Audit logs are immutable — deletes are not permitted.")
