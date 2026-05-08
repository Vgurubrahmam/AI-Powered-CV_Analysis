"""Pipeline orchestrator — end-to-end resume analysis runner.

Accepts an analysis_id, fetches the resume and job description from the database,
runs all pipeline stages in the correct order (parallelising where safe), updates
the analysis status at each stage, and persists the final score + feedback.

Stage execution order:
  1. PARSING   → parse resume bytes (if not already parsed) + parse JD (LLM)
  2. MATCHING  → keyword match + semantic match + skill extraction (parallel)
  3. SCORING   → composite score + calibration
  4. ANALYSIS  → experience, education, ATS, impact, bias (parallel)
  5. FEEDBACK  → generate + rank + persist feedback items

Failure handling:
  - Each stage is individually try/except'd.
  - A stage failure marks that component as None/empty, not the whole pipeline.
  - If parsing completely fails → raise and mark analysis FAILED immediately.
  - All other stage failures → PARTIAL result with degraded score.
"""

from __future__ import annotations

import asyncio
import uuid
from dataclasses import dataclass, field
from typing import Any, Optional

import structlog

from app.core.constants import AnalysisStatus, ParseStatus
from app.core.exceptions import PipelineException

log = structlog.get_logger(__name__)


# ─── Result container ─────────────────────────────────────────────────────────

@dataclass
class PipelineResult:
    """Complete output of the analysis pipeline."""

    analysis_id: uuid.UUID
    status: str

    # Stage outputs
    parsed_resume: Any = None
    parsed_jd: Any = None
    keyword_result: Any = None
    semantic_result: Any = None
    skill_result: Any = None
    experience_result: Any = None
    education_result: Any = None
    ats_result: Any = None
    impact_result: Any = None
    bias_result: Any = None
    score_result: Any = None
    feedback_items: list = field(default_factory=list)

    # Errors per stage
    stage_errors: dict[str, str] = field(default_factory=dict)


# ─── Orchestrator ─────────────────────────────────────────────────────────────

