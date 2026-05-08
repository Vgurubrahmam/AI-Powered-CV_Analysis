"""Resume repository."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import func, select

from app.models.resume import Resume
from app.repositories.base import BaseRepository


class ResumeRepository(BaseRepository[Resume]):
    model = Resume

    async def get_by_user(
        self, user_id: uuid.UUID, *, limit: int = 20, offset: int = 0
    ) -> list[Resume]:
        result = await self.session.execute(
            select(Resume)
            .where(Resume.user_id == user_id)
            .order_by(Resume.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        return list(result.scalars().all())

    async def get_user_resume(self, resume_id: uuid.UUID, user_id: uuid.UUID) -> Resume | None:
        """Get resume by ID scoped to a specific user (prevents cross-user access)."""
        result = await self.session.execute(
            select(Resume).where(Resume.id == resume_id, Resume.user_id == user_id)
        )
        return result.scalar_one_or_none()

    async def update_parse_result(
        self,
        resume: Resume,
        raw_text: str,
        parsed_data: dict[str, Any],
        parse_status: str,
        parse_confidence: float,
    ) -> Resume:
        return await self.update(
            resume,
            {
                "raw_text": raw_text,
                "parsed_data": parsed_data,
                "parse_status": parse_status,
                "parse_confidence": parse_confidence,
            },
        )

    async def count_by_user(self, user_id: uuid.UUID) -> int:
        result = await self.session.execute(
            select(func.count()).select_from(Resume).where(Resume.user_id == user_id)
        )
        return result.scalar_one()

