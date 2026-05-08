"""LLM prompt templates — versioned, task-specific prompts.

All prompts are defined here, not scattered across pipeline modules.
This makes prompt iteration, A/B testing, and auditing straightforward.

Version convention: bump PROMPT_VERSION when any template changes so
prompt_version is stored alongside analysis results for reproducibility.
"""

from __future__ import annotations

PROMPT_VERSION = "1.0.0"


# ─── JD Parsing ───────────────────────────────────────────────────────────────

JD_PARSE_PROMPT = """You are an expert recruiter parsing a job description into structured data.

Extract the following fields from the job description below.

Return ONLY valid JSON matching this exact schema:
{{
  "title": "Job title string",
  "company": "Company name or null",
  "required_skills": ["skill1", "skill2"],
  "preferred_skills": ["skill1", "skill2"],
  "required_yoe_min": <number or null>,
  "required_yoe_max": <number or null>,
  "required_degree": "bachelor|master|phd|associate|none or null",
  "preferred_fields": ["computer science", "engineering"],
  "seniority_level": "intern|junior|mid|senior|lead|principal|director or null",
  "responsibilities": ["responsibility 1 (max 15 words)", "responsibility 2"],
  "location": "City, State or Remote or null",
  "employment_type": "full_time|part_time|contract|internship or null",
  "quality_warnings": ["warning if JD seems unrealistic or unclear"]
}}

Rules:
- required_skills: only hard requirements explicitly stated as required/must-have
- preferred_skills: nice-to-have / preferred skills
- responsibilities: extract up to 8 key responsibilities, max 15 words each
- quality_warnings: flag if YOE > 10 for junior roles, or > 15 required skills

Job Description:
\"\"\"
{jd_text}
\"\"\"

Return ONLY the JSON object. No explanation."""


# ─── Skill Extraction ─────────────────────────────────────────────────────────

SKILL_EXTRACT_PROMPT = """Extract all technical and professional skills from this resume text.

Return ONLY a JSON array of skill strings. Normalize abbreviations
(e.g. "k8s" → "kubernetes", "ML" → "machine learning"). Max 60 skills.

Resume text:
\"\"\"
{resume_text}
\"\"\"

Return ONLY: ["skill1", "skill2", ...]"""


# ─── Impact Scoring ───────────────────────────────────────────────────────────

IMPACT_SCORE_PROMPT = """You are a senior technical recruiter evaluating resume bullet points.

Rate each bullet point for impact quality on a scale of 0-10:
- 10: Strong action verb + specific quantified result (e.g. "Reduced API latency by 40% serving 2M users")
- 7-9: Good action verb + result but missing quantification
- 4-6: Describes responsibility but no result
- 1-3: Vague, passive, or describes duties only
- 0: Not a professional bullet point

Return ONLY valid JSON array:
[{{"bullet": "...", "score": 8, "reason": "one sentence"}}, ...]

Bullets to score:
{bullets_json}

Return ONLY the JSON array."""


# ─── Feedback Generation ──────────────────────────────────────────────────────

FEEDBACK_GENERATE_PROMPT = """You are a senior recruiter and career coach with 15 years of experience.

A candidate's resume was analyzed against a job description. Generate specific, actionable feedback.

CRITICAL RULES:
- Be SPECIFIC. Reference the exact gap, not generic advice.
- Each feedback item must explain WHY it matters for THIS specific role.
- Do NOT give generic advice that applies to any resume.
- Limit to the {max_items} most impactful gaps.

Resume Score: {composite_score}/100
Role: {role_title}
Missing Required Skills: {missing_required}
Weak Bullet Points (low quantification): {weak_bullets}
ATS Issues: {ats_warnings}
Experience Gap: {experience_gap}

Return a JSON array of feedback items:
[
  {{
    "category": "keyword|semantic|impact|ats|education|experience",
    "severity": "critical|high|medium|low",
    "title": "Short title (max 10 words)",
    "description": "Specific description of the issue and why it matters (2-3 sentences)",
    "original_text": "The specific text from the resume that needs improvement (or null)",
    "score_delta": <estimated score points improvement if fixed, 1-15>,
    "source_section": "experience|skills|education|summary|formatting"
  }}
]

Return ONLY the JSON array, no other text."""


# ─── Bullet Rewrite ───────────────────────────────────────────────────────────

REWRITE_BULLET_PROMPT = """You are an expert resume writer. Rewrite the bullet point below to be more impactful.

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


# ─── Summary Rewrite ──────────────────────────────────────────────────────────

REWRITE_SUMMARY_PROMPT = """You are an expert resume writer. Rewrite this professional summary to be
more compelling for the target role while strictly preserving all facts.

STRICT RULES:
1. Do NOT add any experience, skills, or achievements not in the original text.
2. Keep to 3-4 sentences max.
3. Open with a strong positioning statement.
4. Include the most relevant skills for: {role_title}

Original Summary:
{original_text}

Return ONLY the rewritten summary. No explanation."""


def get_prompt(task: str, **kwargs: str) -> str:
    """Render a named prompt template with provided kwargs.

    Args:
        task: One of 'jd_parse', 'skill_extract', 'impact_score',
              'feedback_generate', 'rewrite_bullet', 'rewrite_summary'.
        **kwargs: Template variables.

    Returns:
        Rendered prompt string.

    Raises:
        KeyError: If task name is unknown.
        KeyError: If a required template variable is missing.
    """
    _TEMPLATES = {
        "jd_parse": JD_PARSE_PROMPT,
        "skill_extract": SKILL_EXTRACT_PROMPT,
        "impact_score": IMPACT_SCORE_PROMPT,
        "feedback_generate": FEEDBACK_GENERATE_PROMPT,
        "rewrite_bullet": REWRITE_BULLET_PROMPT,
        "rewrite_summary": REWRITE_SUMMARY_PROMPT,
    }
    template = _TEMPLATES[task]
    return template.format(**kwargs)
