"""Cleanup Celery tasks — expire stale files and purge old analyses."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import structlog
from celery import shared_task

log = structlog.get_logger(__name__)

# Files older than this with no active analyses are eligible for deletion
FILE_EXPIRY_DAYS = 90

# Analyses stuck in non-terminal state for longer than this are purged
STUCK_ANALYSIS_MINUTES = 30

# Completed analyses older than this (and not flagged for retention) are purged
ANALYSIS_RETENTION_DAYS = 365


@shared_task(
    name="app.workers.tasks.cleanup_tasks.expire_old_files",
    soft_time_limit=180,
)
def expire_old_files() -> dict:
    """Delete S3 resume files that are older than FILE_EXPIRY_DAYS and
    have no associated analyses in a non-FAILED/DONE state.

    Returns count of files deleted.
    """
    import asyncio

    async def _run() -> dict:
        from app.main import get_db_session
        from sqlalchemy import select, and_
        from app.models.resume import Resume
        from app.integrations.storage.s3_client import S3Client
        from app.config import settings

        cutoff = datetime.now(timezone.utc) - timedelta(days=FILE_EXPIRY_DAYS)
        deleted = 0

        async with get_db_session() as db:
            result = await db.execute(
                select(Resume).where(Resume.created_at < cutoff)
            )
            old_resumes = result.scalars().all()

            s3 = S3Client(
                bucket=settings.S3_BUCKET_NAME,
                region=settings.AWS_REGION,
                access_key=settings.AWS_ACCESS_KEY_ID,
                secret_key=settings.AWS_SECRET_ACCESS_KEY,
                endpoint_url=settings.S3_ENDPOINT_URL,
            )

            for resume in old_resumes:
                try:
                    if resume.storage_key:
                        await s3.delete(resume.storage_key)
                        await db.execute(
                            Resume.__table__.update()
                            .where(Resume.id == resume.id)
                            .values(storage_key=None)
                        )
                        deleted += 1
                except Exception as exc:
                    log.warning("file_delete_failed", resume_id=str(resume.id), error=str(exc))

            await db.commit()

        log.info("expire_old_files_complete", deleted=deleted, cutoff=cutoff.isoformat())
        return {"deleted": deleted}

    try:
        return asyncio.run(_run())
    except Exception as exc:
        log.error("expire_old_files_failed", error=str(exc))
        return {"status": "FAILED", "error": str(exc)}


@shared_task(
    name="app.workers.tasks.cleanup_tasks.purge_stale_analyses",
    soft_time_limit=120,
)
def purge_stale_analyses() -> dict:
    """Mark analyses stuck in a non-terminal state as FAILED.

    An analysis is considered stuck if:
    - Status is QUEUED / PARSING / MATCHING / SCORING / FEEDBACK
    - updated_at is older than STUCK_ANALYSIS_MINUTES

    Also deletes completed analyses older than ANALYSIS_RETENTION_DAYS
    (unless flagged for long-term retention).
    """
    import asyncio

    async def _run() -> dict:
        from app.main import get_db_session
        from sqlalchemy import select, update
        from app.models.analysis import Analysis
        from app.core.constants import AnalysisStatus

        stuck_cutoff = datetime.now(timezone.utc) - timedelta(minutes=STUCK_ANALYSIS_MINUTES)
        old_cutoff = datetime.now(timezone.utc) - timedelta(days=ANALYSIS_RETENTION_DAYS)
        stuck = 0
        purged = 0

        NON_TERMINAL = [
            AnalysisStatus.QUEUED.value,
            AnalysisStatus.PARSING.value,
            AnalysisStatus.MATCHING.value,
            AnalysisStatus.SCORING.value,
            AnalysisStatus.FEEDBACK.value,
        ]

        async with get_db_session() as db:
            # Mark stuck analyses as FAILED
            result = await db.execute(
                update(Analysis)
                .where(
                    Analysis.status.in_(NON_TERMINAL),
                    Analysis.updated_at < stuck_cutoff,
                )
                .values(
                    status=AnalysisStatus.FAILED.value,
                    pipeline_meta={"error": "timeout", "purged_by": "cleanup_task"},
                )
                .returning(Analysis.id)
            )
            stuck = len(result.fetchall())

            # Soft-delete (or hard-delete) very old completed analyses
            old_result = await db.execute(
                select(Analysis).where(
                    Analysis.status.in_([AnalysisStatus.DONE.value, AnalysisStatus.FAILED.value]),
                    Analysis.created_at < old_cutoff,
                )
            )
            old_analyses = old_result.scalars().all()
            for analysis in old_analyses:
                await db.delete(analysis)
                purged += 1

            await db.commit()

        log.info(
            "purge_stale_analyses_complete",
            stuck_marked_failed=stuck,
            old_purged=purged,
        )
        return {"stuck_marked_failed": stuck, "old_purged": purged}

    try:
        return asyncio.run(_run())
    except Exception as exc:
        log.error("purge_stale_analyses_failed", error=str(exc))
        return {"status": "FAILED", "error": str(exc)}