async def run_pipeline(
    analysis_id: uuid.UUID,
    db,
    redis=None,
) -> PipelineResult:
    """Execute the full analysis pipeline for a given analysis_id.

    Args:
        analysis_id: UUID of the Analysis record.
        db: Async SQLAlchemy session.
        redis: Optional Redis client (used for embedding cache etc.).

    Returns:
        PipelineResult with all stage outputs populated.

    Raises:
        PipelineException: if critical data (resume/JD) cannot be loaded.
    """
    from app.repositories.analysis_repo import AnalysisRepository
    from app.repositories.resume_repo import ResumeRepository
    from app.repositories.job_repo import JobRepository
    from app.models.feedback import FeedbackItem

    analysis_repo = AnalysisRepository(db)
    resume_repo = ResumeRepository(db)
    job_repo = JobRepository(db)

    result = PipelineResult(analysis_id=analysis_id, status=AnalysisStatus.QUEUED.value)

    # ── Load analysis record ──────────────────────────────────────────────────
    analysis = await analysis_repo.get(analysis_id)
    if not analysis:
        raise PipelineException(f"Analysis {analysis_id} not found in database.")

    async def _set_status(status: str) -> None:
        await analysis_repo.update(analysis, {"status": status})
        result.status = status
        log.info("pipeline_stage", analysis_id=str(analysis_id), status=status)

    # ─────────────────────────────────────────────────────────────────────────
    # STAGE 1 — PARSING
    # ─────────────────────────────────────────────────────────────────────────
    await _set_status(AnalysisStatus.PARSING.value)

    resume = await resume_repo.get_user_resume(analysis.resume_id, analysis.user_id)
    jd = await job_repo.get(analysis.job_id)

    if not resume or not jd:
        await _set_status(AnalysisStatus.FAILED.value)
        raise PipelineException("Resume or JD record missing from database.")

    # Parse resume (use cached parsed_data if available)
    parsed_resume = await _parse_resume(resume, result)
    if not parsed_resume:
        await _set_status(AnalysisStatus.FAILED.value)
        raise PipelineException("Resume parsing failed — cannot continue pipeline.")
    result.parsed_resume = parsed_resume

    # Parse JD (LLM-backed, always re-run for freshness unless already parsed)
    parsed_jd = await _parse_jd(jd, result)
    result.parsed_jd = parsed_jd

    # ─────────────────────────────────────────────────────────────────────────
    # STAGE 2 — MATCHING (keyword + semantic + skills, parallel)
    # ─────────────────────────────────────────────────────────────────────────
    await _set_status(AnalysisStatus.MATCHING.value)

    resume_text = parsed_resume.raw_text
    required_skills = _get_required_skills(parsed_jd)
    preferred_skills = _get_preferred_skills(parsed_jd)
    jd_requirements = _get_jd_requirements(parsed_jd)
    resume_chunks = _make_chunks(parsed_resume)

    keyword_task = asyncio.create_task(
        _run_keyword_match(resume_text, required_skills, preferred_skills, result)
    )
    semantic_task = asyncio.create_task(
        _run_semantic_match(resume_chunks, jd_requirements, result)
    )
    skill_task = asyncio.create_task(
        _run_skill_extraction(resume_text, parsed_resume.sections_dict, result)
    )

    await asyncio.gather(keyword_task, semantic_task, skill_task, return_exceptions=True)

    # ─────────────────────────────────────────────────────────────────────────
    # STAGE 3 — SCORING
    # ─────────────────────────────────────────────────────────────────────────
    await _set_status(AnalysisStatus.SCORING.value)

    score_result = await _run_scoring(
        result,
        role_type=_detect_role_type(jd),
        parse_confidence=parsed_resume.parse_confidence,
    )
    result.score_result = score_result

    # Persist intermediate score to DB
    if score_result:
        await analysis_repo.update(analysis, {
            "score": score_result.composite,
            "score_breakdown": score_result.breakdown,
        })

    # ─────────────────────────────────────────────────────────────────────────
    # STAGE 4 — ANALYSIS (experience, education, ATS, impact, bias — parallel)
    # ─────────────────────────────────────────────────────────────────────────
    exp_task = asyncio.create_task(
        _run_experience_analysis(parsed_resume, parsed_jd, result)
    )
    edu_task = asyncio.create_task(
        _run_education_analysis(parsed_resume, parsed_jd, result)
    )
    ats_task = asyncio.create_task(
        _run_ats_check(resume_text, resume, result)
    )
    impact_task = asyncio.create_task(
        _run_impact_score(parsed_resume, result)
    )
    bias_task = asyncio.create_task(
        _run_bias_audit(resume_text, parsed_resume, result)
    )

    await asyncio.gather(
        exp_task, edu_task, ats_task, impact_task, bias_task,
        return_exceptions=True,
    )

    # ─────────────────────────────────────────────────────────────────────────
    # STAGE 5 — FEEDBACK
    # ─────────────────────────────────────────────────────────────────────────
    await _set_status(AnalysisStatus.FEEDBACK.value)

    feedback_items = await _run_feedback_generation(result, jd)
    result.feedback_items = feedback_items

    # Persist feedback items to DB
    await _persist_feedback(analysis, feedback_items, db)

    # ─────────────────────────────────────────────────────────────────────────
    # FINALIZE
    # ─────────────────────────────────────────────────────────────────────────
    final_status = AnalysisStatus.PARTIAL.value if result.stage_errors else AnalysisStatus.DONE.value

    pipeline_meta = {
        "stage_errors": result.stage_errors,
        "parse_method": parsed_resume.parse_method,
        "ocr_used": parsed_resume.ocr_used,
        "embedding_model": getattr(result.semantic_result, "embedding_model", "unknown"),
    }

    await analysis_repo.update(analysis, {
        "status": final_status,
        "pipeline_meta": pipeline_meta,
        "score": result.score_result.composite if result.score_result else None,
        "score_breakdown": result.score_result.breakdown if result.score_result else {},
        "confidence": result.score_result.confidence if result.score_result else 0.0,
    })

    result.status = final_status
    log.info(
        "pipeline_complete",
        analysis_id=str(analysis_id),
        status=final_status,
        score=result.score_result.composite if result.score_result else None,
        feedback_count=len(feedback_items),
        errors=list(result.stage_errors.keys()),
    )

    return result


