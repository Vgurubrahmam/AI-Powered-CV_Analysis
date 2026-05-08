"""Application configuration via pydantic-settings.

All settings are loaded from environment variables (with .env fallback).
Fail fast on startup if required vars are missing — never run with bad config.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Central application settings — all values come from environment vars."""

    _ENV_FILE = Path(__file__).resolve().parent.parent / ".env"

    model_config = SettingsConfigDict(
        env_file=_ENV_FILE,
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── Application ────────────────────────────────────────────────────────
    APP_ENV: str = "development"
    APP_URL: str = "http://localhost:8000"
    DEBUG: bool = False
    SECRET_KEY: str = "change-me-in-production"

    # ── Database ───────────────────────────────────────────────────────────
    DATABASE_URL: str = "postgresql+asyncpg://ats_user:ats_pass@localhost:5432/ats_db"

    # ── Redis ──────────────────────────────────────────────────────────────
    REDIS_URL: str = "redis://localhost:6379/0"

    # ── Supabase ───────────────────────────────────────────────────────────
    SUPABASE_URL: str = ""
    SUPABASE_ANON_KEY: SecretStr = SecretStr("")

    # ── JWT ────────────────────────────────────────────────────────────────
    JWT_SECRET_KEY: str = "change-me-generate-with-openssl-rand-hex-32"
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    JWT_REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # ── LLM — NVIDIA AI (primary) ───────────────────────────────────────
    NVIDIA_API_KEY: SecretStr = SecretStr("")
    NVIDIA_BASE_URL: str = "https://integrate.api.nvidia.com/v1"
    NVIDIA_DEFAULT_MODEL: str = "meta/llama-3.1-8b-instruct"
    NVIDIA_SMART_MODEL: str = "meta/llama-3.1-70b-instruct"

    # ── LLM — OpenRouter (fallback) ──────────────────────────────────────
    OPENROUTER_API_KEY: SecretStr = SecretStr("")
    OPENROUTER_BASE_URL: str = "https://openrouter.ai/api/v1"
    OPENROUTER_DEFAULT_MODEL: str = "google/gemma-3-27b-it:free"
    OPENROUTER_FAST_MODEL: str = "meta-llama/llama-3.1-8b-instruct:free"
    OPENROUTER_SMART_MODEL: str = "deepseek/deepseek-chat-v3-0324:free"

    # Fallback providers (optional)
    OPENAI_API_KEY: SecretStr = SecretStr("")
    ANTHROPIC_API_KEY: SecretStr = SecretStr("")

    LLM_MAX_RETRIES: int = 3
    LLM_RETRY_BASE_DELAY: float = 2.0

    # ── Embeddings ────────────────────────────────────────────────────────
    EMBEDDING_PROVIDER: str = "local"          # local | openai
    SBERT_MODEL_NAME: str = "all-MiniLM-L6-v2"
    EMBEDDING_DIMENSION: int = 384
    SENTENCE_TRANSFORMERS_HOME: str = "./models_cache"

    # ── Feature Flags ─────────────────────────────────────────────────────
    ENABLE_EMBEDDINGS: bool = False
    ENABLE_REDIS: bool = True

    # ── Object Storage (MinIO / S3 / local) ──────────────────────────────────
    STORAGE_BACKEND: str = "local"               # local | s3 | minio
    S3_ENDPOINT_URL: str = "http://localhost:9000"
    S3_BUCKET_NAME: str = "ats-resumes"
    S3_ACCESS_KEY: str = "minioadmin"            # MinIO / local alias
    S3_SECRET_KEY: SecretStr = SecretStr("minioadmin")
    AWS_ACCESS_KEY_ID: str = ""                  # AWS prod key (overrides S3_ACCESS_KEY)
    AWS_SECRET_ACCESS_KEY: SecretStr = SecretStr("")  # AWS prod secret
    AWS_REGION: str = "us-east-1"
    S3_USE_SSL: bool = False
    LOCAL_STORAGE_ROOT: str = ""                 # empty = auto (Backend/storage)

    @property
    def effective_s3_access_key(self) -> str:
        """Return AWS key if set, else MinIO key."""
        return self.AWS_ACCESS_KEY_ID or self.S3_ACCESS_KEY

    @property
    def effective_s3_secret_key(self) -> str:
        """Return AWS secret if set, else MinIO secret."""
        aws = self.AWS_SECRET_ACCESS_KEY.get_secret_value()
        return aws if aws else self.S3_SECRET_KEY.get_secret_value()

    # ── File Upload ────────────────────────────────────────────────────────
    FILE_MAX_SIZE_MB: int = 10
    ALLOWED_MIME_TYPES: str = (
        "application/pdf,"
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document,"
        "text/plain"
    )

    @property
    def allowed_mime_types_list(self) -> list[str]:
        return [m.strip() for m in self.ALLOWED_MIME_TYPES.split(",")]

    @property
    def file_max_size_bytes(self) -> int:
        return self.FILE_MAX_SIZE_MB * 1024 * 1024

    # ── Rate Limiting ──────────────────────────────────────────────────────
    RATE_LIMIT_FREE_ANALYSES_PER_DAY: int = 5
    RATE_LIMIT_PRO_ANALYSES_PER_DAY: int = 50
    RATE_LIMIT_REQUESTS_PER_MINUTE_FREE: int = 10
    RATE_LIMIT_REQUESTS_PER_MINUTE_PRO: int = 60

    # ── CORS ──────────────────────────────────────────────────────────────
    ALLOWED_ORIGINS: str = "http://localhost:3000,http://localhost:5173"

    @property
    def allowed_origins_list(self) -> list[str]:
        return [o.strip() for o in self.ALLOWED_ORIGINS.split(",")]

    # ── Cache TTLs ────────────────────────────────────────────────────────
    ANALYSIS_CACHE_TTL_SECONDS: int = 86400      # 24 h
    RESUME_PARSE_CACHE_TTL_SECONDS: int = 604800  # 7 d
    LOCK_TTL_SECONDS: int = 600                   # 10 min

    # ── Celery ────────────────────────────────────────────────────────────
    CELERY_BROKER_URL: str = "redis://localhost:6379/1"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/2"
    CELERY_TASK_SOFT_TIME_LIMIT: int = 300
    CELERY_TASK_TIME_LIMIT: int = 600

    # ── Email ─────────────────────────────────────────────────────────────
    SMTP_HOST: str = ""
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASSWORD: SecretStr = SecretStr("")
    EMAIL_FROM: str = "noreply@ats-platform.local"

    # ── ClamAV ────────────────────────────────────────────────────────────
    CLAMAV_HOST: str = ""
    CLAMAV_PORT: int = 3310

    # ── Observability ─────────────────────────────────────────────────────
    LOG_LEVEL: str = "INFO"
    SENTRY_DSN: str = ""

    # ── Derived helpers ───────────────────────────────────────────────────
    @property
    def is_production(self) -> bool:
        return self.APP_ENV == "production"

    @property
    def is_development(self) -> bool:
        return self.APP_ENV == "development"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return the cached Settings singleton."""
    return Settings()


# Module-level singleton for convenience imports
settings: Settings = get_settings()
