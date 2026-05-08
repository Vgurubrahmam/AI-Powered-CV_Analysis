"""Resume parser — main dispatcher routing to PDF/DOCX/TXT extractors."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import structlog

from app.core.constants import FileType, ParseStatus
from app.pipeline.parsing.docx_extractor import extract_docx
from app.pipeline.parsing.field_extractor import extract_contact, extract_date_ranges
from app.pipeline.parsing.ocr_fallback import extract_via_ocr
from app.pipeline.parsing.pdf_extractor import extract_pdf
from app.pipeline.parsing.section_classifier import ResumeSection, segment_resume
from app.utils.text_utils import clean_text, split_bullet_points

log = structlog.get_logger(__name__)

OCR_THRESHOLD = 100  # chars below which we trigger OCR fallback


@dataclass
class ParsedResume:
    """Fully parsed, structured resume."""

    raw_text: str
    contact: dict[str, Any] = field(default_factory=dict)
    summary: str | None = None
    experience: list[dict[str, Any]] = field(default_factory=list)
    education: list[dict[str, Any]] = field(default_factory=list)
    skills: list[str] = field(default_factory=list)
    certifications: list[str] = field(default_factory=list)
    projects: list[str] = field(default_factory=list)
    sections_detected: list[str] = field(default_factory=list)
    # Raw section text keyed by section name — used by skill extractor + orchestrator
    sections_dict: dict[str, str] = field(default_factory=dict)

    # Quality signals
    parse_status: str = ParseStatus.PENDING.value
    parse_confidence: float = 1.0
    parse_method: str = "unknown"
    ocr_used: bool = False


def parse_resume(file_bytes: bytes, file_type: str) -> ParsedResume:
    """Main dispatcher: route to correct extractor, classify sections, extract fields."""
    raw_text = ""
    confidence = 1.0
    ocr_used = False
    method = "unknown"

    # ── Step 1: Extract raw text ─────────────────────────────────────────
    ft = file_type.lower()

    if ft == FileType.PDF.value:
        result = extract_pdf(file_bytes)
        raw_text = result.text
        method = result.method_used
        confidence = _pdf_confidence(result)

        # Try OCR if text is insufficient
        if result.char_count < OCR_THRESHOLD:
            log.info("triggering_ocr_fallback", chars=result.char_count)
            ocr_text, ocr_confidence = extract_via_ocr(file_bytes)
            if len(ocr_text) > len(raw_text):
                raw_text = ocr_text
                confidence = ocr_confidence
                method = "tesseract_ocr"
                ocr_used = True

    elif ft == FileType.DOCX.value:
        result = extract_docx(file_bytes)
        raw_text = result.text
        method = "python-docx"
        confidence = 0.95 if not result.is_empty else 0.0

    elif ft == FileType.TXT.value:
        try:
            raw_text = file_bytes.decode("utf-8", errors="replace")
            method = "plain_text"
            confidence = 1.0
        except Exception as exc:
            log.error("txt_decode_failed", error=str(exc))
            confidence = 0.0
    else:
        log.error("unsupported_file_type", file_type=ft)
        return ParsedResume(
            raw_text="",
            parse_status=ParseStatus.FAILED.value,
            parse_confidence=0.0,
            parse_method="unknown",
        )

    # ── Step 2: Handle empty extraction ─────────────────────────────────
    if not raw_text.strip():
        return ParsedResume(
            raw_text="",
            parse_status=ParseStatus.FAILED.value,
            parse_confidence=0.0,
            parse_method=method,
            ocr_used=ocr_used,
        )

    raw_text = clean_text(raw_text)

    # ── Step 3: Segment into sections ────────────────────────────────────
    sections = segment_resume(raw_text)
    sections_detected = [s.value for s in sections.keys() if s != ResumeSection.UNKNOWN]
    # Build string-keyed sections_dict for downstream consumers
    sections_dict: dict[str, str] = {
        k.value: v for k, v in sections.items() if v
    }

    # ── Step 4: Extract structured fields ────────────────────────────────
    contact = extract_contact(raw_text)
    summary = sections.get(ResumeSection.SUMMARY) or sections.get(ResumeSection.OBJECTIVE)

    # Skills: split by comma/semicolon/newline
    skills_text = sections.get(ResumeSection.SKILLS, "")
    skills = _parse_skill_list(skills_text)

    # Certifications: split by newline
    cert_text = sections.get(ResumeSection.CERTIFICATIONS, "")
    certs = [c.strip() for c in cert_text.split("\n") if c.strip() and len(c.strip()) > 3]

    # Experience: parse into job entries
    exp_text = sections.get(ResumeSection.EXPERIENCE, "")
    experience = _parse_experience_section(exp_text)

    # Education: parse into education entries
    edu_text = sections.get(ResumeSection.EDUCATION, "")
    education = _parse_education_section(edu_text)

    # ── Step 5: Compute parse status ─────────────────────────────────────
    coverage = len(sections_detected) / max(len(_CRITICAL_SECTIONS), 1)
    if confidence < 0.4 or len(raw_text) < 200:
        status = ParseStatus.FAILED.value
    elif coverage < 0.5 or confidence < 0.70:
        status = ParseStatus.PARTIAL.value
        confidence = min(confidence, 0.70)
    else:
        status = ParseStatus.SUCCESS.value

    log.info(
        "resume_parsed",
        method=method,
        confidence=confidence,
        status=status,
        sections=sections_detected,
        char_count=len(raw_text),
    )

    return ParsedResume(
        raw_text=raw_text,
        contact=contact,
        summary=summary,
        experience=experience,
        education=education,
        skills=skills,
        certifications=certs,
        sections_detected=sections_detected,
        sections_dict=sections_dict,
        parse_status=status,
        parse_confidence=confidence,
        parse_method=method,
        ocr_used=ocr_used,
    )


_CRITICAL_SECTIONS = {ResumeSection.EXPERIENCE, ResumeSection.SKILLS, ResumeSection.EDUCATION}


def _pdf_confidence(result) -> float:
    """Estimate parse confidence from PDF extraction result."""
    if result.is_empty:
        return 0.0
    failed_ratio = len(result.failed_pages) / max(len(result.pages), 1)
    base = 1.0 - (failed_ratio * 0.5)
    if result.char_count < 200:
        base *= 0.5
    return round(min(1.0, max(0.0, base)), 3)


def _parse_skill_list(text: str) -> list[str]:
    """Parse skill list from skills section text."""
    import re
    # Split by comma, semicolon, bullet, pipe, newline
    skills = re.split(r"[,;|\n•\-\*]", text)
    return [s.strip() for s in skills if 1 < len(s.strip()) < 60]


def _parse_experience_section(text: str) -> list[dict]:
    """Basic experience parser — returns list of job dicts."""
    if not text.strip():
        return []
    bullets = split_bullet_points(text)
    date_ranges = extract_date_ranges(text)

    # Simple heuristic: one entry per date range
    jobs = []
    for i, dr in enumerate(date_ranges):
        jobs.append(
            {
                "start_date": dr["start"],
                "end_date": dr["end"],
                "bullets": bullets[i * 3: (i + 1) * 3] if bullets else [],
                "raw": dr["raw"],
            }
        )
    return jobs if jobs else [{"raw": text[:500], "bullets": bullets[:10]}]


def _parse_education_section(text: str) -> list[dict]:
    """Basic education parser."""
    from app.pipeline.parsing.field_extractor import extract_degree_info
    if not text.strip():
        return []
    degrees = extract_degree_info(text)
    dates = extract_date_ranges(text)
    entries = []
    for i, deg in enumerate(degrees):
        entry = {"degree_raw": deg["degree_raw"], "context": deg["context"]}
        if i < len(dates):
            entry["start_date"] = dates[i]["start"]
            entry["end_date"] = dates[i]["end"]
        entries.append(entry)
    return entries
