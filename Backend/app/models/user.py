"""User ORM model."""

from __future__ import annotations

from sqlalchemy import Boolean, String, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.constants import PlanTier, UserRole
from app.models.base import Base, TimestampMixin, UUIDPKMixin


class User(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "users"

    email: Mapped[str] = mapped_column(String, unique=True, nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(String, nullable=False)
    role: Mapped[str] = mapped_column(
        String, nullable=False, default=UserRole.CANDIDATE.value
    )
    plan_tier: Mapped[str] = mapped_column(
        String, nullable=False, default=PlanTier.FREE.value
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # ── Relationships ──────────────────────────────────────────────────────
    resumes: Mapped[list["Resume"]] = relationship(  # noqa: F821
        "Resume", back_populates="user", cascade="all, delete-orphan"
    )
    job_descriptions: Mapped[list["JobDescription"]] = relationship(  # noqa: F821
        "JobDescription", back_populates="user"
    )
    analyses: Mapped[list["Analysis"]] = relationship(  # noqa: F821
        "Analysis", back_populates="user"
    )

    def __repr__(self) -> str:
        try:
            return f"<User {self.email} role={self.role}>"
        except Exception:
            return f"<User id={self.__dict__.get('id', '?')}>"
