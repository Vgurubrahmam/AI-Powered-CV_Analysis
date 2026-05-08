"""Feedback sub-package: generation, rewriting, priority ranking, hallucination guard."""

from app.pipeline.feedback.feedback_generator import generate_feedback, FeedbackItemData
from app.pipeline.feedback.hallucination_guard import check_hallucinations, HallucinationCheckResult
from app.pipeline.feedback.priority_ranker import rank_feedback_items
from app.pipeline.feedback.rewrite_engine import rewrite_bullet

__all__ = [
    "generate_feedback",
    "FeedbackItemData",
    "check_hallucinations",
    "HallucinationCheckResult",
    "rank_feedback_items",
    "rewrite_bullet",
]