# ─── Stage runners ────────────────────────────────────────────────────────────

async def _parse_resume(resume, result: PipelineResult):
    """Parse resume bytes; return cached parsed_data if already parsed."""
    from app.pipeline.parsing.resume_parser import parse_resume, ParsedResume

    # If the DB record already holds parsed_data, reconstruct cheaply
    if resume.parsed_data and resume.parse_status == ParseStatus.SUCCESS.value:
        pd = resume.parsed_data
        return _dict_to_parsed_resume(pd, resume.parse_confidence)

    # Re-parse from bytes (download from S3 if needed)
    try:
        file_bytes = await _fetch_file_bytes(resume)
        file_type = (resume.file_type or "pdf").lower()
        parsed = parse_resume(file_bytes, file_type)
        return parsed
    except Exception as exc:
        log.error("resume_parse_error", error=str(exc))
        result.stage_errors["parsing"] = str(exc)
        return None


async def _parse_jd(jd, result: PipelineResult):
    """Parse job description via LLM; return cached if available."""
    from app.pipeline.parsing.jd_parser import parse_job_description

    if jd.parsed_data:
        return jd.parsed_data

    try:
        raw_text = jd.raw_text or jd.description or ""
        if not raw_text.strip():
            result.stage_errors["jd_parsing"] = "JD raw_text is empty."
            return {}
        parsed = await parse_job_description(raw_text)
        return parsed
    except Exception as exc:
        log.warning("jd_parse_error", error=str(exc))
        result.stage_errors["jd_parsing"] = str(exc)
        return {}


async def _run_keyword_match(
    resume_text: str,
    required: list[str],
    preferred: list[str],
    result: PipelineResult,
) -> None:
    try:
        from app.pipeline.matching.keyword_engine import compute_keyword_score
        result.keyword_result = compute_keyword_score(resume_text, required, preferred)
    except Exception as exc:
        log.warning("keyword_match_error", error=str(exc))
        result.stage_errors["keyword_match"] = str(exc)


async def _run_semantic_match(
    resume_chunks: list[str],
    jd_requirements: list[str],
    result: PipelineResult,
) -> None:
    try:
        from app.pipeline.matching.semantic_engine import compute_semantic_score
        result.semantic_result = await compute_semantic_score(resume_chunks, jd_requirements)
    except Exception as exc:
        log.warning("semantic_match_error", error=str(exc))
        result.stage_errors["semantic_match"] = str(exc)


async def _run_skill_extraction(
    resume_text: str,
    sections: dict | None,
    result: PipelineResult,
) -> None:
    try:
        from app.pipeline.matching.skill_extractor import extract_skills
        result.skill_result = await extract_skills(resume_text, use_llm=True, sections=sections)
    except Exception as exc:
        log.warning("skill_extraction_error", error=str(exc))
        result.stage_errors["skill_extraction"] = str(exc)


async def _run_scoring(
    result: PipelineResult,
    role_type: str,
    parse_confidence: float,
):
    try:
        from app.pipeline.scoring.score_engine import compute_composite_score, SubScores
        from app.pipeline.scoring.calibrator import calibrate_score

        kw = result.keyword_result
        sem = result.semantic_result
        sk = result.skill_result

        sub = SubScores(
            keyword=kw.score if kw else None,
            semantic=sem.score if sem else None,
            skill_depth=None,   # computed below
        )

        # Skill depth score from skill_extractor
        if sk and result.parsed_jd:
            from app.pipeline.matching.skill_extractor import compute_skill_depth_score
            req = _get_required_skills(result.parsed_jd)
            pref = _get_preferred_skills(result.parsed_jd)
            sub.skill_depth = compute_skill_depth_score(sk.canonical_skills, req, pref)

        score = compute_composite_score(sub, role_type=role_type, parse_confidence=parse_confidence)

        # Apply calibration percentile
        try:
            score = calibrate_score(score)
        except Exception:
            pass  # calibration is optional

        return score
    except Exception as exc:
        log.warning("scoring_error", error=str(exc))
        result.stage_errors["scoring"] = str(exc)
        return None


