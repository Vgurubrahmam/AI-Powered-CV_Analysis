"""Celery application — broker, backend, queue routing, task defaults."""

from __future__ import annotations

import app.core.force_ipv4  # noqa: F401 — must be first to patch DNS before any connections

from celery import Celery
from kombu import Exchange, Queue

from app.config import settings

# ── Create Celery instance ────────────────────────────────────────────────────
celery_app = Celery(
    "ats_platform",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=[
        "app.workers.tasks.parsing_tasks",
        "app.workers.tasks.embedding_tasks",
        "app.workers.tasks.analysis_tasks",
        "app.workers.tasks.notification_tasks",
        "app.workers.tasks.cleanup_tasks",
    ],
)

# ── Serialization ─────────────────────────────────────────────────────────────
celery_app.conf.task_serializer = "json"
celery_app.conf.result_serializer = "json"
celery_app.conf.accept_content = ["json"]
celery_app.conf.timezone = "UTC"
celery_app.conf.enable_utc = True

# ── Task defaults ─────────────────────────────────────────────────────────────
celery_app.conf.task_soft_time_limit = settings.CELERY_TASK_SOFT_TIME_LIMIT   # 5 min
celery_app.conf.task_time_limit = settings.CELERY_TASK_TIME_LIMIT              # 10 min
celery_app.conf.task_acks_late = True       # Ack only after task completes
celery_app.conf.task_reject_on_worker_lost = True  # Re-queue on worker crash
celery_app.conf.worker_prefetch_multiplier = 1     # One task at a time per worker

# ── Result expiry ─────────────────────────────────────────────────────────────
celery_app.conf.result_expires = 86400  # Results expire after 24 hours

# ── Queues & routing ──────────────────────────────────────────────────────────
default_exchange = Exchange("default", type="direct")
llm_exchange = Exchange("llm", type="direct")
parsing_exchange = Exchange("parsing", type="direct")
embeddings_exchange = Exchange("embeddings", type="direct")

celery_app.conf.task_queues = (
    Queue("default", default_exchange, routing_key="default"),
    Queue("parsing", parsing_exchange, routing_key="parsing"),
    Queue("llm", llm_exchange, routing_key="llm"),
    Queue("embeddings", embeddings_exchange, routing_key="embeddings"),
)

celery_app.conf.task_default_queue = "default"
celery_app.conf.task_default_exchange = "default"
celery_app.conf.task_default_routing_key = "default"

celery_app.conf.task_routes = {
    "app.workers.tasks.parsing_tasks.*": {"queue": "parsing"},
    "app.workers.tasks.embedding_tasks.*": {"queue": "embeddings"},
    "app.workers.tasks.analysis_tasks.run_full_analysis": {"queue": "default"},
    "app.workers.tasks.analysis_tasks.run_partial_reanalysis": {"queue": "default"},
    "app.workers.tasks.notification_tasks.*": {"queue": "default"},
    "app.workers.tasks.cleanup_tasks.*": {"queue": "default"},
}

# ── Beat schedule (periodic tasks) ────────────────────────────────────────────
# Loaded separately via beat_schedule.py but referenced here for Celery discovery
celery_app.conf.beat_schedule_filename = "celerybeat-schedule"

# ── Retry policy defaults ─────────────────────────────────────────────────────
celery_app.conf.task_annotations = {
    "*": {
        "max_retries": 3,
        "default_retry_delay": 30,  # seconds
    }
}
