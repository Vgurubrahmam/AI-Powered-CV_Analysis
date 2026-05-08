"""Parsing Celery tasks — async resume + JD parsing workers."""

from __future__ import annotations

import asyncio
import uuid

import structlog
from celery import shared_task

log = structlog.get_logger(__name__)
_worker_loop: asyncio.AbstractEventLoop | None = None


def _run_in_worker_loop(coro):
    """Run async code on a single persistent loop per worker process."""
    global _worker_loop

    if _worker_loop is None or _worker_loop.is_closed():
        _worker_loop = asyncio.new_event_loop()
        asyncio.set_event_loop(_worker_loop)

    return _worker_loop.run_until_complete(coro)


@shared_task(
    name="app.workers.tasks.parsing_tasks.parse_resume_async",
    bind=True,
    max_retries=2,
    default_retry_delay=30,
    soft_time_limit=120,
)
def parse_resume_async(self, resume_id: str) -> dict:
    """Parse a resume file and persist structured data to the Resume record.

    Fetches file bytes from S3, runs the parsing pipeline,
    and updates the DB with parsed_data + parse_status + parse_confidence.
    """
    from app.core.constants import ParseStatus

    async def _run() -> dict:
        from app.main import get_db_session
        from app.repositories.resume_repo import ResumeRepository
        from app.pipeline.parsing.resume_parser import parse_resume

        async with get_db_session() as db:
            repo = ResumeRepository(db)
            resume = await repo.get(uuid.UUID(resume_id))
            if not resume:
                log.error("resume_not_found_for_parsing", resume_id=resume_id)
                return {"status": "ERROR"}

            # Download via configured storage backend (local/s3/minio)
            from app.services.storage_service import StorageService

            storage = StorageService()
            file_bytes = await storage.download_resume(resume.storage_key)
            file_type = (resume.file_type or "pdf").lower()

            # Parse
            parsed = parse_resume(file_bytes, file_type)

            # Persist result
            import dataclasses
            parsed_data = dataclasses.asdict(parsed)
            await repo.update(resume, {
                "parse_status": parsed.parse_status,
                "parse_confidence": parsed.parse_confidence,
                "parsed_data": parsed_data,
            })

            log.info(
                "resume_parsed_async",
                resume_id=resume_id,
                status=parsed.parse_status,
                confidence=parsed.parse_confidence,
            )
            return {
                "status": parsed.parse_status,
                "confidence": parsed.parse_confidence,
            }

    try:
        return _run_in_worker_loop(_run())
    except Exception as exc:
        log.error("parse_resume_task_failed", resume_id=resume_id, error=str(exc))
        # Persist failure so clients don't poll forever on PENDING.
        try:
            async def _mark_failed() -> None:
                from app.main import get_db_session
                from app.repositories.resume_repo import ResumeRepository
                from app.core.constants import ParseStatus

                async with get_db_session() as db:
                    repo = ResumeRepository(db)
                    resume = await repo.get(uuid.UUID(resume_id))
                    if resume:
                        await repo.update(
                            resume,
                            {"parse_status": ParseStatus.FAILED.value},
                        )

            _run_in_worker_loop(_mark_failed())
        except Exception as status_exc:
            log.error(
                "parse_resume_status_update_failed",
                resume_id=resume_id,
                error=str(status_exc),
            )
        try:
            raise self.retry(exc=exc)
        except self.MaxRetriesExceededError:
            return {"status": "FAILED", "error": str(exc)}


@shared_task(
    name="app.workers.tasks.parsing_tasks.parse_jd_async",
    bind=True,
    max_retries=2,
    default_retry_delay=30,
    soft_time_limit=90,
)
def parse_jd_async(self, job_id: str) -> dict:
    """Parse a job description via LLM and persist structured data.

    Reads the raw JD text from the JobDescription record, calls the LLM
    parser, and persists parsed_data back to the DB.
    """
    async def _run() -> dict:
        from app.main import get_db_session
        from app.repositories.job_repo import JobRepository
        from app.pipeline.parsing.jd_parser import parse_job_description

        async with get_db_session() as db:
            repo = JobRepository(db)
            jd = await repo.get(uuid.UUID(job_id))
            if not jd:
                log.error("jd_not_found_for_parsing", job_id=job_id)
                return {"status": "ERROR"}

            raw_text = jd.raw_text or jd.description or ""
            if not raw_text.strip():
                return {"status": "SKIPPED", "reason": "empty_text"}

            parsed = await parse_job_description(raw_text)
            await repo.update(jd, {"parsed_data": parsed})

            log.info("jd_parsed_async", job_id=job_id, skills=len(parsed.get("required_skills", [])))
            return {"status": "SUCCESS", "required_skills": len(parsed.get("required_skills", []))}

    try:
        return _run_in_worker_loop(_run())
    except Exception as exc:
        log.error("parse_jd_task_failed", job_id=job_id, error=str(exc))
        try:
            raise self.retry(exc=exc)
        except self.MaxRetriesExceededError:
            return {"status": "FAILED", "error": str(exc)}
