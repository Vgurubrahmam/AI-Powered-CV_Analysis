"""E2E API tests — analysis lifecycle endpoints."""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio

from app.core.constants import ParseStatus, AnalysisStatus


class TestAnalysisAPI:
    """HTTP-level tests for POST /v1/analysis, GET /{id}, GET /{id}/score."""

    @pytest_asyncio.fixture
    async def analysis_data(self, db, auth_client):
        """Set up resume + JD for the authenticated test user, return IDs."""
        from app.models.user import User
        from app.models.resume import Resume
        from app.models.job import JobDescription
        from app.models.analysis import Analysis
        from sqlalchemy import select

        # Get the current user from the auth token
        me_resp = await auth_client.get("/v1/users/me")
        user_id = uuid.UUID(me_resp.json()["data"]["id"])

        resume = Resume(
            id=uuid.uuid4(),
            user_id=user_id,
            filename="cv.pdf",
            file_type="pdf",
            parse_status=ParseStatus.SUCCESS.value,
            parse_confidence=0.92,
            parsed_data={
                "raw_text": "Python developer 5 years.",
                "skills": ["python", "fastapi"],
                "experience": [],
                "education": [],
                "sections_dict": {},
                "sections_detected": [],
                "contact": {},
                "certifications": [],
            },
        )
        db.add(resume)

        jd = JobDescription(
            id=uuid.uuid4(),
            user_id=user_id,
            title="Python Engineer",
            raw_text="Python FastAPI required.",
            parse_status="SUCCESS",
            parsed_data={
                "required_skills": ["python", "fastapi"],
                "preferred_skills": [],
                "required_yoe_min": 2,
                "required_degree": None,
                "seniority_level": "mid",
                "title": "Python Engineer",
            },
        )
        db.add(jd)
        await db.flush()

        return {"resume_id": str(resume.id), "job_id": str(jd.id)}

    @pytest.mark.asyncio
    async def test_create_analysis_returns_202(self, auth_client, analysis_data):
        with patch("app.workers.tasks.analysis_tasks.run_full_analysis") as mock_task:
            mock_task.apply_async = MagicMock(return_value=MagicMock(id="task-abc"))
            response = await auth_client.post(
                "/v1/analysis",
                json=analysis_data,
            )
        assert response.status_code == 202
        body = response.json()
        assert body["data"]["analysis_id"]
        assert body["data"]["status"] in ("QUEUED", "queued")

    @pytest.mark.asyncio
    async def test_get_analysis_status(self, auth_client, analysis_data, db):
        """Create an analysis record and poll its status."""
        from app.models.analysis import Analysis
        from sqlalchemy import select

        me_resp = await auth_client.get("/v1/users/me")
        user_id = uuid.UUID(me_resp.json()["data"]["id"])

        analysis = Analysis(
            id=uuid.uuid4(),
            user_id=user_id,
            resume_id=uuid.UUID(analysis_data["resume_id"]),
            job_id=uuid.UUID(analysis_data["job_id"]),
            status=AnalysisStatus.DONE.value,
            score=72.5,
            confidence=0.88,
        )
        db.add(analysis)
        await db.flush()

        response = await auth_client.get(f"/v1/analysis/{analysis.id}")
        assert response.status_code == 200
        data = response.json()["data"]
        assert data["status"] == "DONE"

    @pytest.mark.asyncio
    async def test_get_nonexistent_analysis_returns_404(self, auth_client):
        response = await auth_client.get(f"/v1/analysis/{uuid.uuid4()}")
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_duplicate_analysis_returns_409(self, auth_client, analysis_data, mock_redis):
        """Second create for same resume+jd while lock held → 409 Conflict."""
        lock_key = (
            f"lock:analysis:"
            f"{analysis_data['resume_id']}:"
            f"{analysis_data['job_id']}"
        )
        await mock_redis.set(lock_key, "1")

        response = await auth_client.post("/v1/analysis", json=analysis_data)
        assert response.status_code == 409

    @pytest.mark.asyncio
    async def test_analysis_score_endpoint(self, auth_client, analysis_data, db):
        """GET /analysis/{id}/score returns breakdown for completed analysis."""
        from app.models.analysis import Analysis

        me_resp = await auth_client.get("/v1/users/me")
        user_id = uuid.UUID(me_resp.json()["data"]["id"])

        analysis = Analysis(
            id=uuid.uuid4(),
            user_id=user_id,
            resume_id=uuid.UUID(analysis_data["resume_id"]),
            job_id=uuid.UUID(analysis_data["job_id"]),
            status=AnalysisStatus.DONE.value,
            score=85.0,
            confidence=0.91,
            score_breakdown={"keyword": 90.0, "semantic": 80.0},
        )
        db.add(analysis)
        await db.flush()

        response = await auth_client.get(f"/v1/analysis/{analysis.id}/score")
        assert response.status_code == 200
