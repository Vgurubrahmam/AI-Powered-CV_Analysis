"""JobDescription ORM model."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.constants import ParseStatus
from app.models.base import Base, TimestampMixin, UUIDPKMixin


class JobDescription(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "job_descriptions"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    title: Mapped[str | None] = mapped_column(String(512), nullable=True)
    company: Mapped[str | None] = mapped_column(String(512), nullable=True)
    raw_text: Mapped[str] = mapped_column(Text, nullable=False)
    parsed_data: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)

    parse_status: Mapped[str] = mapped_column(
        String, nullable=False, default=ParseStatus.PENDING.value
    )


    # ── Relationships ──────────────────────────────────────────────────────
    user: Mapped["User"] = relationship("User", back_populates="job_descriptions")  # noqa: F821
    analyses: Mapped[list["Analysis"]] = relationship(  # noqa: F821
        "Analysis", back_populates="job"
    )

    def __repr__(self) -> str:
        return f"<JobDescription {self.title} status={self.parse_status}>"
