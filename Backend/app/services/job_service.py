"""Job Description service."""

from __future__ import annotations

import uuid

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import ParseStatus
from app.core.exceptions import ResourceNotFoundException, PermissionException
from app.models.job import JobDescription
from app.repositories.job_repo import JobRepository
from app.schemas.job import JDCreate, ParsedJDData, ParsedJDRead

log = structlog.get_logger(__name__)


class JobService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.repo = JobRepository(db)

    # ── aliases used by the API routes ─────────────────────────────────

    async def create_job(self, user_id: uuid.UUID, payload: JDCreate) -> JobDescription:
        """Create a JD record and enqueue async parsing."""
        jd = await self.repo.create(
            {
                "user_id": user_id,
                "title": payload.title,
                "company": payload.company,
                "raw_text": payload.raw_text,
                "parse_status": ParseStatus.PENDING.value,
            }
        )

        # Enqueue async JD parsing via Celery
        try:
            from app.workers.tasks.parsing_tasks import parse_jd_async
            parse_jd_async.apply_async(
                kwargs={"job_id": str(jd.id)},
                queue="parsing",
            )
            log.info("jd_queued_for_parsing", jd_id=str(jd.id))
        except Exception as exc:
            log.warning("jd_celery_enqueue_failed", jd_id=str(jd.id), error=str(exc))
            # Sync fallback: parse inline if Celery is unavailable
            try:
                await self._parse_jd_sync(jd)
            except Exception as parse_exc:
                log.error("jd_sync_parse_failed", jd_id=str(jd.id), error=str(parse_exc))

        log.info("jd_created", jd_id=str(jd.id))
        return jd

    async def _parse_jd_sync(self, jd: JobDescription) -> None:
        """Synchronous fallback: parse JD inline when Celery is unavailable."""
        from app.pipeline.parsing.jd_parser import parse_job_description
        raw_text = jd.raw_text or ""
        if not raw_text.strip():
            return
        try:
            parsed = await parse_job_description(raw_text)
            await self.repo.update(jd, {
                "parsed_data": parsed,
                "parse_status": ParseStatus.SUCCESS.value,
            })
            log.info("jd_parsed_sync", jd_id=str(jd.id))
        except Exception as exc:
            await self.repo.update(jd, {"parse_status": ParseStatus.FAILED.value})
            log.error("jd_sync_parse_error", jd_id=str(jd.id), error=str(exc))

    async def get_job(self, jd_id: uuid.UUID, user_id: uuid.UUID) -> JobDescription:
        """Get a single JD by id, ensuring ownership."""
        jd = await self.repo.get(jd_id)
        if not jd:
            raise ResourceNotFoundException(f"Job description '{jd_id}' not found.")
        if jd.user_id != user_id:
            raise PermissionException("You don't have access to this job description.")
        return jd

    async def get_parsed_job(self, jd_id: uuid.UUID, user_id: uuid.UUID) -> ParsedJDRead:
        """Return JD with parsed data attached."""
        jd = await self.get_job(jd_id, user_id)
        parsed_data = None
        if jd.parsed_data:
            parsed_data = ParsedJDData.model_validate(jd.parsed_data)
        return ParsedJDRead(
            id=jd.id,
            user_id=jd.user_id,
            title=jd.title,
            company=jd.company,
            parse_status=jd.parse_status,
            created_at=jd.created_at,
            parsed_data=parsed_data,
            raw_text=jd.raw_text,
        )

    async def list_jobs(
        self, user_id: uuid.UUID, *, limit: int = 20, offset: int = 0
    ) -> tuple[list[JobDescription], int]:
        """Return paginated list of JDs for a user, plus total count."""
        items = await self.repo.get_by_user(user_id, limit=limit, offset=offset)
        total = await self.repo.count_by_user(user_id)
        return items, total
