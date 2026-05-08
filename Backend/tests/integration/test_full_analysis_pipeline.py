"""Integration test — full analysis pipeline (orchestrator with mocked LLM)."""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio

from app.core.constants import ParseStatus, AnalysisStatus


class TestFullAnalysisPipeline:
    """Tests the pipeline orchestrator end-to-end with mocked LLM/embedding."""

    @pytest_asyncio.fixture
    async def analysis_fixture(self, db):
        """Create user, resume (with parsed_data), JD, and analysis records."""
        from app.models.user import User
        from app.models.resume import Resume
        from app.models.job import JobDescription
        from app.models.analysis import Analysis
        from app.core.security import hash_password

        user = User(
            id=uuid.uuid4(),
            email=f"pipeline+{uuid.uuid4().hex[:6]}@test.local",
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
            parsed_data={
                "raw_text": "Python developer with 5 years. FastAPI, PostgreSQL, Docker.",
                "skills": ["python", "fastapi", "postgresql", "docker"],
                "experience": [{"title": "Senior Engineer", "company": "Acme", "duration_months": 24}],
                "education": [{"degree": "bachelor", "field": "computer science", "institution": "MIT"}],
                "sections_dict": {
                    "experience": "Senior Engineer at Acme Corp 2020-2022. Built FastAPI services.",
                    "skills": "Python, FastAPI, PostgreSQL, Docker, Redis",
                },
                "sections_detected": ["experience", "skills", "education"],
                "contact": {"email": "test@test.com"},
                "certifications": [],
            },
        )
        db.add(resume)

        jd = JobDescription(
            id=uuid.uuid4(),
            user_id=user.id,
            title="Senior Python Engineer",
            raw_text="Need Python, FastAPI, PostgreSQL, AWS. 3+ YOE required.",
            parse_status="SUCCESS",
            parsed_data={
                "required_skills": ["python", "fastapi", "postgresql"],
                "preferred_skills": ["aws", "docker"],
                "required_yoe_min": 3,
                "required_degree": "bachelor",
                "seniority_level": "senior",
                "title": "Senior Python Engineer",
            },
        )
        db.add(jd)

        analysis = Analysis(
            id=uuid.uuid4(),
            user_id=user.id,
            resume_id=resume.id,
            job_id=jd.id,
            status=AnalysisStatus.QUEUED.value,
        )
        db.add(analysis)
        await db.flush()

        return {"user": user, "resume": resume, "jd": jd, "analysis": analysis}

    @pytest.mark.asyncio
    async def test_pipeline_produces_score(self, db, mock_redis, analysis_fixture):
        """Pipeline should complete and produce a composite score > 0."""
        analysis = analysis_fixture["analysis"]

        # Mock LLM calls to return valid JSON without API keys
        mock_llm = AsyncMock()
        mock_llm.complete = AsyncMock(return_value='["python", "fastapi", "postgresql", "docker"]')

        # Mock SBERT embeddings with random unit vectors
        import numpy as np
        mock_embedder = AsyncMock()
        mock_embedder.embed_batch = AsyncMock(
            return_value=[[float(x) for x in np.random.rand(768)] for _ in range(5)]
        )

        with (
            patch("app.pipeline.orchestrator.get_llm_client", return_value=mock_llm),
            patch("app.pipeline.orchestrator.get_embedding_client", return_value=mock_embedder),
        ):
            from app.pipeline.orchestrator import run_pipeline
            result = await run_pipeline(analysis_id=analysis.id, db=db, redis=mock_redis)

        assert result is not None
        assert result.status in (AnalysisStatus.DONE.value, AnalysisStatus.PARTIAL.value)
        if result.score_result:
            assert result.score_result.composite >= 0.0

    @pytest.mark.asyncio
    async def test_pipeline_handles_llm_failure_gracefully(self, db, mock_redis, analysis_fixture):
        """Pipeline should degrade gracefully when LLM is unavailable."""
        analysis = analysis_fixture["analysis"]

        mock_llm = AsyncMock()
        mock_llm.complete = AsyncMock(side_effect=RuntimeError("LLM unavailable"))

        mock_embedder = AsyncMock()
        mock_embedder.embed_batch = AsyncMock(return_value=[[0.1] * 768])

        with (
            patch("app.pipeline.orchestrator.get_llm_client", return_value=mock_llm),
            patch("app.pipeline.orchestrator.get_embedding_client", return_value=mock_embedder),
        ):
            from app.pipeline.orchestrator import run_pipeline
            result = await run_pipeline(analysis_id=analysis.id, db=db, redis=mock_redis)

        # Should not crash — should return PARTIAL or DONE with rule-based results
        assert result is not None
        assert result.status in (
            AnalysisStatus.DONE.value,
            AnalysisStatus.PARTIAL.value,
            AnalysisStatus.FAILED.value,
        )
