"""Synonym expander — alias and acronym expansion for keyword matching."""

from __future__ import annotations

# Bidirectional alias map: each entry maps a canonical form ↔ common aliases
# All lookups are lowercased
_ALIAS_MAP: dict[str, list[str]] = {
    "machine learning": ["ml", "machine-learning"],
    "artificial intelligence": ["ai", "a.i."],
    "natural language processing": ["nlp", "natural-language-processing"],
    "kubernetes": ["k8s", "kube"],
    "postgresql": ["postgres", "psql", "pg"],
    "javascript": ["js"],
    "typescript": ["ts"],
    "python": ["py"],
    "amazon web services": ["aws", "amazon cloud"],
    "google cloud platform": ["gcp", "google cloud"],
    "microsoft azure": ["azure", "ms azure"],
    "continuous integration": ["ci", "ci/cd"],
    "continuous deployment": ["cd", "ci/cd"],
    "infrastructure as code": ["iac", "infrastructure-as-code"],
    "object oriented programming": ["oop", "object-oriented"],
    "test driven development": ["tdd", "test-driven-development"],
    "agile": ["agile methodology", "scrum", "agile/scrum"],
    "react": ["reactjs", "react.js"],
    "node.js": ["nodejs", "node"],
    "docker": ["containerization", "docker containers"],
    "elasticsearch": ["elastic", "es"],
    "nosql": ["no-sql", "non-relational"],
    "data structures": ["ds", "data-structures"],
    "algorithms": ["algo", "data structures and algorithms", "dsa"],
    "continuous learning": ["lifelong learning"],
    "deep learning": ["dl", "deep-learning", "neural networks"],
    "convolutional neural network": ["cnn", "convnet"],
    "recurrent neural network": ["rnn", "lstm"],
    "large language model": ["llm", "gpt", "language model"],
    "rest api": ["restful api", "rest", "restful", "rest services"],
    "graphql": ["graph ql"],
    "sql": ["structured query language", "relational database"],
    "nosql": ["mongodb", "cassandra", "dynamodb", "redis", "non-relational"],
    "devops": ["dev ops", "dev-ops"],
    "ci/cd": ["continuous integration", "continuous deployment", "jenkins", "github actions"],
    "microservices": ["micro-services", "microservice architecture"],
    "api": ["application programming interface", "web api", "rest api"],
    "ui/ux": ["user interface", "user experience", "ux", "ui"],
    "product management": ["pm", "product manager"],
    "project management": ["pmp", "project manager"],
    "data analysis": ["data analytics", "data analyst"],
    "data science": ["data scientist", "ds"],
    "tableau": ["business intelligence", "bi", "data visualization"],
    "power bi": ["powerbi", "microsoft power bi"],
    "version control": ["git", "github", "gitlab", "svn", "source control"],
    "regression testing": ["qa", "quality assurance"],
    "unit testing": ["unit tests", "automated testing"],
    "linux": ["unix", "bash", "shell scripting"],
}

# Build reverse lookup: alias → canonical
_REVERSE_MAP: dict[str, str] = {}
for canonical, aliases in _ALIAS_MAP.items():
    _REVERSE_MAP[canonical] = canonical  # canonical maps to itself
    for alias in aliases:
        _REVERSE_MAP[alias.lower()] = canonical


def expand_aliases(skill: str) -> set[str]:
    """Return a set of all aliases and the canonical form for a given skill.

    Example: expand_aliases("ML") → {"ml", "machine learning", "machine-learning"}
    """
    skill_lower = skill.lower().strip()
    variants: set[str] = {skill_lower}

    # Direct lookup from reverse map
    canonical = _REVERSE_MAP.get(skill_lower)
    if canonical:
        variants.add(canonical)
        variants.update(a.lower() for a in _ALIAS_MAP.get(canonical, []))

    # Also check if skill is a canonical itself
    if skill_lower in _ALIAS_MAP:
        variants.update(a.lower() for a in _ALIAS_MAP[skill_lower])

    return variants


def normalize_skill(skill: str) -> str:
    """Normalize a skill string to its canonical form."""
    return _REVERSE_MAP.get(skill.lower().strip(), skill.lower().strip())
