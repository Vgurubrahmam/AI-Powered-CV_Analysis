"""Rewrite engine — constrained LLM bullet/summary rewriting with hallucination guard.

Workflow per rewrite request:
1. Build a strict constrained prompt (must-not-invent rule prominently placed).
2. Call LLM (fast model, low temperature).
3. Run hallucination guard on the output.
4. If guard fails → return original text with a warning (no silent hallucination).
5. If guard passes → return rewritten text.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional

import structlog

from app.pipeline.feedback.hallucination_guard import check_hallucinations

log = structlog.get_logger(__name__)

_REWRITE_PROMPT = """You are an expert resume writer. Rewrite the bullet point below to be more impactful.

STRICT RULES — VIOLATION IS NOT ACCEPTABLE:
1. Do NOT invent new facts, companies, numbers, or achievements not present in the original text.
2. Do NOT add metrics (%, $, numbers) unless they appear in the original text.
3. Use strong action verbs (Led, Built, Reduced, Increased, Designed, etc.).
4. Keep the rewrite to 1-2 sentences maximum.
5. Maintain the same tense as the original.
6. Role context: {role_context}

ORIGINAL BULLET:
{original_text}

IMPROVEMENT GUIDANCE:
{improvement_guidance}

Return ONLY the rewritten bullet. No explanation, no prefix, no quotes."""


@dataclass
class RewriteResult:
    """Result of a bullet/summary rewrite."""

    rewritten_text: str
    original_text: str
    hallucination_check_passed: bool
    flagged_entities: list[str]
    model_used: str
    warning: Optional[str] = None


async def rewrite_bullet(
    original_text: str,
    source_resume_text: str,
    improvement_guidance: str = "",
    role_context: str = "a professional role",
    max_retries: int = 2,
) -> RewriteResult:
    """Rewrite a resume bullet point using LLM with hallucination guard.

    Args:
        original_text: The bullet or sentence to rewrite.
        source_resume_text: Full resume text (used for hallucination validation).
        improvement_guidance: Specific guidance (e.g. "Add more quantification").
        role_context: Job role context for tone calibration.
        max_retries: Number of LLM retry attempts if guard fails.

    Returns:
        RewriteResult. If hallucination guard fails on all retries,
        returns original text with passed=False.
    """
    from app.integrations.llm.client import get_llm_client
    from app.config import settings

    client = get_llm_client()
    model = settings.NVIDIA_DEFAULT_MODEL

    prompt = _REWRITE_PROMPT.format(
        original_text=original_text.strip(),
        improvement_guidance=improvement_guidance or "Make it more impactful and results-oriented.",
        role_context=role_context,
    )

    last_rewrite = original_text
    last_guard = None

    for attempt in range(max_retries):
        try:
            response = await client.complete(
                prompt=prompt,
                model=model,
                max_tokens=300,
                temperature=0.3 + attempt * 0.1,  # slight increase on retry
            )
            candidate = _clean_rewrite(response)

            if not candidate or len(candidate) < 10:
                log.warning("rewrite_too_short", attempt=attempt, response=repr(response))
                continue

            guard = check_hallucinations(candidate, source_resume_text)
            last_rewrite = candidate
            last_guard = guard

            if guard.passed:
                log.info("rewrite_accepted", attempt=attempt, model=model)
                return RewriteResult(
                    rewritten_text=candidate,
                    original_text=original_text,
                    hallucination_check_passed=True,
                    flagged_entities=[],
                    model_used=model,
                )
            else:
                log.warning(
                    "rewrite_hallucination_detected",
                    attempt=attempt,
                    flagged=guard.flagged_entities,
                )

        except Exception as exc:
            log.error("rewrite_llm_error", attempt=attempt, error=str(exc))

    # All retries exhausted or failed guard — return original with warning
    flagged = last_guard.flagged_entities if last_guard else []
    warning = (
        last_guard.warning if last_guard else
        "Rewrite failed due to a system error. Original text retained."
    )
    log.warning("rewrite_returning_original", reason=warning)

    return RewriteResult(
        rewritten_text=original_text,
        original_text=original_text,
        hallucination_check_passed=False,
        flagged_entities=flagged,
        model_used=model,
        warning=warning,
    )


def _clean_rewrite(raw: str) -> str:
    """Strip common LLM preamble from rewrite output."""
    raw = raw.strip()
    # Remove leading labels like "Rewritten:", "Here is:", etc.
    raw = re.sub(
        r"^(rewritten[:\-]?|here\s+is[:\-]?|improved[:\-]?|result[:\-]?)\s*",
        "",
        raw,
        flags=re.IGNORECASE,
    )
    # Remove wrapping quotes
    if raw.startswith('"') and raw.endswith('"'):
        raw = raw[1:-1]
    if raw.startswith("'") and raw.endswith("'"):
        raw = raw[1:-1]
    return raw.strip()
