"""Role-type weight profiles for the scoring engine."""

from __future__ import annotations

WEIGHT_PROFILES: dict[str, dict[str, float]] = {
    "software_engineering": {
        "keyword":     0.20,
        "semantic":    0.30,
        "skill_depth": 0.20,
        "experience":  0.15,
        "impact":      0.12,
        "education":   0.03,
    },
    "data_science": {
        "keyword":     0.18,
        "semantic":    0.28,
        "skill_depth": 0.22,
        "experience":  0.15,
        "impact":      0.12,
        "education":   0.05,
    },
    "product_management": {
        "keyword":     0.15,
        "semantic":    0.25,
        "skill_depth": 0.10,
        "experience":  0.25,
        "impact":      0.20,
        "education":   0.05,
    },
    "finance": {
        "keyword":     0.20,
        "semantic":    0.20,
        "skill_depth": 0.15,
        "experience":  0.20,
        "impact":      0.15,
        "education":   0.10,
    },
    "marketing": {
        "keyword":     0.20,
        "semantic":    0.25,
        "skill_depth": 0.10,
        "experience":  0.20,
        "impact":      0.20,
        "education":   0.05,
    },
    "design": {
        "keyword":     0.15,
        "semantic":    0.25,
        "skill_depth": 0.20,
        "experience":  0.18,
        "impact":      0.20,
        "education":   0.02,
    },
    "default": {
        "keyword":     0.20,
        "semantic":    0.25,
        "skill_depth": 0.15,
        "experience":  0.20,
        "impact":      0.15,
        "education":   0.05,
    },
}

# Role title keyword → profile mapping
_ROLE_KEYWORDS: dict[str, str] = {
    "software": "software_engineering",
    "engineer": "software_engineering",
    "developer": "software_engineering",
    "backend": "software_engineering",
    "frontend": "software_engineering",
    "fullstack": "software_engineering",
    "full stack": "software_engineering",
    "devops": "software_engineering",
    "data scientist": "data_science",
    "machine learning": "data_science",
    "ml engineer": "data_science",
    "data analyst": "data_science",
    "product manager": "product_management",
    "product owner": "product_management",
    "finance": "finance",
    "accountant": "finance",
    "analyst": "finance",
    "marketing": "marketing",
    "content": "marketing",
    "designer": "design",
    "ux": "design",
    "ui": "design",
}


def get_weight_profile(role_type: str) -> dict[str, float]:
    """Return the weight profile for a given role type (falls back to default)."""
    return WEIGHT_PROFILES.get(role_type, WEIGHT_PROFILES["default"]).copy()


def infer_role_type(role_title: str | None) -> str:
    """Infer role type from a job title string."""
    if not role_title:
        return "default"
    title_lower = role_title.lower()
    for keyword, profile in _ROLE_KEYWORDS.items():
        if keyword in title_lower:
            return profile
    return "default"
