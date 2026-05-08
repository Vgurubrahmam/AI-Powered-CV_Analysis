"""FastAPI application factory.

Responsibilities:
  - Create and configure the FastAPI app
  - Register middleware (CORS, request-id, timing, rate-limit)
  - Register global exception handlers
  - Mount all API routers
  - Manage lifespan (DB pool init, Redis handshake, model warm-up)
"""

from __future__ import annotations

import app.core.force_ipv4  # noqa: F401 — must be first to patch DNS before any connections

from contextlib import asynccontextmanager
from typing import AsyncGenerator

import structlog
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from prometheus_fastapi_instrumentator import Instrumentator

from app.api.router import api_router
from app.config import settings
from app.core.exceptions import register_exception_handlers
from app.core.logging import configure_logging
from app.core.middleware import RequestContextMiddleware

log = structlog.get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Startup and shutdown lifecycle manager."""
    import asyncio
    import os

    # ── Startup ──────────────────────────────────────────────────────────
    configure_logging()
    log.info("ats_platform_starting", env=settings.APP_ENV)

    # Set model cache directory before any sentence-transformers import
    os.environ.setdefault("SENTENCE_TRANSFORMERS_HOME", settings.SENTENCE_TRANSFORMERS_HOME)

    # Lazy-import heavy singletons to avoid import-time side effects
    from app.dependencies import get_db_engine, get_redis_client

    # Verify DB connection (non-fatal — allows frontend dev without DB)
    engine = get_db_engine()
    try:
        from sqlalchemy import text

        async with engine.begin() as conn:
            await conn.execute(text("SELECT 1"))
        log.info("database_connected")
    except Exception as exc:
        log.error("database_connection_failed", error=str(exc))
        log.warning("app_starting_without_db", hint="DB-dependent routes will fail")

    # Verify Redis connection (skip if disabled)
    if settings.ENABLE_REDIS:
        try:
            redis = get_redis_client()
            await redis.ping()
            log.info("redis_connected")
        except Exception as exc:
            log.warning("redis_connection_failed", error=str(exc))
    else:
        log.info("redis_skipped", reason="ENABLE_REDIS=false")

    # Warm up embedding model in background (skip if disabled)
    if settings.ENABLE_EMBEDDINGS:
        async def _warmup_embeddings():
            try:
                from app.integrations.embeddings.client import get_embedding_client
                embedding_client = get_embedding_client()
                await embedding_client.warmup()
                log.info("embedding_model_ready", model=settings.SBERT_MODEL_NAME)
            except Exception as exc:
                log.warning("embedding_model_warmup_failed", error=str(exc))

        asyncio.create_task(_warmup_embeddings())
        log.info("embedding_warmup_scheduled", model=settings.SBERT_MODEL_NAME)
    else:
        log.info("embeddings_skipped", reason="ENABLE_EMBEDDINGS=false")

    log.info("ats_platform_ready", url=settings.APP_URL)

    yield  # ── Application running ──────────────────────────────────────

    # ── Shutdown ─────────────────────────────────────────────────────────
    log.info("ats_platform_shutting_down")
    await engine.dispose()
    log.info("ats_platform_stopped")



# ─── Context managers for Celery tasks ───────────────────────────────────────
# These allow Celery workers to create DB sessions and Redis connections
# outside of FastAPI's dependency injection system.

from contextlib import asynccontextmanager as _acm


@_acm
async def get_db_session():
    """Async context manager: yield an AsyncSession (for use in Celery tasks)."""
    from app.dependencies import get_session_factory
    factory = get_session_factory()
    async with factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def get_redis():
    """Return the shared Redis client (for use in Celery tasks)."""
    from app.dependencies import get_redis_client
    return get_redis_client()


def create_app() -> FastAPI:
    """Application factory — build and return the configured FastAPI app."""
    app = FastAPI(
        title="ATS Platform API",
        description="Enterprise AI-Powered Resume Analysis & ATS Platform",
        version="1.0.0",
        docs_url="/docs" if not settings.is_production else None,
        redoc_url="/redoc" if not settings.is_production else None,
        openapi_url="/openapi.json" if not settings.is_production else None,
        lifespan=lifespan,
    )

    # ── Middleware (applied bottom-up, last registered = outermost) ───────
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.allowed_origins_list,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["*"],
    )
    app.add_middleware(RequestContextMiddleware)

    # ── Exception handlers ────────────────────────────────────────────────
    register_exception_handlers(app)

    # ── Routes ────────────────────────────────────────────────────────────
    app.include_router(api_router, prefix="/api")

    # ── Prometheus metrics ────────────────────────────────────────────────
    Instrumentator(
        should_group_status_codes=True,
        should_ignore_untemplated=True,
        should_respect_env_var=True,
        env_var_name="ENABLE_METRICS",
    ).instrument(app).expose(app, endpoint="/metrics", include_in_schema=False)

    # ── Health check (outside versioned router) ───────────────────────────
    @app.get("/health", include_in_schema=False, tags=["ops"])
    async def health_check() -> dict:
        return {"status": "ok", "env": settings.APP_ENV, "version": "1.0.0"}

    return app


# Module-level app instance used by uvicorn and tests
app = create_app()
