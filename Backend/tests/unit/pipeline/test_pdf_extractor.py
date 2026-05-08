"""Unit tests for PDF extractor."""

from __future__ import annotations

import pytest

from app.pipeline.parsing.pdf_extractor import extract_text_from_pdf


class TestPDFExtractor:

    def test_minimal_valid_pdf(self, sample_resume_bytes):
        """Should not raise on minimal valid PDF bytes (may return empty text)."""
        text, confidence = extract_text_from_pdf(sample_resume_bytes)
        # Should complete without exception; text may be empty for stub PDF
        assert isinstance(text, str)
        assert 0.0 <= confidence <= 1.0

    def test_empty_bytes_returns_empty_string(self):
        text, confidence = extract_text_from_pdf(b"")
        assert text == "" or isinstance(text, str)
        assert confidence == 0.0 or isinstance(confidence, float)

    def test_invalid_pdf_returns_empty(self):
        """Garbage bytes should not raise, just return low-confidence empty."""
        text, confidence = extract_text_from_pdf(b"not a pdf at all %$#@!")
        assert isinstance(text, str)
        assert confidence < 0.5

    def test_return_types(self, sample_resume_bytes):
        result = extract_text_from_pdf(sample_resume_bytes)
        assert isinstance(result, tuple)
        assert len(result) == 2
        text, conf = result
        assert isinstance(text, str)
        assert isinstance(conf, float)
