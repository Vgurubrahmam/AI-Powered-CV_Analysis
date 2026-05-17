"""Section classifier — detect resume section headers and map to canonical names.

Uses a two-pass approach:
  1. Exact regex matching against known patterns
  2. Fuzzy keyword matching for decorated/non-standard headers
"""

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
        r"^profile(\s+summary)?$",
        r"^about\s+(me|myself)$",
        r"^overview$",
        r"^career\s+profile$",
        r"^personal\s+statement$",
    ]),
    (ResumeSection.OBJECTIVE, [
        r"^(career\s+)?objective$",
        r"^professional\s+objective$",
        r"^goal$",
    ]),
    (ResumeSection.EXPERIENCE, [
        r"^(work|professional|employment|job|career)\s+(experience|history)$",
        r"^experience$",
        r"^positions?\s+(held|of\s+responsibility)$",
        r"^relevant\s+experience$",
        r"^internship(s)?(\s+experience)?$",
        r"^work\s+experience\s+and\s+projects?$",
        r"^professional\s+experience\s+and\s+projects?$",
    ]),
    (ResumeSection.EDUCATION, [
        r"^education(al)?(\s+(background|qualifications?|details?))?$",
        r"^academic(\s+(background|qualifications?|record))?$",
        r"^degrees?$",
        r"^qualifications?$",
        r"^education\s+(and|&)\s+(certifications?|training)$",
    ]),
    (ResumeSection.SKILLS, [
        r"^(technical\s+|core\s+|key\s+|relevant\s+|professional\s+)?skills?(\s+(and\s+)?(tools|technologies|competencies|abilities|expertise))?$",
        r"^competenc(y|ies)$",
        r"^expertise$",
        r"^technologies$",
        r"^(technical\s+)?proficienc(y|ies)$",
        r"^tools?\s+(and\s+(technologies|skills?))?$",
        r"^areas?\s+of\s+(expertise|knowledge)$",
        r"^skill\s+set$",
        r"^technical\s+stack$",
        r"^tech\s+stack$",
        r"^programming(\s+languages)?$",
        r"^languages?\s+(and\s+)?(frameworks?|tools?|technologies)?$",
    ]),
    (ResumeSection.CERTIFICATIONS, [
        r"^certifications?(\s+(and\s+)?(licenses?|training|courses?))?$",
        r"^licenses?\s+(and\s+certifications?)?$",
        r"^credentials?$",
        r"^professional\s+development$",
        r"^training(\s+(and\s+certifications?|programs?))?$",
        r"^courses?(\s+and\s+certifications?)?$",
    ]),
    (ResumeSection.PROJECTS, [
        r"^(personal\s+|key\s+|notable\s+|academic\s+|side\s+)?projects?$",
        r"^portfolio$",
        r"^open\s+source",
        r"^project\s+(work|experience|highlights?)$",
    ]),
    (ResumeSection.AWARDS, [
        r"^awards?\s+(and\s+(recognitions?|honours?))?$",
        r"^honors?\s+(and\s+awards?)?$",
        r"^achievements?$",
        r"^accomplishments?$",
        r"^extracurricular(\s+activities)?$",
        r"^activities(\s+and\s+achievements?)?$",
    ]),
    (ResumeSection.PUBLICATIONS, [
        r"^publications?$",
        r"^research(\s+papers?)?$",
        r"^papers?$",
    ]),
    (ResumeSection.VOLUNTEERING, [
        r"^volunteer(ing|s?)?(\s+(experience|work))?$",
        r"^community\s+(service|involvement)$",
        r"^civic\s+activities$",
        r"^social\s+(service|work)$",
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

# ── Keyword fallback for fuzzy matching ──────────────────────────────────────
# If regex doesn't match, check if the line *contains* any of these keywords
_KEYWORD_FALLBACK: list[tuple[ResumeSection, list[str]]] = [
    (ResumeSection.EXPERIENCE, ["experience", "employment", "work history", "internship"]),
    (ResumeSection.EDUCATION, ["education", "academic", "qualification", "degree"]),
    (ResumeSection.SKILLS, ["skills", "technologies", "expertise", "proficiency", "competenc",
                            "tech stack", "programming"]),
    (ResumeSection.CERTIFICATIONS, ["certification", "certificate", "credential", "training"]),
    (ResumeSection.PROJECTS, ["project", "portfolio"]),
    (ResumeSection.SUMMARY, ["summary", "profile", "overview", "about me"]),
    (ResumeSection.AWARDS, ["award", "achievement", "accomplishment", "honor"]),
    (ResumeSection.PUBLICATIONS, ["publication", "research"]),
    (ResumeSection.VOLUNTEERING, ["volunteer", "community"]),
]


@dataclass
class TextBlock:
    text: str
    is_header: bool = False
    section: ResumeSection = ResumeSection.UNKNOWN
    line_num: int = 0


def _clean_header(line: str) -> str:
    """Strip decorations from a potential header line."""
    cleaned = line.strip()
    # Remove common decorations: dashes, equals, underscores, stars, bullets, pipes, colons
    cleaned = re.sub(r"^[\s\-=_*•|:►▶→#~]+", "", cleaned)
    cleaned = re.sub(r"[\s\-=_*•|:►▶→#~]+$", "", cleaned)
    # Remove markdown-style formatting: **bold**, __underline__
    cleaned = re.sub(r"\*{1,2}|_{1,2}", "", cleaned)
    # Remove numbering: "1.", "I.", "A."
    cleaned = re.sub(r"^\d+[\.\)]\s*", "", cleaned)
    cleaned = re.sub(r"^[IVXLCDM]+[\.\)]\s*", "", cleaned)
    return cleaned.strip()


def classify_section(line: str) -> Optional[ResumeSection]:
    """Classify a text line as a section header. Returns None if not a header."""
    cleaned = _clean_header(line).lower()
    if not cleaned or len(cleaned) > 80:  # headers are short
        return None

    # Pass 1: exact regex match
    for section, patterns in _COMPILED_PATTERNS:
        for pattern in patterns:
            if pattern.match(cleaned):
                return section

    # Pass 2: keyword fallback (only if line looks like a header)
    if len(cleaned) < 50 and is_likely_header(line):
        for section, keywords in _KEYWORD_FALLBACK:
            for kw in keywords:
                if kw in cleaned:
                    return section

    return None


def is_likely_header(line: str) -> bool:
    """Heuristically determine if a line looks like a section header."""
    stripped = line.strip()
    if not stripped:
        return False
    cleaned = _clean_header(stripped)
    if not cleaned:
        return False

    # ALL CAPS and short
    if cleaned.isupper() and 2 < len(cleaned) < 60:
        return True
    # Title Case and short (e.g., "Work Experience")
    if re.match(r"^[A-Z][A-Za-z\s&/,\-]+$", cleaned) and len(cleaned) < 60:
        return True
    # Decorated lines: "--- EXPERIENCE ---", "=== SKILLS ==="
    if re.match(r"^[\-=_*~]+\s*.+\s*[\-=_*~]+$", stripped):
        return True
    # Bold/markdown headers: "**Experience**"
    if re.match(r"^\*{1,2}[A-Za-z\s&/]+\*{1,2}$", stripped):
        return True
    # Ends with colon: "Skills:"
    if re.match(r"^[A-Za-z\s&/]+:$", stripped) and len(stripped) < 40:
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
