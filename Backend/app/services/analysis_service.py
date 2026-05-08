"""Analysis service — orchestrate full analysis pipeline."""

from __future__ import annotations

import uuid

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.constants import AnalysisStatus, ParseStatus
from app.core.exceptions import (
    ConflictException,
    ParseException,
    ResourceNotFoundException,
    ValidationException,
)
from app.repositories.analysis_repo import AnalysisRepository
from app.repositories.job_repo import JobRepository
from app.repositories.resume_repo import ResumeRepository
from app.schemas.analysis import AnalysisCreateResponse, AnalysisRequest

log = structlog.get_logger(__name__)


class AnalysisService:
    def __init__(self, db: AsyncSession, redis) -> None:
        self.db = db
        self.redis = redis
        self.repo = AnalysisRepository(db)
        self.resume_repo = ResumeRepository(db)
        self.job_repo = JobRepository(db)

    def _lock_key(self, resume_id: uuid.UUID, job_id: uuid.UUID) -> str:
        return f"lock:analysis:{resume_id}:{job_id}"

    async def create_analysis(
        self, payload: AnalysisRequest, user_id: uuid.UUID
    ) -> AnalysisCreateResponse:
        """Validate inputs, acquire lock, create Analysis record, enqueue Celery task."""

        # ── Validate resume exists and belongs to user ─────────────────────
        resume = await self.resume_repo.get_user_resume(payload.resume_id, user_id)
        if not resume:
            raise ResourceNotFoundException(f"Resume '{payload.resume_id}' not found.")
        if resume.parse_status == ParseStatus.FAILED.value:
            raise ParseException(
                "The selected resume failed to parse. Please upload a valid resume file."
            )

        # ── Validate JD exists ─────────────────────────────────────────────
        jd = await self.job_repo.get(payload.job_id)
        if not jd:
            raise ResourceNotFoundException(f"Job description '{payload.job_id}' not found.")

        # ── Distributed lock — prevent duplicate parallel analyses ─────────
        lock_key = self._lock_key(payload.resume_id, payload.job_id)
        acquired = await self.redis.set(lock_key, "1", nx=True, ex=settings.LOCK_TTL_SECONDS)
        if not acquired:
            raise ConflictException(
                "An analysis for this resume+job combination is already in progress. "
                "Please wait for it to complete before starting a new one."
            )

        # ── Create Analysis record ─────────────────────────────────────────
        analysis = await self.repo.create(
            {
                "user_id": user_id,
                "resume_id": payload.resume_id,
                "job_id": payload.job_id,
                "status": AnalysisStatus.QUEUED.value,
            }
        )

        # ── Enqueue Celery task ────────────────────────────────────────────
        from app.workers.tasks.analysis_tasks import run_full_analysis
        task = run_full_analysis.apply_async(
            kwargs={"analysis_id": str(analysis.id)},
            queue="default",
        )
        await self.repo.update(analysis, {"celery_task_id": task.id})

        log.info("analysis_queued", analysis_id=str(analysis.id), task_id=task.id)

        return AnalysisCreateResponse(
            analysis_id=analysis.id,
            status=AnalysisStatus.QUEUED,
        )

    async def get_analysis(self, analysis_id: uuid.UUID, user_id: uuid.UUID):
        """Get analysis result scoped to user."""
        analysis = await self.repo.get_user_analysis(analysis_id, user_id)
        if not analysis:
            raise ResourceNotFoundException(f"Analysis '{analysis_id}' not found.")
        return analysis

    async def get_feedback(self, analysis_id: uuid.UUID, user_id: uuid.UUID) -> list:
        """Get prioritized feedback items for an analysis."""
        analysis = await self.get_analysis(analysis_id, user_id)
        if analysis.status not in (AnalysisStatus.DONE.value, AnalysisStatus.PARTIAL.value):
            raise ValidationException("Analysis has not completed yet.")

        from app.repositories.base import BaseRepository
        from app.models.feedback import FeedbackItem
        from sqlalchemy import select
        result = await self.db.execute(
            select(FeedbackItem)
            .where(FeedbackItem.analysis_id == analysis_id)
            .order_by(FeedbackItem.score_delta.desc().nullslast())
        )
        return list(result.scalars().all())

    async def list_analyses(
        self, user_id: uuid.UUID, *, limit: int = 20, offset: int = 0
    ) -> tuple[list, int]:
        """Return paginated list of analyses for a user, plus total count."""
        items = await self.repo.get_by_user(user_id, limit=limit, offset=offset)
        total = await self.repo.count_by_user(user_id)
        return items, total

    async def get_stats(self, user_id: uuid.UUID) -> dict:
        """Return summary stats for the dashboard."""
        total = await self.repo.count_by_user(user_id)
        avg_score = await self.repo.avg_score_by_user(user_id)
        return {"total_analyses": total, "avg_score": avg_score}

