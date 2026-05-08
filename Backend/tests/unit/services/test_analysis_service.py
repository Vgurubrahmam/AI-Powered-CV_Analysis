"""Unit tests for AnalysisService.create_analysis."""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio

from app.core.exceptions import ConflictException, ResourceNotFoundException, ParseException
from app.core.constants import ParseStatus
from app.schemas.analysis import AnalysisRequest
from app.services.analysis_service import AnalysisService


class TestAnalysisServiceCreate:

    @pytest_asyncio.fixture
    async def setup_data(self, db):
        """Create user, resume, and JD for testing."""
        from app.models.user import User
        from app.models.resume import Resume
        from app.models.job import JobDescription
        from app.core.security import hash_password

        user = User(
            id=uuid.uuid4(),
            email=f"analysistest+{uuid.uuid4().hex[:6]}@test.local",
            password_hash=hash_password("Pass123!"),
            role="candidate",
            plan_tier="pro",
            is_active=True,
        )
        db.add(user)

        resume = Resume(
            id=uuid.uuid4(),
            user_id=user.id,
            filename="test_resume.pdf",
            file_type="pdf",
            parse_status=ParseStatus.SUCCESS.value,
            parse_confidence=0.95,
        )
        db.add(resume)

        jd = JobDescription(
            id=uuid.uuid4(),
            user_id=user.id,
            title="Software Engineer",
            raw_text="We need a Python developer with FastAPI experience.",
            parse_status="SUCCESS",
        )
        db.add(jd)
        await db.flush()

        return {"user": user, "resume": resume, "jd": jd}

    @pytest.mark.asyncio
    async def test_create_analysis_success(self, db, mock_redis, setup_data):
        user = setup_data["user"]
        resume = setup_data["resume"]
        jd = setup_data["jd"]

        payload = AnalysisRequest(resume_id=resume.id, job_id=jd.id)

        with patch("app.workers.tasks.analysis_tasks.run_full_analysis") as mock_task:
            mock_task.apply_async = AsyncMock(return_value=MagicMock(id="test-task-id"))
            svc = AnalysisService(db=db, redis=mock_redis)
            result = await svc.create_analysis(payload, user.id)

        assert result.analysis_id is not None
        assert result.status.value in ("QUEUED", "queued")

    @pytest.mark.asyncio
    async def test_create_analysis_resume_not_found(self, db, mock_redis, setup_data):
        user = setup_data["user"]
        jd = setup_data["jd"]
        payload = AnalysisRequest(resume_id=uuid.uuid4(), job_id=jd.id)
        svc = AnalysisService(db=db, redis=mock_redis)
        with pytest.raises(ResourceNotFoundException):
            await svc.create_analysis(payload, user.id)

    @pytest.mark.asyncio
    async def test_create_analysis_failed_resume_raises(self, db, mock_redis):
        from app.models.user import User
        from app.models.resume import Resume
        from app.models.job import JobDescription
        from app.core.security import hash_password

        user = User(id=uuid.uuid4(), email=f"t2+{uuid.uuid4().hex[:6]}@t.local",
                    password_hash=hash_password("P!"), role="candidate", plan_tier="free", is_active=True)
        db.add(user)
        resume = Resume(id=uuid.uuid4(), user_id=user.id, filename="f.pdf",
                        file_type="pdf", parse_status=ParseStatus.FAILED.value)
        db.add(resume)
        jd = JobDescription(id=uuid.uuid4(), user_id=user.id, title="J",
                            raw_text="x", parse_status="SUCCESS")
        db.add(jd)
        await db.flush()

        payload = AnalysisRequest(resume_id=resume.id, job_id=jd.id)
        svc = AnalysisService(db=db, redis=mock_redis)
        with pytest.raises(ParseException):
            await svc.create_analysis(payload, user.id)

    @pytest.mark.asyncio
    async def test_duplicate_analysis_raises_conflict(self, db, mock_redis, setup_data):
        """Second identical request should raise ConflictException (lock held)."""
        user = setup_data["user"]
        resume = setup_data["resume"]
        jd = setup_data["jd"]
        payload = AnalysisRequest(resume_id=resume.id, job_id=jd.id)

        # Simulate lock already held
        lock_key = f"lock:analysis:{resume.id}:{jd.id}"
        await mock_redis.set(lock_key, "1")

        svc = AnalysisService(db=db, redis=mock_redis)
        with pytest.raises(ConflictException):
            await svc.create_analysis(payload, user.id)


from unittest.mock import MagicMock  # noqa: E402 — placed here to avoid polluting top-level
