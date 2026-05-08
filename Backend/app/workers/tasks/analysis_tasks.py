"""Analysis Celery tasks — full pipeline and partial reanalysis."""

from __future__ import annotations

import asyncio
import uuid

import structlog
from celery import shared_task
from sqlalchemy.ext.asyncio import AsyncSession

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
    name="app.workers.tasks.analysis_tasks.run_full_analysis",
    bind=True,
    max_retries=2,
    default_retry_delay=60,
    soft_time_limit=300,
    time_limit=600,
)
def run_full_analysis(self, analysis_id: str) -> dict:
    """Run the complete AI analysis pipeline for a given analysis_id.

    This task:
    1. Creates an async DB session
    2. Calls the pipeline orchestrator
    3. Updates the analysis record with final status + score
    4. Releases the distributed lock

    On failure: retries up to 2 times with 60s delay. After exhaustion,
    marks the analysis as FAILED and releases the lock.
    """
    from app.pipeline.orchestrator import run_pipeline
    from app.core.exceptions import PipelineException

    async def _run() -> dict:
        from app.main import get_db_session, get_redis
        async with get_db_session() as db:
            redis = await get_redis()
            try:
                result = await run_pipeline(
                    analysis_id=uuid.UUID(analysis_id),
                    db=db,
                    redis=redis,
                )
                return {
                    "status": result.status,
                    "score": result.score_result.composite if result.score_result else None,
                    "feedback_count": len(result.feedback_items),
                    "stage_errors": result.stage_errors,
                }
            except PipelineException as exc:
                log.error("pipeline_failed", analysis_id=analysis_id, error=str(exc))
                raise
            finally:
                # Always release the distributed lock
                analysis_obj = await _get_analysis(db, analysis_id)
                if analysis_obj:
                    lock_key = f"lock:analysis:{analysis_obj.resume_id}:{analysis_obj.job_id}"
                    await redis.delete(lock_key)

    try:
        return _run_in_worker_loop(_run())
    except Exception as exc:
        log.error("full_analysis_task_failed", analysis_id=analysis_id, error=str(exc))
        try:
            raise self.retry(exc=exc)
        except self.MaxRetriesExceededError:
            _mark_analysis_failed_sync(analysis_id)
            return {"status": "FAILED", "error": str(exc)}


@shared_task(
    name="app.workers.tasks.analysis_tasks.run_partial_reanalysis",
    bind=True,
    max_retries=1,
    soft_time_limit=180,
)
def run_partial_reanalysis(self, analysis_id: str, stage: str) -> dict:
    """Re-run a single pipeline stage for an existing analysis.

    Useful for: re-running feedback after JD edit, refreshing semantic score
    after embedding model upgrade.

    Args:
        analysis_id: UUID string of the existing analysis.
        stage: One of 'matching', 'scoring', 'feedback'.
    """
    log.info("partial_reanalysis_started", analysis_id=analysis_id, stage=stage)

    VALID_STAGES = {"matching", "scoring", "feedback"}
    if stage not in VALID_STAGES:
        log.error("invalid_stage", stage=stage)
        return {"status": "ERROR", "error": f"Invalid stage: {stage}"}

    async def _run() -> dict:
        from app.main import get_db_session
        async with get_db_session() as db:
            from app.pipeline.orchestrator import run_pipeline
            # For partial re-runs we call the full orchestrator but it
            # uses cached parsed_data and skips re-parsing
            result = await run_pipeline(uuid.UUID(analysis_id), db=db)
            return {"status": result.status}

    try:
        return _run_in_worker_loop(_run())
    except Exception as exc:
        log.error("partial_reanalysis_failed", analysis_id=analysis_id, error=str(exc))
        try:
            raise self.retry(exc=exc)
        except self.MaxRetriesExceededError:
            return {"status": "FAILED", "error": str(exc)}


@shared_task(name="app.workers.tasks.analysis_tasks.refresh_score_calibration")
def refresh_score_calibration() -> dict:
    """Weekly task: recompute score percentile distribution from completed analyses."""
    async def _run() -> dict:
        from app.main import get_db_session
        from app.pipeline.scoring.calibrator import rebuild_percentile_table
        async with get_db_session() as db:
            count = await rebuild_percentile_table(db)
            log.info("calibration_refreshed", samples=count)
            return {"samples_used": count}

    try:
        return _run_in_worker_loop(_run())
    except Exception as exc:
        log.error("calibration_refresh_failed", error=str(exc))
        return {"status": "FAILED", "error": str(exc)}


# ─── Internal helpers ─────────────────────────────────────────────────────────

async def _get_analysis(db, analysis_id: str):
    from app.repositories.analysis_repo import AnalysisRepository
    repo = AnalysisRepository(db)
    try:
        return await repo.get(uuid.UUID(analysis_id))
    except Exception:
        return None


def _mark_analysis_failed_sync(analysis_id: str) -> None:
    """Best-effort sync fallback to mark analysis FAILED when all retries exhausted."""
    from app.core.constants import AnalysisStatus

    async def _mark():
        from app.main import get_db_session
        async with get_db_session() as db:
            analysis = await _get_analysis(db, analysis_id)
            if analysis:
                from app.repositories.analysis_repo import AnalysisRepository
                repo = AnalysisRepository(db)
                await repo.update(analysis, {"status": AnalysisStatus.FAILED.value})

    try:
        _run_in_worker_loop(_mark())
    except Exception as exc:
        log.error("mark_failed_error", error=str(exc))
