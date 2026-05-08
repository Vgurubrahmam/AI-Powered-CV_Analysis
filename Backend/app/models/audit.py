"""AuditLog ORM model — append-only.

NOTE: Column names are mapped to match the existing Supabase schema which uses
  event_type (not action), resource_type (not resource), details (not metadata).
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, UUIDPKMixin


class AuditLog(UUIDPKMixin, Base):
    """Immutable audit trail. Application code must NEVER UPDATE or DELETE rows here."""

    __tablename__ = "audit_logs"

    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    # DB column: event_type  (ORM attr: action for back-compat)
    action: Mapped[str] = mapped_column("event_type", String(256), nullable=False)
    # DB column: resource_type  (ORM attr: resource for back-compat)
    resource: Mapped[str | None] = mapped_column("resource_type", String(128), nullable=True)
    resource_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    ip_address: Mapped[str | None] = mapped_column(String(256), nullable=True)
    # DB column: details  (stores extra JSON including user_agent)
    extra_data: Mapped[dict[str, Any] | None] = mapped_column("details", JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        server_default=func.now(),
        nullable=False,
        index=True,
    )

    def __repr__(self) -> str:
        return f"<AuditLog {self.action} user={self.user_id}>"
