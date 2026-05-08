"""Unit tests for keyword_engine.py — match_keywords function."""

from __future__ import annotations

import pytest

from app.pipeline.matching.keyword_engine import match_keywords


class TestMatchKeywords:
    """Tests for keyword matching logic."""

    def test_exact_required_skill_match(self):
        resume_skills = ["python", "fastapi", "postgresql", "redis", "docker"]
        jd_required = ["python", "fastapi", "postgresql"]
        jd_preferred = ["redis", "kubernetes"]

        result = match_keywords(resume_skills, jd_required, jd_preferred)

        assert result.matched_required == ["python", "fastapi", "postgresql"]
        assert result.missing_required == []
        assert "redis" in result.matched_preferred
        assert result.match_rate == pytest.approx(1.0, abs=0.01)

    def test_partial_required_match(self):
        resume_skills = ["python", "fastapi"]
        jd_required = ["python", "fastapi", "kubernetes", "terraform"]
        jd_preferred = []

        result = match_keywords(resume_skills, jd_required, jd_preferred)

        assert "kubernetes" in result.missing_required
        assert "terraform" in result.missing_required
        assert result.match_rate == pytest.approx(0.5, abs=0.01)

    def test_case_insensitive_matching(self):
        resume_skills = ["Python", "FastAPI", "PostgreSQL"]
        jd_required = ["python", "fastapi", "postgresql"]

        result = match_keywords(resume_skills, jd_required, [])
        assert result.missing_required == []

    def test_no_match(self):
        resume_skills = ["javascript", "react", "css"]
        jd_required = ["python", "java", "kubernetes"]

        result = match_keywords(resume_skills, jd_required, [])
        assert result.match_rate == pytest.approx(0.0, abs=0.01)
        assert len(result.missing_required) == 3

    def test_empty_inputs(self):
        result = match_keywords([], [], [])
        assert result.match_rate == 0.0
        assert result.matched_required == []

    def test_preferred_only_no_impact_on_match_rate(self):
        """Preferred skills should not inflate required match_rate."""
        resume_skills = ["python", "tensorflow", "pandas"]
        jd_required = ["python"]
        jd_preferred = ["tensorflow", "pytorch"]

        result = match_keywords(resume_skills, jd_required, jd_preferred)
        assert result.match_rate == pytest.approx(1.0, abs=0.01)
        assert "tensorflow" in result.matched_preferred

    def test_synonym_expansion(self):
        """Should match 'k8s' against 'kubernetes' via synonym expansion."""
        resume_skills = ["k8s", "python"]
        jd_required = ["kubernetes", "python"]

        result = match_keywords(resume_skills, jd_required, [])
        # k8s should match kubernetes
        assert "kubernetes" not in result.missing_required
