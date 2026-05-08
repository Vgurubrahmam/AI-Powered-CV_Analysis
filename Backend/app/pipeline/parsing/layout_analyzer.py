"""Layout analyzer — bounding-box column detection and multi-column reading order fix.

Uses pdfplumber word-level bbox data to detect two-column layouts and reconstruct
a correct linear reading order (left column top-to-bottom, then right column).
Falls back gracefully when bbox data is unavailable.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import structlog

log = structlog.get_logger(__name__)

# Fraction of page width: if most words have x-coords < LEFT_COL_MAX_FRAC
# OR > RIGHT_COL_MIN_FRAC, we suspect a two-column layout.
LEFT_COL_MAX_FRAC = 0.48
RIGHT_COL_MIN_FRAC = 0.52


@dataclass
class LayoutAnalysisResult:
    """Result of layout analysis."""

    is_multicolumn: bool
    num_columns: int
    reading_order_text: str            # Reconstructed linear text
    raw_words: list[dict] = field(default_factory=list)
    confidence: float = 1.0


def analyze_layout(pages_data: list[dict[str, Any]]) -> LayoutAnalysisResult:
    """Detect multi-column layout and reconstruct correct reading order.

    Args:
        pages_data: List of page dicts from pdfplumber, each with:
            - ``words``: list of word dicts (text, x0, y0, x1, y1)
            - ``width``: page width
            - ``text``: fallback raw text

    Returns:
        LayoutAnalysisResult with reconstructed text and column metadata.
    """
    if not pages_data:
        return LayoutAnalysisResult(
            is_multicolumn=False,
            num_columns=1,
            reading_order_text="",
        )

    all_text_parts: list[str] = []
    is_multicolumn_overall = False
    total_confidence = 0.0

    for page in pages_data:
        words = page.get("words", [])
        page_width = page.get("width", 612.0)  # default US letter

        if not words:
            # Fall back to raw text
            all_text_parts.append(page.get("text", ""))
            total_confidence += 0.5
            continue

        page_text, is_mc, conf = _reconstruct_page_text(words, page_width)
        all_text_parts.append(page_text)

        if is_mc:
            is_multicolumn_overall = True
        total_confidence += conf

    avg_confidence = total_confidence / len(pages_data) if pages_data else 1.0
    num_cols = 2 if is_multicolumn_overall else 1

    log.debug(
        "layout_analysis_complete",
        multicolumn=is_multicolumn_overall,
        num_cols=num_cols,
        confidence=round(avg_confidence, 3),
        pages=len(pages_data),
    )

    return LayoutAnalysisResult(
        is_multicolumn=is_multicolumn_overall,
        num_columns=num_cols,
        reading_order_text="\n\n".join(p for p in all_text_parts if p),
        confidence=round(avg_confidence, 3),
    )


def _reconstruct_page_text(
    words: list[dict],
    page_width: float,
) -> tuple[str, bool, float]:
    """Reconstruct reading-order text for a single page.

    Returns:
        (reconstructed_text, is_multicolumn, confidence)
    """
    if not words:
        return "", False, 0.5

    mid = page_width * 0.5

    left_words = [w for w in words if _word_x_center(w) < mid * 1.05]
    right_words = [w for w in words if _word_x_center(w) >= mid * 0.95]

    # Overlap detection: if many words appear in both buckets → single column
    overlap = set(_word_key(w) for w in left_words) & set(_word_key(w) for w in right_words)
    overlap_ratio = len(overlap) / max(len(words), 1)

    is_multicolumn = False
    confidence = 1.0

    if overlap_ratio < 0.3 and len(right_words) > 5 and len(left_words) > 5:
        # Check if right words are truly offset (not just near the margin)
        right_x_centers = [_word_x_center(w) for w in right_words]
        left_x_centers = [_word_x_center(w) for w in left_words]
        avg_right_x = sum(right_x_centers) / len(right_x_centers)
        avg_left_x = sum(left_x_centers) / len(left_x_centers)

        if (avg_right_x - avg_left_x) > page_width * 0.25:
            is_multicolumn = True
            confidence = 0.85

    if is_multicolumn:
        # Sort each column by y (top to bottom), then left→right within same y band
        left_sorted = sorted(left_words, key=lambda w: (round(w.get("y0", 0) / 5) * 5, w.get("x0", 0)))
        right_sorted = sorted(right_words, key=lambda w: (round(w.get("y0", 0) / 5) * 5, w.get("x0", 0)))

        left_text = _words_to_text(left_sorted)
        right_text = _words_to_text(right_sorted)
        return f"{left_text}\n{right_text}", True, confidence

    # Single column: sort top→bottom, left→right
    sorted_words = sorted(words, key=lambda w: (round(w.get("y0", 0) / 5) * 5, w.get("x0", 0)))
    return _words_to_text(sorted_words), False, 1.0


def _word_x_center(word: dict) -> float:
    x0 = word.get("x0", 0.0)
    x1 = word.get("x1", x0)
    return (x0 + x1) / 2.0


def _word_key(word: dict) -> str:
    return f"{word.get('text', '')}_{word.get('x0', 0):.0f}_{word.get('y0', 0):.0f}"


def _words_to_text(words: list[dict]) -> str:
    """Convert sorted word list to readable text, inserting newlines on y-jumps."""
    if not words:
        return ""

    lines: list[list[str]] = []
    current_line: list[str] = []
    prev_y = words[0].get("y0", 0.0)

    for word in words:
        y = word.get("y0", 0.0)
        text = word.get("text", "").strip()
        if not text:
            continue

        if abs(y - prev_y) > 8:  # new line threshold (pts)
            if current_line:
                lines.append(current_line)
            current_line = [text]
        else:
            current_line.append(text)
        prev_y = y

    if current_line:
        lines.append(current_line)

    return "\n".join(" ".join(line) for line in lines)
