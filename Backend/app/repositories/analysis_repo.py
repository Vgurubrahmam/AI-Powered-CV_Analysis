"""Analysis repository."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import func, select

from app.core.constants import AnalysisStatus
from app.models.analysis import Analysis
from app.repositories.base import BaseRepository


class AnalysisRepository(BaseRepository[Analysis]):
    model = Analysis

    async def get_by_user(
        self,
        user_id: uuid.UUID,
        *,
        status: str | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> list[Analysis]:
        stmt = (
            select(Analysis)
            .where(Analysis.user_id == user_id)
            .order_by(Analysis.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        if status:
            stmt = stmt.where(Analysis.status == status)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_user_analysis(
        self, analysis_id: uuid.UUID, user_id: uuid.UUID
    ) -> Analysis | None:
        """Get analysis by ID scoped to user."""
        result = await self.session.execute(
            select(Analysis).where(
                Analysis.id == analysis_id,
                Analysis.user_id == user_id,
            )
        )
        return result.scalar_one_or_none()

    async def update_status(
        self, analysis: Analysis, status: AnalysisStatus, error_detail: dict | None = None
    ) -> Analysis:
        updates: dict = {"status": status.value}
        if status in (AnalysisStatus.DONE, AnalysisStatus.FAILED, AnalysisStatus.PARTIAL):
            updates["completed_at"] = datetime.now(UTC)
        if error_detail:
            updates["error_detail"] = error_detail
        return await self.update(analysis, updates)

    async def get_stuck_analyses(self, timeout_minutes: int = 10) -> list[Analysis]:
        """Return analyses that have been QUEUED/PARSING for too long."""
        from datetime import timedelta
        cutoff = datetime.now(UTC) - timedelta(minutes=timeout_minutes)
        result = await self.session.execute(
            select(Analysis).where(
                Analysis.status.in_([AnalysisStatus.QUEUED.value, AnalysisStatus.PARSING.value]),
                Analysis.created_at < cutoff,
            )
        )
        return list(result.scalars().all())

    async def count_by_user(self, user_id: uuid.UUID) -> int:
        result = await self.session.execute(
            select(func.count()).select_from(Analysis).where(Analysis.user_id == user_id)
        )
        return result.scalar_one()

    async def avg_score_by_user(self, user_id: uuid.UUID) -> float | None:
        result = await self.session.execute(
            select(func.avg(Analysis.score))
            .where(Analysis.user_id == user_id)
            .where(Analysis.status == AnalysisStatus.DONE.value)
            .where(Analysis.score.isnot(None))
        )
        val = result.scalar_one_or_none()
        return float(val) if val is not None else None

