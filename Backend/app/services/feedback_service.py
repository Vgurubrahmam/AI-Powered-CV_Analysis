"""Feedback service — prioritized feedback retrieval, accept tracking, rewrites."""

from __future__ import annotations

import uuid
from typing import Any

import structlog
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ResourceNotFoundException, ValidationException
from app.core.constants import AnalysisStatus

log = structlog.get_logger(__name__)


class FeedbackService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get_feedback_for_analysis(
        self,
        analysis_id: uuid.UUID,
        user_id: uuid.UUID,
        limit: int = 20,
    ) -> list:
        """Return prioritized feedback items for a completed analysis.

        Validates that the analysis belongs to the requesting user and
        that it is in a terminal state before returning items.
        """
        from app.models.analysis import Analysis
        from app.models.feedback import FeedbackItem

        # Ownership + status check
        result = await self.db.execute(
            select(Analysis).where(
                Analysis.id == analysis_id,
                Analysis.user_id == user_id,
            )
        )
        analysis = result.scalar_one_or_none()
        if not analysis:
            raise ResourceNotFoundException(f"Analysis '{analysis_id}' not found.")
        if analysis.status not in (AnalysisStatus.DONE.value, AnalysisStatus.PARTIAL.value):
            raise ValidationException(
                f"Analysis is not yet complete (status: {analysis.status}). "
                "Please wait for it to finish before requesting feedback."
            )

        # Fetch feedback items ordered by score_delta desc (highest impact first)
        fb_result = await self.db.execute(
            select(FeedbackItem)
            .where(FeedbackItem.analysis_id == analysis_id)
            .order_by(FeedbackItem.score_delta.desc().nullslast())
            .limit(limit)
        )
        return list(fb_result.scalars().all())

    async def get_feedback_item(
        self,
        feedback_id: uuid.UUID,
        user_id: uuid.UUID,
    ):
        """Fetch a single feedback item, checking user ownership via analysis."""
        from app.models.feedback import FeedbackItem
        from app.models.analysis import Analysis

        result = await self.db.execute(
            select(FeedbackItem)
            .join(Analysis, Analysis.id == FeedbackItem.analysis_id)
            .where(
                FeedbackItem.id == feedback_id,
                Analysis.user_id == user_id,
            )
        )
        item = result.scalar_one_or_none()
        if not item:
            raise ResourceNotFoundException(f"Feedback item '{feedback_id}' not found.")
        return item

    async def mark_accepted(
        self,
        feedback_id: uuid.UUID,
        user_id: uuid.UUID,
    ):
        """Mark a feedback item as accepted by the user."""
        item = await self.get_feedback_item(feedback_id, user_id)
        await self.db.execute(
            update(type(item))
            .where(type(item).id == feedback_id)
            .values(is_accepted=True)
        )
        await self.db.flush()
        await self.db.refresh(item)
        log.info("feedback_item_accepted", feedback_id=str(feedback_id), user_id=str(user_id))
        return item

    async def request_rewrite(
        self,
        feedback_id: uuid.UUID,
        user_id: uuid.UUID,
        guidance: str | None = None,
    ) -> dict[str, Any]:
        """Trigger an LLM rewrite for a feedback item's original_text.

        Returns the rewrite result dict (rewritten_text, warning, passed).
        Does NOT persist the rewrite — the caller decides whether to save it.
        """
        from app.pipeline.feedback.rewrite_engine import rewrite_bullet
        from app.models.analysis import Analysis
        from app.models.resume import Resume
        from sqlalchemy import select

        item = await self.get_feedback_item(feedback_id, user_id)

        if not item.original_text:
            raise ValidationException(
                "This feedback item has no original text to rewrite."
            )

        # Fetch full resume text for hallucination guard
        analysis_result = await self.db.execute(
            select(Analysis).where(Analysis.id == item.analysis_id)
        )
        analysis = analysis_result.scalar_one_or_none()
        resume_text = ""
        if analysis:
            resume_result = await self.db.execute(
                select(Resume).where(Resume.id == analysis.resume_id)
            )
            resume = resume_result.scalar_one_or_none()
            if resume:
                resume_text = resume.raw_text or ""

        rewrite = await rewrite_bullet(
            original_text=item.original_text,
            source_resume_text=resume_text,
            improvement_guidance=guidance or item.description or "",
        )

        log.info(
            "rewrite_requested",
            feedback_id=str(feedback_id),
            passed=rewrite.hallucination_check_passed,
        )

        return {
            "original_text": rewrite.original_text,
            "rewritten_text": rewrite.rewritten_text,
            "hallucination_check_passed": rewrite.hallucination_check_passed,
            "flagged_entities": rewrite.flagged_entities,
            "warning": rewrite.warning,
            "model_used": rewrite.model_used,
        }
