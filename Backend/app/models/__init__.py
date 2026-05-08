"""Models package — import all models here so Alembic can discover them."""

from app.models.analysis import Analysis
from app.models.audit import AuditLog
from app.models.base import Base
from app.models.feedback import FeedbackItem
from app.models.job import JobDescription
from app.models.resume import Resume
from app.models.resume_embedding import ResumeEmbedding
from app.models.user import User

__all__ = [
    "Base",
    "User",
    "Resume",
    "ResumeEmbedding",
    "JobDescription",
    "Analysis",
    "FeedbackItem",
    "AuditLog",
]
