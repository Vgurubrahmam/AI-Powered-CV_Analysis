"""Structured JSON logging via structlog.

Every log line carries: request_id, user_id (if available), service, level, timestamp, event.
Never use print() or bare logging.getLogger() — always use structlog.get_logger().
"""

from __future__ import annotations

import logging
import sys

import structlog

from app.config import settings


def configure_logging() -> None:
    """Configure structlog for the application.

    In development: pretty-printed colored output.
    In production: compact JSON output (one line per event).
    """
    log_level = getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO)

    shared_processors: list = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
    ]

    if settings.is_development:
        # Human-readable dev output
        processors = [
            *shared_processors,
            structlog.dev.ConsoleRenderer(colors=True),
        ]
    else:
        # Machine-parseable JSON for log aggregators
        processors = [
            *shared_processors,
            structlog.processors.dict_tracebacks,
            structlog.processors.JSONRenderer(),
        ]

    structlog.configure(
        processors=processors,
        wrapper_class=structlog.make_filtering_bound_logger(log_level),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(sys.stdout),
        cache_logger_on_first_use=True,
    )

    # Also configure stdlib logging to route through structlog
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=log_level,
    )
    for noisy_logger in [
        "uvicorn.access",
        "sqlalchemy.engine",
        "sqlalchemy.pool",
        "httpcore",
        "httpx",
        "sentence_transformers",
    ]:
        logging.getLogger(noisy_logger).setLevel(logging.WARNING)
