"""Celery Beat schedule — periodic background tasks."""

from __future__ import annotations

from celery.schedules import crontab

from app.workers.celery_app import celery_app

celery_app.conf.beat_schedule = {
    # ── Nightly cleanup: expire old files and stale analyses ─────────────────
    "nightly-cleanup": {
        "task": "app.workers.tasks.cleanup_tasks.expire_old_files",
        "schedule": crontab(hour=2, minute=0),   # 02:00 UTC daily
        "options": {"queue": "default"},
    },
    "purge-stale-analyses": {
        "task": "app.workers.tasks.cleanup_tasks.purge_stale_analyses",
        "schedule": crontab(hour=3, minute=0),   # 03:00 UTC daily
        "options": {"queue": "default"},
    },

    # ── Score calibration refresh (weekly) ───────────────────────────────────
    "weekly-calibration-refresh": {
        "task": "app.workers.tasks.analysis_tasks.refresh_score_calibration",
        "schedule": crontab(day_of_week=0, hour=4, minute=0),  # Sunday 04:00 UTC
        "options": {"queue": "default"},
    },
}
