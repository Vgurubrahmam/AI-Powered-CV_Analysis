"""pytest configuration and shared fixtures.

All fixtures are async-compatible using pytest-asyncio.
The test DB is created fresh per session using the test DATABASE_URL.
"""

from __future__ import annotations

import asyncio
import os
import uuid
from typing import AsyncGenerator
from unittest.mock import AsyncMock, MagicMock

import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

# ── Force test env before any app import ──────────────────────────────────────
os.environ.setdefault("APP_ENV", "test")
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://ats_test:ats_test@localhost:5433/ats_test_db")
os.environ.setdefault("REDIS_URL", "redis://localhost:6380/0")
os.environ.setdefault("CELERY_BROKER_URL", "redis://localhost:6380/1")
os.environ.setdefault("CELERY_RESULT_BACKEND", "redis://localhost:6380/2")
os.environ.setdefault("S3_ENDPOINT_URL", "")
os.environ.setdefault("CLAMAV_HOST", "")
os.environ.setdefault("OPENROUTER_API_KEY", "")
os.environ.setdefault("EMBEDDING_PROVIDER", "local")


from app.models.base import Base  # noqa: E402


# ── Engine / session fixtures ─────────────────────────────────────────────────

@pytest.fixture(scope="session")
def event_loop():
    """Shared event loop for all session-scoped async fixtures."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="session")
async def db_engine():
    """Create the test database schema once per test session."""
    from app.config import settings
    engine = create_async_engine(settings.DATABASE_URL, echo=False)

    async with engine.begin() as conn:
        # Enable pgvector if available (skip gracefully in unit tests)
        try:
            from sqlalchemy import text
            await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        except Exception:
            pass
        await conn.run_sync(Base.metadata.create_all)

    yield engine

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture
async def db(db_engine) -> AsyncGenerator[AsyncSession, None]:
    """Provide a transactional DB session that rolls back after each test."""
    factory = async_sessionmaker(db_engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as session:
        # Use a savepoint to rollback cleanly
        async with session.begin_nested():
            yield session
        await session.rollback()


# ── Mock Redis ────────────────────────────────────────────────────────────────

@pytest.fixture
def mock_redis():
    """In-memory mock for Redis used in unit tests."""
    store = {}
    redis = AsyncMock()

    async def _set(key, value, ex=None, nx=False, **kwargs):
        if nx and key in store:
            return False
        store[key] = value
        return True

    async def _get(key):
        return store.get(key)

    async def _delete(*keys):
        for k in keys:
            store.pop(k, None)

    async def _ping():
        return True

    redis.set = _set
    redis.get = _get
    redis.delete = _delete
    redis.ping = _ping
    redis.pipeline = MagicMock(return_value=AsyncMock(
        execute=AsyncMock(return_value=[0, True, 0, True]),
        incrby=MagicMock(return_value=None),
        expire=MagicMock(return_value=None),
    ))
    return redis


# ── Sample data factories ─────────────────────────────────────────────────────

@pytest.fixture
def sample_user_data():
    return {
        "id": uuid.uuid4(),
        "email": f"test+{uuid.uuid4().hex[:8]}@example.com",
        "password_hash": "$2b$12$test_hash",
        "role": "candidate",
        "plan_tier": "free",
        "is_active": True,
    }


@pytest.fixture
def sample_resume_bytes():
    """Minimal valid PDF bytes (enough for format detection)."""
    return (
        b"%PDF-1.4\n1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n"
        b"2 0 obj\n<< /Type /Pages /Kids [3 0 R] /Count 1 >>\nendobj\n"
        b"3 0 obj\n<< /Type /Page /Parent 2 0 R /Resources << >> "
        b"/MediaBox [0 0 612 792] >>\nendobj\nxref\n0 4\ntrailer\n"
        b"<< /Size 4 /Root 1 0 R >>\nstartxref\n9\n%%EOF"
    )


@pytest.fixture
def sample_resume_text():
    return """John Doe
john.doe@example.com | +1 (555) 000-1234 | San Francisco, CA
github.com/johndoe | linkedin.com/in/johndoe

SUMMARY
Senior Software Engineer with 7 years of experience building scalable backend systems.
Expertise in Python, FastAPI, PostgreSQL, and cloud infrastructure.

EXPERIENCE
Senior Software Engineer — Acme Corp (2021 - Present)
• Designed and implemented REST APIs serving 2M+ requests per day using FastAPI and PostgreSQL
• Reduced API latency by 40% through Redis caching and query optimization
• Led a team of 4 engineers to migrate monolith to microservices architecture

Software Engineer — StartupXYZ (2018 - 2021)
• Built data pipeline processing 500k records/day using Python and Airflow
• Implemented CI/CD workflows reducing deployment time from 2 hours to 15 minutes

SKILLS
Python, FastAPI, Django, PostgreSQL, Redis, Docker, Kubernetes, AWS, Celery, Airflow

EDUCATION
B.S. Computer Science — Stanford University (2018)

CERTIFICATIONS
AWS Certified Solutions Architect - Associate (2022)
"""


# ── FastAPI test client ────────────────────────────────────────────────────────

@pytest_asyncio.fixture
async def app(db, mock_redis) -> FastAPI:
    """Return the FastAPI app with DB/Redis dependencies overridden."""
    from app.main import app as _app
    from app.dependencies import get_db, get_redis

    _app.dependency_overrides[get_db] = lambda: db
    _app.dependency_overrides[get_redis] = lambda: mock_redis

    yield _app

    _app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def client(app) -> AsyncGenerator[AsyncClient, None]:
    """Async HTTP test client for endpoint tests."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac


@pytest_asyncio.fixture
async def auth_client(client, db) -> AsyncGenerator[AsyncClient, None]:
    """Authenticated HTTP test client with a valid JWT for a test candidate."""
    from app.core.security import hash_password, create_access_token
    from app.models.user import User

    test_user = User(
        id=uuid.uuid4(),
        email=f"auth+{uuid.uuid4().hex[:8]}@test.local",
        password_hash=hash_password("TestPass123!"),
        role="candidate",
        plan_tier="pro",
        is_active=True,
    )
    db.add(test_user)
    await db.flush()

    token = create_access_token({"sub": str(test_user.id), "role": test_user.role})
    client.headers["Authorization"] = f"Bearer {token}"
    yield client
