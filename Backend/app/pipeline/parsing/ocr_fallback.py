"""OCR fallback — rasterize PDF pages and run Tesseract OCR."""

from __future__ import annotations

import structlog

log = structlog.get_logger(__name__)

OCR_MAX_CONFIDENCE = 0.60  # Always flag OCR-extracted resumes with lower confidence


def extract_via_ocr(file_bytes: bytes) -> tuple[str, float]:
    """Rasterize a PDF and extract text via Tesseract OCR.

    Returns:
        (extracted_text, confidence) — confidence is always ≤ 0.60 for OCR results.
    """
    try:
        from pdf2image import convert_from_bytes
        import pytesseract
    except ImportError as exc:
        log.warning("ocr_dependency_missing", error=str(exc))
        return "", 0.0

    try:
        images = convert_from_bytes(file_bytes, dpi=200)
    except Exception as exc:
        log.error("pdf2image_failed", error=str(exc))
        return "", 0.0

    parts: list[str] = []
    for i, image in enumerate(images):
        try:
            text = pytesseract.image_to_string(image, lang="eng")
            if text.strip():
                parts.append(text)
        except Exception as exc:
            log.warning("tesseract_page_failed", page=i + 1, error=str(exc))

    if not parts:
        return "", 0.0

    full_text = "\n\n".join(parts)
    # Estimate confidence based on coverage
    char_count = len(full_text.strip())
    estimated_confidence = min(OCR_MAX_CONFIDENCE, max(0.30, char_count / 5000))
    log.info("ocr_completed", chars=char_count, pages=len(images), confidence=estimated_confidence)
    return full_text, estimated_confidence
