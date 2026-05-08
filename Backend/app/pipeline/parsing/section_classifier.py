"""Section classifier — detect resume section headers and map to canonical names."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional

from app.core.constants import ResumeSection

# ── Regex patterns for common section headers ────────────────────────────────
_SECTION_PATTERNS: list[tuple[ResumeSection, list[str]]] = [
    (ResumeSection.SUMMARY, [
        r"^(professional\s+)?summary$",
        r"^(executive\s+)?summary$",
        r"^profile$",
        r"^about\s+(me|myself)$",
        r"^overview$",
        r"^career\s+profile$",
    ]),
    (ResumeSection.OBJECTIVE, [
        r"^objective$",
        r"^career\s+objective$",
        r"^professional\s+objective$",
    ]),
    (ResumeSection.EXPERIENCE, [
        r"^(work|professional|employment|job|career)\s+experience$",
        r"^(work|professional)\s+history$",
        r"^experience$",
        r"^positions?\s+(held|of\s+responsibility)$",
        r"^relevant\s+experience$",
    ]),
    (ResumeSection.EDUCATION, [
        r"^education(al\s+(background|qualifications?))?$",
        r"^academic\s+(background|qualifications?)$",
        r"^degrees?$",
        r"^qualifications?$",
    ]),
    (ResumeSection.SKILLS, [
        r"^(technical\s+|core\s+|key\s+)?skills?$",
        r"^competenc(y|ies)$",
        r"^expertise$",
        r"^technologies$",
        r"^(technical\s+)?proficiencies$",
        r"^tools?\s+(and\s+technologies)?$",
    ]),
    (ResumeSection.CERTIFICATIONS, [
        r"^certifications?$",
        r"^licenses?\s+(and\s+certifications?)?$",
        r"^credentials?$",
        r"^professional\s+development$",
        r"^training(\s+and\s+certifications?)?$",
    ]),
    (ResumeSection.PROJECTS, [
        r"^(personal\s+|key\s+|notable\s+)?projects?$",
        r"^portfolio$",
        r"^open\s+source",
    ]),
    (ResumeSection.AWARDS, [
        r"^awards?\s+(and\s+recognitions?)?$",
        r"^honors?\s+(and\s+awards?)?$",
        r"^achievements?$",
        r"^accomplishments?$",
    ]),
    (ResumeSection.PUBLICATIONS, [
        r"^publications?$",
        r"^research$",
        r"^papers?$",
    ]),
    (ResumeSection.VOLUNTEERING, [
        r"^volunteer(ing|s?)?$",
        r"^community\s+(service|involvement)$",
        r"^civic\s+activities$",
    ]),
    (ResumeSection.CONTACT, [
        r"^contact(\s+(information|details?))?$",
        r"^personal\s+(information|details?)$",
    ]),
]

_COMPILED_PATTERNS: list[tuple[ResumeSection, list[re.Pattern]]] = [
    (section, [re.compile(p, re.IGNORECASE) for p in patterns])
    for section, patterns in _SECTION_PATTERNS
]


@dataclass
class TextBlock:
    text: str
    is_header: bool = False
    section: ResumeSection = ResumeSection.UNKNOWN
    line_num: int = 0


def classify_section(line: str) -> Optional[ResumeSection]:
    """Classify a text line as a section header. Returns None if not a header."""
    cleaned = line.strip().lower()
    if not cleaned or len(cleaned) > 60:  # headers are short
        return None

    for section, patterns in _COMPILED_PATTERNS:
        for pattern in patterns:
            if pattern.match(cleaned):
                return section

    return None


def is_likely_header(line: str) -> bool:
    """Heuristically determine if a line looks like a section header."""
    stripped = line.strip()
    if not stripped:
        return False
    # Common header signals: ALL CAPS, short length, ends without period
    if stripped.isupper() and len(stripped) < 50:
        return True
    if re.match(r"^[A-Z][A-Za-z\s&/-]+$", stripped) and len(stripped) < 50:
        return True
    return False


def segment_resume(text: str) -> dict[ResumeSection, str]:
    """Split resume text into sections by detecting section headers.

    Returns dict mapping ResumeSection → section text content.
    """
    lines = text.split("\n")
    sections: dict[ResumeSection, list[str]] = {}
    current_section = ResumeSection.CONTACT  # default first section
    buffer: list[str] = []

    for line in lines:
        section = classify_section(line)
        if section is None and is_likely_header(line):
            # Try stripping punctuation and re-classifying
            section = classify_section(re.sub(r"[:\-_=*•]+", "", line))

        if section is not None:
            # Save buffered content to current section
            if buffer:
                existing = sections.get(current_section, [])
                existing.extend(buffer)
                sections[current_section] = existing
                buffer = []
            current_section = section
        else:
            buffer.append(line)

    # Flush remaining buffer
    if buffer:
        existing = sections.get(current_section, [])
        existing.extend(buffer)
        sections[current_section] = existing

    return {section: "\n".join(lines).strip() for section, lines in sections.items()}