async def _run_experience_analysis(parsed_resume, parsed_jd: dict, result: PipelineResult) -> None:
    try:
        from app.pipeline.analysis.experience_analyzer import analyze_experience
        positions = parsed_resume.experience or []
        req_yoe_min = _safe_float(parsed_jd.get("required_yoe_min"))
        req_yoe_max = _safe_float(parsed_jd.get("required_yoe_max"))
        seniority = parsed_jd.get("seniority_level")
        result.experience_result = analyze_experience(
            positions, req_yoe_min, req_yoe_max, seniority
        )
    except Exception as exc:
        log.warning("experience_analysis_error", error=str(exc))
        result.stage_errors["experience_analysis"] = str(exc)


async def _run_education_analysis(parsed_resume, parsed_jd: dict, result: PipelineResult) -> None:
    try:
        from app.pipeline.analysis.education_analyzer import analyze_education
        education_data = parsed_resume.education or []
        required_degree = parsed_jd.get("required_degree")
        preferred_fields = parsed_jd.get("preferred_fields") or []
        result.education_result = analyze_education(
            education_data,
            required_degree=required_degree,
            preferred_fields=preferred_fields,
            full_resume_text=parsed_resume.raw_text,
        )
    except Exception as exc:
        log.warning("education_analysis_error", error=str(exc))
        result.stage_errors["education_analysis"] = str(exc)


async def _run_ats_check(resume_text: str, resume, result: PipelineResult) -> None:
    try:
        from app.pipeline.analysis.ats_checker import check_ats_compatibility
        file_type = (resume.file_type or "pdf").lower()
        tables_detected = resume.parsed_data.get("has_tables", False) if resume.parsed_data else False
        result.ats_result = check_ats_compatibility(
            resume_text, file_type, tables_detected=tables_detected
        )
    except Exception as exc:
        log.warning("ats_check_error", error=str(exc))
        result.stage_errors["ats_check"] = str(exc)


async def _run_impact_score(parsed_resume, result: PipelineResult) -> None:
    try:
        from app.pipeline.analysis.impact_scorer import score_impact
        bullets = _collect_bullets(parsed_resume)
        result.impact_result = await score_impact(bullets)
    except Exception as exc:
        log.warning("impact_score_error", error=str(exc))
        result.stage_errors["impact_score"] = str(exc)


async def _run_bias_audit(resume_text: str, parsed_resume, result: PipelineResult) -> None:
    try:
        from app.pipeline.analysis.bias_auditor import audit_bias_risks
        parsed_dict = {
            "contact": parsed_resume.contact,
            "education": parsed_resume.education,
        }
        result.bias_result = audit_bias_risks(resume_text, parsed_dict)
    except Exception as exc:
        log.warning("bias_audit_error", error=str(exc))
        result.stage_errors["bias_audit"] = str(exc)


async def _run_feedback_generation(result: PipelineResult, jd) -> list:
    try:
        from app.pipeline.feedback.feedback_generator import generate_feedback
        from app.pipeline.feedback.priority_ranker import rank_feedback_items

        kw = result.keyword_result
        ats = result.ats_result
        impact = result.impact_result
        exp = result.experience_result

        analysis_data: dict = {
            "composite_score": result.score_result.composite if result.score_result else 0,
            "role_title": getattr(jd, "title", "the specified role"),
            "keyword_result": {
                "missing_required": kw.missing_required if kw else [],
                "matched_required": kw.matched_required if kw else [],
            },
            "weak_bullets": getattr(impact, "low_impact_bullets", []) if impact else [],
            "ats_warnings": (
                [f"{w.level.value.upper()}: {w.message}" for w in ats.warnings]
                if ats else []
            ),
            "experience_gap": (
                f"Candidate has {exp.total_yoe:.1f} YOE vs {exp.required_yoe or 'N/A'} required"
                if exp else "N/A"
            ),
        }

        items = await generate_feedback(analysis_data, max_items=10)
        return rank_feedback_items(items, max_items=10)
    except Exception as exc:
        log.warning("feedback_generation_error", error=str(exc))
        result.stage_errors["feedback_generation"] = str(exc)
        return []


