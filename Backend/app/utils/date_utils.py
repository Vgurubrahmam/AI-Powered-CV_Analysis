"""Date utilities — parsing, duration calculation, years of experience."""

from __future__ import annotations

import re
from datetime import date, datetime
from typing import Optional

from dateutil import parser as dateutil_parser
from dateutil.relativedelta import relativedelta

_PRESENT_WORDS = {"present", "current", "now", "today", "ongoing", "till date"}
_YEAR_RE = re.compile(r"\b(19|20)\d{2}\b")
_DATE_RANGE_RE = re.compile(
    r"((?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.?\s+)?"
    r"(19|20)\d{2}"
    r"\s*[-–—to]+\s*"
    r"((?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.?\s+)?"
    r"((?:19|20)\d{2}|present|current|now)",
    re.IGNORECASE,
)


def parse_date(date_str: str) -> Optional[date]:
    """Attempt to parse a date string into a Python date object."""
    if not date_str or date_str.lower().strip() in _PRESENT_WORDS:
        return None
    try:
        return dateutil_parser.parse(date_str, default=datetime(2000, 1, 1)).date()
    except (ValueError, OverflowError):
        # Try extracting just the year
        match = _YEAR_RE.search(date_str)
        if match:
            year = int(match.group())
            return date(year, 1, 1)
        return None


def is_present(date_str: str) -> bool:
    """Return True if date string represents 'present' / current."""
    return date_str.lower().strip() in _PRESENT_WORDS if date_str else False


def months_between(start: date, end: date) -> int:
    """Calculate the number of months between two dates."""
    delta = relativedelta(end, start)
    return delta.years * 12 + delta.months


def calculate_duration_months(start_str: str, end_str: str) -> int:
    """Calculate duration in months between two date strings.

    Returns 0 if parsing fails.
    """
    start = parse_date(start_str)
    if start is None:
        return 0

    end = date.today() if is_present(end_str) else parse_date(end_str)
    if end is None:
        end = date.today()

    if end < start:
        return 0

    return months_between(start, end)


def extract_years_of_experience(positions: list[dict]) -> float:
    """Calculate total years of experience from a list of positions.

    Each position dict must have 'start_date' and 'end_date' (or 'present').
    Handles overlapping periods by taking the earliest start and latest end.
    """
    if not positions:
        return 0.0

    intervals: list[tuple[date, date]] = []
    for pos in positions:
        start_str = pos.get("start_date") or ""
        end_str = pos.get("end_date") or "present"
        start = parse_date(start_str)
        if not start:
            continue
        end = date.today() if is_present(end_str) else (parse_date(end_str) or date.today())
        if end >= start:
            intervals.append((start, end))

    if not intervals:
        return 0.0

    # Merge overlapping intervals
    intervals.sort(key=lambda x: x[0])
    merged: list[tuple[date, date]] = [intervals[0]]
    for start, end in intervals[1:]:
        prev_start, prev_end = merged[-1]
        if start <= prev_end:
            merged[-1] = (prev_start, max(prev_end, end))
        else:
            merged.append((start, end))

    total_months = sum(months_between(s, e) for s, e in merged)
    return round(total_months / 12, 1)
