"""FeedbackItem ORM model."""

from __future__ import annotations

import uuid

from sqlalchemy import Boolean, ForeignKey, Numeric, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.constants import FeedbackCategory, FeedbackSeverity
from app.models.base import Base, TimestampMixin, UUIDPKMixin


class FeedbackItem(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "feedback_items"

    analysis_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("analyses.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    category: Mapped[str] = mapped_column(String, nullable=False)    # FeedbackCategory
    severity: Mapped[str] = mapped_column(String, nullable=False)    # FeedbackSeverity
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)

    original_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    suggested_text: Mapped[str | None] = mapped_column(Text, nullable=True)

    score_delta: Mapped[float | None] = mapped_column(Numeric(5, 2), nullable=True)
    source_section: Mapped[str | None] = mapped_column(String, nullable=True)
    is_accepted: Mapped[bool | None] = mapped_column(Boolean, nullable=True)

    # ── Relationships ──────────────────────────────────────────────────────
    analysis: Mapped["Analysis"] = relationship(  # noqa: F821
        "Analysis", back_populates="feedback_items"
    )

    def __repr__(self) -> str:
        return f"<FeedbackItem {self.category}/{self.severity} delta={self.score_delta}>"
