"""JobDescription repository."""

from __future__ import annotations

import uuid

from sqlalchemy import select

from app.models.job import JobDescription
from app.repositories.base import BaseRepository


class JobRepository(BaseRepository[JobDescription]):
    model = JobDescription

    async def get_by_user(
        self, user_id: uuid.UUID, *, limit: int = 20, offset: int = 0
    ) -> list[JobDescription]:
        result = await self.session.execute(
            select(JobDescription)
            .where(JobDescription.user_id == user_id)
            .order_by(JobDescription.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        return list(result.scalars().all())

    async def count_by_user(self, user_id: uuid.UUID) -> int:
        from sqlalchemy import func
        result = await self.session.execute(
            select(func.count())
            .select_from(JobDescription)
            .where(JobDescription.user_id == user_id)
        )
        return result.scalar_one()

