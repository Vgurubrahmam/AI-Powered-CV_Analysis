"""Skill taxonomy — ESCO/O*NET-inspired normalized skill dictionary.

Loaded once at first import, cached in module-level dict.
Maps raw skill mention → canonical normalized name.

Usage:
    from app.pipeline.matching.skill_taxonomy import get_taxonomy, normalize_skill
    canonical = normalize_skill("k8s")  # → "kubernetes"
"""

from __future__ import annotations

import threading
from functools import lru_cache
from typing import Optional

import structlog

log = structlog.get_logger(__name__)

_LOCK = threading.Lock()
_TAXONOMY: dict[str, str] | None = None  # raw_lower → canonical


# ─── Raw taxonomy data ────────────────────────────────────────────────────────
# Format: canonical_name → [aliases, abbreviations, variants]
_RAW_TAXONOMY: dict[str, list[str]] = {
    # ── Languages ──────────────────────────────────────────────────────────────
    "python": ["python3", "python 3", "py"],
    "javascript": ["js", "javascript es6", "es6", "es2015", "ecmascript"],
    "typescript": ["ts", "typescript 4", "typescript 5"],
    "java": ["java 8", "java 11", "java 17", "java 21", "jvm"],
    "kotlin": ["kotlin/jvm"],
    "swift": ["swift 5", "swift ui", "swiftui"],
    "go": ["golang", "go lang"],
    "rust": ["rust lang"],
    "c++": ["cpp", "c plus plus", "cplusplus"],
    "c#": ["csharp", "c sharp", ".net c#"],
    "ruby": ["ruby on rails", "ror"],
    "php": ["php 7", "php 8"],
    "scala": ["scala 2", "scala 3"],
    "r": ["r programming", "r language", "r lang"],
    "matlab": ["matlab/simulink"],
    "shell": ["bash", "shell scripting", "bash scripting", "sh", "zsh"],
    "powershell": ["pwsh"],
    "sql": ["structured query language", "t-sql", "tsql", "pl/sql", "plsql"],
    "html": ["html5", "html 5"],
    "css": ["css3", "css 3", "cascading style sheets"],

    # ── Frontend ───────────────────────────────────────────────────────────────
    "react": ["reactjs", "react.js", "react js"],
    "vue": ["vuejs", "vue.js", "vue js", "vue 3"],
    "angular": ["angularjs", "angular 2", "angular js"],
    "next.js": ["nextjs", "next js"],
    "nuxt.js": ["nuxtjs", "nuxt js"],
    "svelte": ["sveltejs", "svelte.js"],
    "tailwind css": ["tailwindcss", "tailwind"],
    "redux": ["redux toolkit", "rtk"],
    "graphql": ["graph ql"],
    "webpack": [],
    "vite": [],

    # ── Backend / frameworks ───────────────────────────────────────────────────
    "fastapi": ["fast api"],
    "django": ["django rest framework", "drf"],
    "flask": ["flask python"],
    "spring boot": ["springboot", "spring framework", "spring"],
    "express.js": ["expressjs", "express js", "express"],
    "nestjs": ["nest.js"],
    "laravel": [],
    "rails": ["ruby on rails", "ror"],
    "asp.net": ["aspnet", "asp net", ".net core", "dotnet core"],

    # ── Databases ──────────────────────────────────────────────────────────────
    "postgresql": ["postgres", "pg", "psql", "pgvector"],
    "mysql": ["mysql 8"],
    "mongodb": ["mongo", "mongo db"],
    "redis": ["redis cache"],
    "elasticsearch": ["elastic search", "es", "opensearch"],
    "cassandra": ["apache cassandra"],
    "dynamodb": ["dynamo db", "aws dynamodb"],
    "sqlite": ["sqlite3"],
    "neo4j": ["graph database"],
    "snowflake": [],
    "bigquery": ["google bigquery", "bq"],

    # ── Cloud & Infrastructure ─────────────────────────────────────────────────
    "aws": ["amazon web services", "amazon aws"],
    "gcp": ["google cloud platform", "google cloud"],
    "azure": ["microsoft azure", "ms azure"],
    "kubernetes": ["k8s", "kube", "k8"],
    "docker": ["docker compose", "dockerfile", "containers"],
    "terraform": ["tf", "hashicorp terraform"],
    "ansible": [],
    "helm": [],
    "istio": [],
    "prometheus": [],
    "grafana": [],
    "jenkins": [],
    "github actions": ["gh actions", "gha"],
    "gitlab ci": ["gitlab ci/cd", "gitlab"],
    "circleci": ["circle ci"],
    "argocd": ["argo cd"],
    "pulumi": [],

    # ── AI / ML ────────────────────────────────────────────────────────────────
    "machine learning": ["ml"],
    "deep learning": ["dl"],
    "natural language processing": ["nlp", "natural language understanding", "nlu"],
    "computer vision": ["cv"],
    "pytorch": ["torch"],
    "tensorflow": ["tf", "keras"],
    "scikit-learn": ["sklearn", "scikit learn"],
    "hugging face": ["huggingface", "transformers"],
    "langchain": ["lang chain"],
    "llm": ["large language model", "large language models", "llms"],
    "openai": ["open ai", "gpt", "gpt-4", "chatgpt"],
    "anthropic": ["claude"],
    "numpy": ["np"],
    "pandas": ["pd"],
    "matplotlib": [],
    "spark": ["apache spark", "pyspark", "spark sql"],
    "airflow": ["apache airflow"],
    "mlflow": [],
    "sagemaker": ["aws sagemaker"],
    "vertex ai": ["google vertex"],

    # ── DevOps / Practices ────────────────────────────────────────────────────
    "ci/cd": ["cicd", "continuous integration", "continuous deployment", "continuous delivery"],
    "devops": ["dev ops"],
    "microservices": ["micro services", "microservice architecture"],
    "agile": ["scrum", "kanban", "safe agile"],
    "tdd": ["test driven development", "test-driven development"],
    "bdd": ["behavior driven development"],
    "rest api": ["restful api", "rest", "restful", "rest apis"],
    "grpc": ["grpc api"],
    "message queues": ["rabbitmq", "kafka", "apache kafka", "celery", "sqs", "pubsub"],

    # ── Testing ───────────────────────────────────────────────────────────────
    "pytest": ["py.test"],
    "jest": [],
    "cypress": [],
    "selenium": [],
    "unit testing": ["unit tests"],
    "integration testing": ["integration tests"],
    "load testing": ["k6", "locust", "jmeter"],

    # ── Security ──────────────────────────────────────────────────────────────
    "oauth": ["oauth2", "oauth 2.0"],
    "jwt": ["json web token", "json web tokens"],
    "sso": ["single sign on", "saml"],
    "penetration testing": ["pentest", "pen testing"],

    # ── Data / Analytics ──────────────────────────────────────────────────────
    "data engineering": [],
    "etl": ["extract transform load", "elt"],
    "dbt": ["data build tool"],
    "looker": [],
    "tableau": [],
    "power bi": ["powerbi", "microsoft power bi"],

    # ── Soft skills ───────────────────────────────────────────────────────────
    "leadership": ["team lead", "tech lead", "technical lead"],
    "communication": [],
    "problem solving": ["problem-solving"],
    "collaboration": ["cross-functional collaboration"],
    "mentoring": ["mentorship", "coaching"],
    "project management": ["pm", "project manager"],
}


