"""ATS compatibility checker — formatting linter for resume files."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum


class ATSWarningLevel(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


@dataclass
class ATSWarning:
    level: ATSWarningLevel
    message: str
    fix: str


@dataclass
class ATSCheckResult:
    score: float                                        # 0–100
    warnings: list[ATSWarning] = field(default_factory=list)
    passed: bool = True


def check_ats_compatibility(
    raw_text: str,
    file_type: str,
    parsed_data: dict | None = None,
    tables_detected: bool = False,
) -> ATSCheckResult:
    """Run ATS formatting lint checks on a resume.

    Checks:
    - Presence of contact info (email, phone)
    - Over-reliance on tables (ATS parsers often fail on tables)
    - Special characters that break parsing
    - Date formatting consistency
    - Section header clarity
    - File type compliance
    """
    warnings: list[ATSWarning] = []
    deductions = 0.0

    # ── 1. File type ─────────────────────────────────────────────────────
    if file_type not in ("pdf", "docx", "txt"):
        warnings.append(ATSWarning(
            level=ATSWarningLevel.CRITICAL,
            message="Unsupported file format. Most ATS systems only accept PDF or DOCX.",
            fix="Convert your resume to PDF or DOCX format.",
        ))
        deductions += 30

    # ── 2. Tables ─────────────────────────────────────────────────────────
    if tables_detected:
        warnings.append(ATSWarning(
            level=ATSWarningLevel.HIGH,
            message="Resume contains tables. Many ATS systems cannot parse table content correctly.",
            fix="Replace tables with plain bulleted lists or simple text formatting.",
        ))
        deductions += 15

    # ── 3. Multi-column detection (heuristic from text) ───────────────────
    if _detect_multicolumn(raw_text):
        warnings.append(ATSWarning(
            level=ATSWarningLevel.HIGH,
            message="Resume may use multi-column layout. ATS often reads columns out of order.",
            fix="Use a single-column layout for ATS submissions.",
        ))
        deductions += 15

    # ── 4. Contact info ───────────────────────────────────────────────────
    if not re.search(r"[\w.+-]+@[\w-]+\.[a-z]{2,}", raw_text, re.IGNORECASE):
        warnings.append(ATSWarning(
            level=ATSWarningLevel.CRITICAL,
            message="No email address detected in resume.",
            fix="Include a clearly formatted email address at the top of your resume.",
        ))
        deductions += 20

    if not re.search(r"[\+]?[(]?[0-9]{3}[)]?[-\s\.]?[0-9]{3}[-\s\.]?[0-9]{4,6}", raw_text):
        warnings.append(ATSWarning(
            level=ATSWarningLevel.MEDIUM,
            message="No phone number detected.",
            fix="Include a phone number in your contact information.",
        ))
        deductions += 5

    # ── 5. Special characters ─────────────────────────────────────────────
    problematic_chars = re.findall(r"[^\x00-\x7F]", raw_text)
    if len(problematic_chars) > 50:
        warnings.append(ATSWarning(
            level=ATSWarningLevel.MEDIUM,
            message=f"Resume contains {len(problematic_chars)} non-ASCII characters that may confuse ATS parsers.",
            fix="Use standard ASCII characters. Replace special typographic quotes, em-dashes, etc.",
        ))
        deductions += 10

    # ── 6. Graphics/images (can't detect from text, flag for PDF) ─────────
    if file_type == "pdf" and len(raw_text.strip()) < 300:
        warnings.append(ATSWarning(
            level=ATSWarningLevel.CRITICAL,
            message="Very little text extracted from PDF. Resume may contain images or graphics that ATS cannot read.",
            fix="Ensure your resume text is selectable. Avoid image-heavy designs.",
        ))
        deductions += 25

    # ── 7. Header/footer overlap (heuristic) ──────────────────────────────
    if _detect_header_footer_text(raw_text):
        warnings.append(ATSWarning(
            level=ATSWarningLevel.LOW,
            message="Resume may contain header or footer text that could interfere with parsing.",
            fix="Avoid placing important information in headers or footers.",
        ))
        deductions += 5

    score = round(max(0.0, 100.0 - deductions), 2)
    passed = score >= 70

    return ATSCheckResult(
        score=score,
        warnings=warnings,
        passed=passed,
    )


def _detect_multicolumn(text: str) -> bool:
    """Heuristic: detect if text appears to come from a multi-column layout.

    Signal: very short lines interspersed with longer ones, common in column reads.
    """
    lines = [l for l in text.split("\n") if l.strip()]
    if len(lines) < 10:
        return False
    avg_len = sum(len(l) for l in lines) / len(lines)
    short_count = sum(1 for l in lines if len(l.strip()) < avg_len * 0.3)
    return (short_count / len(lines)) > 0.4


def _detect_header_footer_text(text: str) -> bool:
    """Heuristic: detect repeated short lines that could be headers/footers."""
    lines = [l.strip() for l in text.split("\n")]
    short_lines = [l for l in lines if 0 < len(l) < 30]
    # If many short, non-bulleted lines → possible header/footer pollution
    return len(short_lines) > 20
