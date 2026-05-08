"""Resume and ResumeEmbedding ORM models."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import BigInteger, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.constants import FileType, ParseStatus
from app.models.base import Base, TimestampMixin, UUIDPKMixin


class Resume(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "resumes"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    storage_key: Mapped[str | None] = mapped_column(String, nullable=True)  # S3/local object key
    filename: Mapped[str] = mapped_column(String, nullable=False)
    file_type: Mapped[str | None] = mapped_column(String, nullable=True)  # pdf | docx | txt
    file_size_bytes: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    content_type: Mapped[str | None] = mapped_column(String, nullable=True)  # MIME type
    ocr_used: Mapped[bool] = mapped_column(default=False, nullable=False)

    raw_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    parsed_data: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)

    parse_status: Mapped[str] = mapped_column(
        String, nullable=False, default=ParseStatus.PENDING.value
    )
    parse_confidence: Mapped[float | None] = mapped_column(Numeric(4, 3), nullable=True)
    language: Mapped[str] = mapped_column(String(10), default="en", nullable=False)
    version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)

    # ── Relationships ──────────────────────────────────────────────────────
    user: Mapped["User"] = relationship("User", back_populates="resumes")  # noqa: F821
    embeddings: Mapped[list["ResumeEmbedding"]] = relationship(
        "ResumeEmbedding", back_populates="resume", cascade="all, delete-orphan"
    )
    analyses: Mapped[list["Analysis"]] = relationship(  # noqa: F821
        "Analysis", back_populates="resume"
    )

    def __repr__(self) -> str:
        return f"<Resume {self.filename} status={self.parse_status}>"
