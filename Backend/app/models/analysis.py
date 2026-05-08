"""Analysis ORM model — central pipeline result container."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

import sqlalchemy as sa
from sqlalchemy import DateTime, ForeignKey, Numeric, String
from sqlalchemy.dialects import postgresql
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.constants import AnalysisStatus
from app.models.base import Base, TimestampMixin, UUIDPKMixin


class Analysis(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "analyses"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    resume_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("resumes.id", ondelete="CASCADE"), nullable=False
    )
    job_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("job_descriptions.id", ondelete="CASCADE"),
        nullable=False,
    )

    status: Mapped[str] = mapped_column(
        String, nullable=False, default=AnalysisStatus.QUEUED.value, index=True
    )

    # ── Scores ────────────────────────────────────────────────────────────
    score: Mapped[float | None] = mapped_column(Numeric(5, 2), nullable=True)
    score_breakdown: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    confidence: Mapped[float | None] = mapped_column(Numeric(4, 3), nullable=True)
    percentile: Mapped[float | None] = mapped_column(Numeric(5, 2), nullable=True)

    # ── Detail JSONB fields ───────────────────────────────────────────────
    keyword_detail: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    semantic_detail: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    experience_detail: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    ats_warnings: Mapped[list[str] | None] = mapped_column(postgresql.ARRAY(sa.Text), nullable=True)

    # ── Meta ──────────────────────────────────────────────────────────────
    pipeline_meta: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Fields for partial analysis tracking
    celery_task_id: Mapped[str | None] = mapped_column(String(256), nullable=True)

    # ── Relationships ──────────────────────────────────────────────────────
    user: Mapped["User"] = relationship("User", back_populates="analyses")  # noqa: F821
    resume: Mapped["Resume"] = relationship("Resume", back_populates="analyses")  # noqa: F821
    job: Mapped["JobDescription"] = relationship(  # noqa: F821
        "JobDescription", back_populates="analyses"
    )
    feedback_items: Mapped[list["FeedbackItem"]] = relationship(  # noqa: F821
        "FeedbackItem", back_populates="analysis", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Analysis {self.id} status={self.status} score={self.score}>"
