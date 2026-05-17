"""PDF text extractor — primary pdfplumber path with pymupdf fallback."""

from __future__ import annotations

import io
from dataclasses import dataclass, field

import structlog

log = structlog.get_logger(__name__)


@dataclass
class PageResult:
    page_num: int
    text: str
    success: bool
    error: str | None = None


@dataclass
class PDFExtractResult:
    text: str
    pages: list[PageResult] = field(default_factory=list)
    method_used: str = "pdfplumber"
    failed_pages: list[int] = field(default_factory=list)
    char_count: int = 0
    is_empty: bool = False


def extract_pdf(file_bytes: bytes) -> PDFExtractResult:
    """Extract text from PDF bytes.

    Primary path: pdfplumber (preserves reading order better).
    Fallback: pymupdf character-level extraction.
    """
    result = _extract_with_pdfplumber(file_bytes)

    if result.is_empty or result.char_count < 100:
        log.info("pdf_pdfplumber_insufficient", chars=result.char_count, trying="pymupdf")
        fallback = _extract_with_pymupdf(file_bytes)
        if fallback.char_count > result.char_count:
            return fallback

    return result


def _extract_with_pdfplumber(file_bytes: bytes) -> PDFExtractResult:
    """Extract text via pdfplumber preserving reading order."""
    try:
        import pdfplumber
    except ImportError:
        log.warning("pdfplumber_not_installed")
        return PDFExtractResult(text="", is_empty=True, method_used="pdfplumber")

    pages: list[PageResult] = []
    all_text_parts: list[str] = []
    failed: list[int] = []

    try:
        with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
            for i, page in enumerate(pdf.pages):
                try:
                    # layout=True preserves visual spacing; wider tolerances
                    # prevent words from being glued together
                    text = page.extract_text(
                        layout=True,
                        x_tolerance=5,
                        y_tolerance=5,
                    ) or ""
                    # layout mode adds lots of internal spaces; normalize them
                    # but keep line breaks intact
                    import re
                    text = re.sub(r"[ \t]{2,}", "  ", text)  # collapse huge gaps
                    pages.append(PageResult(page_num=i + 1, text=text, success=True))
                    if text.strip():
                        all_text_parts.append(text)
                except Exception as exc:
                    log.warning("pdf_page_extract_failed", page=i + 1, error=str(exc))
                    pages.append(PageResult(page_num=i + 1, text="", success=False, error=str(exc)))
                    failed.append(i + 1)
    except Exception as exc:
        log.error("pdfplumber_open_failed", error=str(exc))
        return PDFExtractResult(text="", is_empty=True, method_used="pdfplumber")

    full_text = "\n\n".join(all_text_parts)
    return PDFExtractResult(
        text=full_text,
        pages=pages,
        method_used="pdfplumber",
        failed_pages=failed,
        char_count=len(full_text),
        is_empty=len(full_text.strip()) == 0,
    )


def _extract_with_pymupdf(file_bytes: bytes) -> PDFExtractResult:
    """Extract text via pymupdf (fitz) — character-level, better for complex layouts."""
    try:
        import fitz  # pymupdf
    except ImportError:
        log.warning("pymupdf_not_installed")
        return PDFExtractResult(text="", is_empty=True, method_used="pymupdf")

    pages: list[PageResult] = []
    all_text_parts: list[str] = []
    failed: list[int] = []

    try:
        doc = fitz.open(stream=file_bytes, filetype="pdf")
        for i, page in enumerate(doc):
            try:
                text = page.get_text("text")  # type: ignore[attr-defined]
                pages.append(PageResult(page_num=i + 1, text=text, success=True))
                if text.strip():
                    all_text_parts.append(text)
            except Exception as exc:
                log.warning("pymupdf_page_failed", page=i + 1, error=str(exc))
                pages.append(PageResult(page_num=i + 1, text="", success=False, error=str(exc)))
                failed.append(i + 1)
        doc.close()
    except Exception as exc:
        log.error("pymupdf_open_failed", error=str(exc))
        return PDFExtractResult(text="", is_empty=True, method_used="pymupdf")

    full_text = "\n\n".join(all_text_parts)
    return PDFExtractResult(
        text=full_text,
        pages=pages,
        method_used="pymupdf",
        failed_pages=failed,
        char_count=len(full_text),
        is_empty=len(full_text.strip()) == 0,
    )
