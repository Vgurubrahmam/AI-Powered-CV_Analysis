"""ResumeEmbedding ORM model — stores pgvector embeddings per resume section."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import DateTime, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, UUIDPKMixin


class ResumeEmbedding(UUIDPKMixin, Base):
    __tablename__ = "resume_embeddings"

    resume_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("resumes.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    section: Mapped[str] = mapped_column(String, nullable=False)  # summary|experience|skills|full
    embedding: Mapped[list[float]] = mapped_column(Vector(768), nullable=False)
    model_id: Mapped[str] = mapped_column(String, nullable=False)  # e.g. "all-mpnet-base-v2"
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        server_default=func.now(),
        nullable=False,
    )

    # ── Relationships ──────────────────────────────────────────────────────
    resume: Mapped["Resume"] = relationship("Resume", back_populates="embeddings")  # noqa: F821

    def __repr__(self) -> str:
        return f"<ResumeEmbedding resume={self.resume_id} section={self.section}>"