async def _persist_feedback(analysis, items: list, db) -> None:
    """Persist FeedbackItemData list → FeedbackItem ORM rows."""
    try:
        from app.models.feedback import FeedbackItem
        from app.core.constants import FeedbackCategory, FeedbackSeverity
        from app.pipeline.feedback.feedback_generator import _normalize_category, _normalize_severity

        for item in items:
            fb = FeedbackItem(
                analysis_id=analysis.id,
                category=_normalize_category(item.category),
                severity=_normalize_severity(item.severity),
                title=item.title,
                description=item.description,
                original_text=item.original_text,
                score_delta=item.score_delta,
                source_section=item.source_section,
            )
            db.add(fb)
        await db.commit()
    except Exception as exc:
        log.error("feedback_persist_error", error=str(exc))
        await db.rollback()


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _get_required_skills(parsed_jd: dict | None) -> list[str]:
    if not parsed_jd:
        return []
    return parsed_jd.get("required_skills") or []


def _get_preferred_skills(parsed_jd: dict | None) -> list[str]:
    if not parsed_jd:
        return []
    return parsed_jd.get("preferred_skills") or []


def _get_jd_requirements(parsed_jd: dict | None) -> list[str]:
    """Flatten JD requirements into sentence-level chunks for semantic matching."""
    if not parsed_jd:
        return []
    reqs: list[str] = []
    reqs.extend(parsed_jd.get("required_skills") or [])
    reqs.extend(parsed_jd.get("responsibilities") or [])
    reqs.extend(parsed_jd.get("preferred_skills") or [])
    return [r for r in reqs if r and len(r) > 3][:40]  # cap at 40 requirements


def _make_chunks(parsed_resume) -> list[str]:
    """Build sentence-level resume chunks for semantic matching."""
    chunks: list[str] = []
    if parsed_resume.summary:
        chunks.append(parsed_resume.summary)
    for job in (parsed_resume.experience or []):
        if job.get("bullets"):
            chunks.extend(job["bullets"][:5])
        elif job.get("raw"):
            chunks.append(job["raw"][:300])
    if parsed_resume.skills:
        chunks.append(", ".join(parsed_resume.skills[:30]))
    return [c for c in chunks if c and len(c.strip()) > 10][:50]


def _collect_bullets(parsed_resume) -> list[str]:
    """Collect all experience bullets for impact scoring."""
    bullets: list[str] = []
    for job in (parsed_resume.experience or []):
        bullets.extend(job.get("bullets", []))
    return bullets[:50]


def _detect_role_type(jd) -> str:
    """Map job title to a weight profile key."""
    title = (getattr(jd, "title", "") or "").lower()
    if any(t in title for t in ("software", "engineer", "developer", "sre", "devops", "platform")):
        return "software_engineering"
    if any(t in title for t in ("product manager", "pm ", " pm", "product owner")):
        return "product_management"
    if any(t in title for t in ("finance", "analyst", "accounting", "cfo", "controller")):
        return "finance"
    return "default"


def _safe_float(val) -> Optional[float]:
    try:
        return float(val) if val is not None else None
    except (ValueError, TypeError):
        return None


async def _fetch_file_bytes(resume) -> bytes:
    """Fetch resume file bytes from S3/storage if not in memory."""
    from app.services.storage_service import StorageService

    if hasattr(resume, "_file_bytes") and resume._file_bytes:
        return resume._file_bytes

    storage = StorageService()
    return await storage.download_resume(resume.storage_key)


def _dict_to_parsed_resume(data: dict, confidence: float):
    """Reconstruct a lightweight ParsedResume-like object from cached JSONB data."""
    from app.pipeline.parsing.resume_parser import ParsedResume
    from app.core.constants import ParseStatus

    return ParsedResume(
        raw_text=data.get("raw_text", ""),
        contact=data.get("contact", {}),
        summary=data.get("summary"),
        experience=data.get("experience", []),
        education=data.get("education", []),
        skills=data.get("skills", []),
        certifications=data.get("certifications", []),
        projects=data.get("projects", []),
        sections_detected=data.get("sections_detected", []),
        sections_dict=data.get("sections_dict", {}),
        parse_status=ParseStatus.SUCCESS.value,
        parse_confidence=confidence,
        parse_method="cached",
        ocr_used=data.get("ocr_used", False),
    )
