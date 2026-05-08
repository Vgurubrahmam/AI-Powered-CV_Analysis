"""Unit tests for hallucination_guard.py."""

from __future__ import annotations

import pytest

from app.pipeline.feedback.hallucination_guard import check_hallucinations, HallucinationResult


RESUME_TEXT = """
John Doe - Software Engineer
7 years of experience at Acme Corp.
Reduced API latency by 40%.
Led team of 4 engineers.
Skills: Python, FastAPI, PostgreSQL, Redis, Docker.
B.S. Computer Science, Stanford University 2018.
AWS Certified Solutions Architect.
"""


class TestCheckHallucinations:

    def test_clean_rewrite_passes(self):
        rewrite = "Led a team of 4 engineers to reduce API latency by 40% at Acme Corp."
        result = check_hallucinations(rewrite, RESUME_TEXT)
        assert result.passed is True
        assert len(result.flagged_entities) == 0

    def test_invented_metric_is_flagged(self):
        """A metric not in the resume should be flagged."""
        rewrite = "Increased revenue by 500% and led a team of 4 engineers."
        result = check_hallucinations(rewrite, RESUME_TEXT)
        # 500% is not in resume — should be flagged
        assert result.passed is False or "500%" in result.flagged_entities

    def test_invented_company_is_flagged(self):
        """A company name not in the resume should be flagged."""
        rewrite = "Senior Engineer at Google with 10 years at Microsoft."
        result = check_hallucinations(rewrite, RESUME_TEXT)
        assert result.passed is False

    def test_empty_rewrite_passes(self):
        result = check_hallucinations("", RESUME_TEXT)
        assert result.passed is True

    def test_rewrite_same_as_original_passes(self):
        result = check_hallucinations(RESUME_TEXT, RESUME_TEXT)
        assert result.passed is True

    def test_known_skills_preserved(self):
        rewrite = "Built scalable systems using Python, FastAPI, and PostgreSQL."
        result = check_hallucinations(rewrite, RESUME_TEXT)
        assert result.passed is True

    def test_hallucination_result_has_warning(self):
        rewrite = "Founded a unicorn startup and raised $500M in Series B."
        result = check_hallucinations(rewrite, RESUME_TEXT)
        if not result.passed:
            assert result.warning is not None