def _build_index(raw: dict[str, list[str]]) -> dict[str, str]:
    """Build flat lookup: lowercase_alias → canonical_name."""
    index: dict[str, str] = {}
    for canonical, aliases in raw.items():
        index[canonical.lower()] = canonical
        for alias in aliases:
            index[alias.lower()] = canonical
    return index


def _get_taxonomy() -> dict[str, str]:
    global _TAXONOMY
    if _TAXONOMY is not None:
        return _TAXONOMY
    with _LOCK:
        if _TAXONOMY is None:
            _TAXONOMY = _build_index(_RAW_TAXONOMY)
            log.debug("skill_taxonomy_loaded", entries=len(_TAXONOMY))
    return _TAXONOMY


def normalize_skill(raw_skill: str) -> str:
    """Normalize a raw skill string to its canonical taxonomy name.

    Returns the canonical name if found, otherwise returns the original
    (stripped + lowercased) skill.
    """
    taxonomy = _get_taxonomy()
    key = raw_skill.strip().lower()
    return taxonomy.get(key, raw_skill.strip())


def get_taxonomy() -> dict[str, str]:
    """Return the full alias-to-canonical taxonomy dict (read-only view)."""
    return _get_taxonomy()


@lru_cache(maxsize=2048)
def is_known_skill(skill: str) -> bool:
    """Return True if the skill (or any alias) is in the taxonomy."""
    taxonomy = _get_taxonomy()
    return skill.strip().lower() in taxonomy


def get_all_canonical_skills() -> list[str]:
    """Return all unique canonical skill names."""
    return list(_RAW_TAXONOMY.keys())


def find_closest_canonical(skill: str, top_k: int = 3) -> list[tuple[str, float]]:
    """Find the closest canonical skills using simple character overlap.

    Useful for fuzzy suggestions when exact match fails.

    Returns:
        List of (canonical_name, similarity_score) tuples, highest first.
    """
    skill_lower = skill.strip().lower()
    results: list[tuple[str, float]] = []

    for canonical in _RAW_TAXONOMY:
        # Jaccard character bigram similarity
        a_bigrams = _bigrams(skill_lower)
        b_bigrams = _bigrams(canonical.lower())
        if not a_bigrams and not b_bigrams:
            continue
        intersection = len(a_bigrams & b_bigrams)
        union = len(a_bigrams | b_bigrams)
        if union > 0:
            sim = intersection / union
            if sim > 0.2:
                results.append((canonical, round(sim, 3)))

    results.sort(key=lambda x: x[1], reverse=True)
    return results[:top_k]


def _bigrams(text: str) -> set[str]:
    return {text[i:i+2] for i in range(len(text) - 1)}
