"""Unit tests for score_engine.py — compute_composite_score."""

from __future__ import annotations

import pytest

from app.pipeline.scoring.score_engine import SubScores, compute_composite_score


class TestCompositeScore:

    def test_all_scores_present(self):
        subs = SubScores(
            keyword=80.0,
            semantic=70.0,
            skill_depth=60.0,
            experience=75.0,
            impact=65.0,
            education=55.0,
        )
        result = compute_composite_score(subs)
        assert 0.0 <= result.composite <= 100.0

    def test_composite_within_bounds(self):
        """Composite must always be [0, 100]."""
        for kw in [0.0, 50.0, 100.0]:
            subs = SubScores(keyword=kw, semantic=kw)
            result = compute_composite_score(subs)
            assert 0.0 <= result.composite <= 100.0

    def test_perfect_score(self):
        subs = SubScores(
            keyword=100.0,
            semantic=100.0,
            skill_depth=100.0,
            experience=100.0,
            impact=100.0,
            education=100.0,
        )
        result = compute_composite_score(subs)
        assert result.composite == pytest.approx(100.0, abs=0.1)

    def test_zero_score(self):
        subs = SubScores(
            keyword=0.0,
            semantic=0.0,
            skill_depth=0.0,
            experience=0.0,
            impact=0.0,
            education=0.0,
        )
        result = compute_composite_score(subs)
        assert result.composite == pytest.approx(0.0, abs=0.1)

    def test_missing_optional_scores_dont_crash(self):
        """Optional sub-scores (impact, education) can be None."""
        subs = SubScores(keyword=70.0, semantic=60.0)
        result = compute_composite_score(subs)
        assert result.composite > 0

    def test_confidence_propagation(self):
        """Lower parse confidence should lower composite score."""
        subs = SubScores(keyword=80.0, semantic=80.0)
        result_high = compute_composite_score(subs, parse_confidence=1.0)
        result_low = compute_composite_score(subs, parse_confidence=0.5)
        assert result_high.composite >= result_low.composite

    def test_sub_scores_preserved(self):
        subs = SubScores(keyword=77.5, semantic=62.3)
        result = compute_composite_score(subs)
        assert result.sub_scores.keyword == pytest.approx(77.5)
        assert result.sub_scores.semantic == pytest.approx(62.3)
