"""Field extractor — contact info, dates, job titles, education from raw text."""

from __future__ import annotations

import re
from typing import Optional

from app.utils.text_utils import extract_emails, extract_phones, extract_urls


# ── LinkedIn / GitHub URL patterns ──────────────────────────────────────────
_LINKEDIN_RE = re.compile(r"linkedin\.com/in/[\w\-]+", re.IGNORECASE)
_GITHUB_RE = re.compile(r"github\.com/[\w\-]+", re.IGNORECASE)

# ── Name detection (heuristic: first 3 lines, all caps or title case) ────────
_NAME_RE = re.compile(r"^[A-Z][a-z]+ [A-Z][a-z]+(?:\s+[A-Z][a-z]+)?$", re.MULTILINE)

# ── Date ranges ─────────────────────────────────────────────────────────────
_DATE_RANGE_SECTION_RE = re.compile(
    r"((?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+)?"
    r"(19|20)\d{2}"
    r"\s*[-–—to]+\s*"
    r"((?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s*)?"
    r"((?:19|20)\d{2}|[Pp]resent|[Cc]urrent|[Nn]ow)",
    re.IGNORECASE,
)

# ── Degree patterns ──────────────────────────────────────────────────────────
_DEGREE_RE = re.compile(
    r"\b(B\.?S\.?|B\.?A\.?|M\.?S\.?|M\.?A\.?|M\.?B\.?A\.?|Ph\.?D\.?|B\.?E\.?|"
    r"Bachelor['\s]?s?|Master['\s]?s?|Doctor(?:ate)?|Associate['\s]?s?)\b",
    re.IGNORECASE,
)


def extract_contact(text: str) -> dict:
    """Extract contact fields from resume text."""
    emails = extract_emails(text)
    phones = extract_phones(text)
    urls = extract_urls(text)

    linkedin = next((u for u in urls if "linkedin.com/in/" in u.lower()), None)
    if not linkedin:
        match = _LINKEDIN_RE.search(text)
        linkedin = match.group(0) if match else None

    github = next((u for u in urls if "github.com/" in u.lower()), None)
    if not github:
        match = _GITHUB_RE.search(text)
        github = match.group(0) if match else None

    website = next(
        (u for u in urls if "linkedin" not in u.lower() and "github" not in u.lower()),
        None,
    )

    # Name: try first non-empty line, check it looks like a name
    name = None
    for line in text.split("\n")[:5]:
        stripped = line.strip()
        if stripped and _NAME_RE.match(stripped):
            name = stripped
            break

    return {
        "name": name,
        "email": emails[0] if emails else None,
        "phone": phones[0] if phones else None,
        "linkedin": linkedin,
        "github": github,
        "website": website,
        "location": _extract_location(text),
    }


def _extract_location(text: str) -> Optional[str]:
    """Heuristic location extraction: look for City, State or City, Country patterns."""
    pattern = re.compile(
        r"\b([A-Z][a-zA-Z\s]+),\s*([A-Z]{2}|[A-Z][a-zA-Z]+)\b", re.MULTILINE
    )
    # Look in the first 500 chars (contact block)
    match = pattern.search(text[:500])
    return match.group(0) if match else None


def extract_date_ranges(text: str) -> list[dict]:
    """Extract all date ranges present in the text."""
    ranges = []
    for match in _DATE_RANGE_SECTION_RE.finditer(text):
        full = match.group(0)
        # Split on separator
        parts = re.split(r"[-–—to]+", full, maxsplit=1)
        if len(parts) == 2:
            ranges.append({"start": parts[0].strip(), "end": parts[1].strip(), "raw": full})
    return ranges


def extract_degree_info(education_text: str) -> list[dict]:
    """Extract degree mentions from education section text."""
    degrees = []
    for match in _DEGREE_RE.finditer(education_text):
        # Get surrounding context
        start = max(0, match.start() - 20)
        end = min(len(education_text), match.end() + 100)
        context = education_text[start:end].replace("\n", " ")
        degrees.append({"degree_raw": match.group(0), "context": context})
    return degrees
