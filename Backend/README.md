# Backend — AI-Powered CV Analysis Platform

> FastAPI + PostgreSQL + Celery + NVIDIA AI — Enterprise resume analysis & ATS scoring engine.

---

## Table of Contents

- [Tech Stack](#tech-stack)
- [Project Structure](#project-structure)
- [Getting Started](#getting-started)
- [Environment Variables](#environment-variables)
- [API Endpoints](#api-endpoints)
- [AI Analysis Pipeline](#ai-analysis-pipeline)
- [Background Workers](#background-workers)
- [Database Schema](#database-schema)
- [Deployment](#deployment)
- [Troubleshooting](#troubleshooting)

---

## Tech Stack

| Layer             | Technology                                      |
|-------------------|-------------------------------------------------|
| **Framework**     | FastAPI 0.115+ (async, Pydantic v2)             |
| **Database**      | PostgreSQL 15 (Supabase) + SQLAlchemy 2.0 async |
| **Task Queue**    | Celery 5.4 + Redis                              |
| **LLM Provider**  | NVIDIA AI (primary), OpenRouter (fallback)       |
| **Embeddings**    | Sentence-Transformers (all-MiniLM-L6-v2)        |
| **Auth**          | JWT (access + refresh tokens)                   |
| **Observability** | Structlog + Prometheus + Sentry                 |
| **Storage**       | Local filesystem / S3-compatible                |

---

## Project Structure

```
Backend/
├── app/
│   ├── api/                    # HTTP layer
│   │   ├── router.py           # Central router
│   │   └── v1/                 # Versioned endpoints
│   │       ├── auth.py         #   Authentication (login/register/refresh)
│   │       ├── users.py        #   User profile management
│   │       ├── resumes.py      #   Resume upload & listing
│   │       ├── jobs.py         #   Job description CRUD
│   │       ├── analysis.py     #   Analysis trigger & results
│   │       ├── feedback.py     #   AI feedback items
│   │       ├── admin.py        #   Admin operations
│   │       └── webhooks.py     #   Webhook integrations
│   │
│   ├── config.py               # Pydantic Settings (env-driven)
│   ├── dependencies.py         # FastAPI DI (DB sessions, Redis, auth)
│   ├── main.py                 # App factory + lifespan
│   │
│   ├── core/                   # Cross-cutting concerns
│   │   ├── constants.py        #   Enums (AnalysisStatus, FeedbackCategory, etc.)
│   │   ├── exceptions.py       #   Exception hierarchy + handlers
│   │   ├── force_ipv4.py       #   DNS IPv4 patch (Supabase IPv6 workaround)
│   │   ├── logging.py          #   Structlog configuration
│   │   ├── middleware.py       #   Request context (request_id, timing)
│   │   └── security.py        #   JWT encode/decode, password hashing
│   │
│   ├── models/                 # SQLAlchemy ORM models
│   │   ├── base.py             #   Base, UUIDPKMixin, TimestampMixin
│   │   ├── user.py             #   User
│   │   ├── resume.py           #   Resume
│   │   ├── job.py              #   JobDescription
│   │   ├── analysis.py         #   Analysis
│   │   ├── feedback.py         #   FeedbackItem
│   │   ├── audit.py            #   AuditLog
│   │   └── resume_embedding.py #   ResumeEmbedding (pgvector)
│   │
│   ├── schemas/                # Pydantic request/response models
│   │   ├── auth.py             #   LoginRequest, TokenPair
│   │   ├── user.py             #   UserCreate, UserRead
│   │   ├── resume.py           #   ResumeRead, ResumeUploadResponse
│   │   ├── job.py              #   JDCreate, JDRead
│   │   ├── analysis.py         #   AnalysisRequest, AnalysisRead
│   │   ├── feedback.py         #   FeedbackItemRead, RewriteResult
│   │   └── common.py           #   APIResponse[T], CursorPage
│   │
│   ├── repositories/           # Data access layer
│   │   ├── base.py             #   Generic CRUD base repo
│   │   ├── user_repo.py
│   │   ├── resume_repo.py
│   │   ├── job_repo.py
│   │   ├── analysis_repo.py
│   │   └── audit_repo.py
│   │
│   ├── services/               # Business logic layer
│   │   ├── auth_service.py     #   Register, login, refresh, logout
│   │   ├── user_service.py     #   Profile updates
│   │   ├── resume_service.py   #   Upload, parse, list
│   │   ├── job_service.py      #   JD management
│   │   ├── analysis_service.py #   Trigger analysis, fetch results
│   │   ├── feedback_service.py #   Feedback CRUD, rewrite
│   │   ├── storage_service.py  #   File upload/download abstraction
│   │   ├── notification_service.py  # Email + webhook dispatch
│   │   └── audit_service.py    #   Audit trail logging
│   │
│   ├── pipeline/               # AI analysis engine
│   │   ├── orchestrator.py     #   5-stage pipeline runner
│   │   ├── parsing/            #   Resume & JD parsing
│   │   │   ├── resume_parser.py
│   │   │   ├── pdf_extractor.py
│   │   │   ├── docx_extractor.py
│   │   │   ├── field_extractor.py
│   │   │   ├── section_classifier.py
│   │   │   ├── layout_analyzer.py
│   │   │   ├── ocr_fallback.py
│   │   │   └── jd_parser.py
│   │   ├── matching/           #   Skill matching & extraction
│   │   │   ├── keyword_engine.py
│   │   │   ├── semantic_engine.py
│   │   │   ├── skill_extractor.py
│   │   │   ├── skill_taxonomy.py
│   │   │   ├── synonym_expander.py
│   │   │   └── reranker.py
│   │   ├── analysis/           #   Deep analysis modules
│   │   │   ├── experience_analyzer.py
│   │   │   ├── education_analyzer.py
│   │   │   ├── ats_checker.py
│   │   │   ├── impact_scorer.py
│   │   │   └── bias_auditor.py
│   │   ├── scoring/            #   Composite scoring
│   │   │   ├── score_engine.py
│   │   │   ├── weight_configs.py
│   │   │   ├── calibrator.py
│   │   │   └── confidence.py
│   │   └── feedback/           #   Feedback generation
│   │       ├── feedback_generator.py
│   │       ├── priority_ranker.py
│   │       ├── rewrite_engine.py
│   │       └── hallucination_guard.py
│   │
│   ├── integrations/           # External service clients
│   │   ├── llm/                #   LLM provider abstraction
│   │   │   ├── client.py       #     NVIDIA + OpenRouter + fallback
│   │   │   ├── prompt_templates.py
│   │   │   ├── rate_limiter.py
│   │   │   └── structured_output.py
│   │   ├── embeddings/         #   SBERT embedding client
│   │   │   ├── client.py
│   │   │   └── vector_store.py
│   │   ├── storage/            #   File storage (S3/local)
│   │   │   ├── s3_client.py
│   │   │   └── local_client.py
│   │   ├── av_scanner.py       #   ClamAV integration (optional)
│   │   └── supabase_client.py  #   Supabase REST client
│   │
│   ├── workers/                # Celery background tasks
│   │   ├── celery_app.py       #   Celery instance & config
│   │   ├── beat_schedule.py    #   Periodic task schedule
│   │   └── tasks/
│   │       ├── parsing_tasks.py
│   │       ├── analysis_tasks.py
│   │       ├── embedding_tasks.py
│   │       ├── notification_tasks.py
│   │       └── cleanup_tasks.py
│   │
│   └── utils/                  # Shared utilities
│       ├── crypto_utils.py
│       ├── date_utils.py
│       ├── file_utils.py
│       ├── text_utils.py
│       └── retry.py
│
├── migrations/                 # Alembic DB migrations
├── tests/                      # Test suite
│   ├── unit/
│   ├── integration/
│   └── e2e/
├── scripts/                    # Dev/ops scripts
│   └── seed_data.py
├── infra/                      # Docker & Nginx config
│   ├── docker-compose.yml
│   └── nginx/
├── .env.example                # Environment template
├── requirements.txt            # Production dependencies
├── requirements-dev.txt        # Dev/test dependencies
├── Dockerfile
├── Makefile
└── alembic.ini
```

---

## Getting Started

### Prerequisites

- Python 3.11+
- PostgreSQL 15+ (or Supabase account)
- Redis 7+

### Installation

```bash
# 1. Create virtual environment
python -m venv .venv

# 2. Activate it
.\.venv\Scripts\activate          # Windows PowerShell
# source .venv/bin/activate       # macOS/Linux

# 3. Install dependencies
pip install -r requirements.txt

# 4. Configure environment
cp .env.example .env
# Edit .env with your DATABASE_URL, NVIDIA_API_KEY, etc.

# 5. Run the server
uvicorn app.main:app --reload --port 8000
```

### Start Celery Worker

```bash
celery -A app.workers.celery_app worker --pool=solo --loglevel=info -Q parsing,default,llm,embeddings
```

---

## Environment Variables

All config is driven by `.env` (never committed). See [`.env.example`](.env.example) for the full template.

| Variable | Required | Description |
|----------|----------|-------------|
| `DATABASE_URL` | ✅ | PostgreSQL connection (Supabase pooler recommended) |
| `REDIS_URL` | ✅ | Redis connection for Celery & caching |
| `SECRET_KEY` | ✅ | App-level secret (32+ chars) |
| `JWT_SECRET_KEY` | ✅ | JWT signing key (generate with `openssl rand -hex 32`) |
| `NVIDIA_API_KEY` | ✅ | NVIDIA AI API key for LLM calls |
| `ALLOWED_ORIGINS` | ✅ | CORS origins (comma-separated) |
| `ENABLE_REDIS` | ⬜ | Enable/disable Redis (default: `true`) |
| `ENABLE_EMBEDDINGS` | ⬜ | Enable/disable SBERT model (default: `false`) |
| `STORAGE_BACKEND` | ⬜ | `local` or `s3` (default: `local`) |

---

## API Endpoints

Base URL: `http://localhost:8000/api/v1`

| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| `POST` | `/auth/register` | ❌ | Create account |
| `POST` | `/auth/login` | ❌ | Get JWT tokens |
| `POST` | `/auth/refresh` | ❌ | Refresh access token |
| `POST` | `/auth/logout` | ✅ | Blacklist token |
| `GET` | `/users/me` | ✅ | Current user profile |
| `PUT` | `/users/me` | ✅ | Update profile |
| `POST` | `/resumes/upload` | ✅ | Upload resume (PDF/DOCX/TXT) |
| `GET` | `/resumes` | ✅ | List user's resumes |
| `POST` | `/jobs` | ✅ | Create job description |
| `GET` | `/jobs` | ✅ | List job descriptions |
| `POST` | `/analysis` | ✅ | Trigger analysis (async) |
| `GET` | `/analysis` | ✅ | List analyses |
| `GET` | `/analysis/{id}` | ✅ | Get analysis result |
| `GET` | `/analysis/{id}/feedback` | ✅ | Get feedback items |

Interactive docs: http://localhost:8000/docs

---

## AI Analysis Pipeline

The pipeline runs in 5 sequential stages via Celery:

```
┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐
│ PARSING  │ →  │ MATCHING │ →  │ SCORING  │ →  │ ANALYSIS │ →  │ FEEDBACK │
│          │    │          │    │          │    │          │    │          │
│ Resume   │    │ Keyword  │    │ Composite│    │ ATS      │    │ LLM      │
│ JD Parse │    │ Semantic │    │ Score    │    │ Impact   │    │ Generate │
│          │    │ Skills   │    │ Calibrate│    │ Exp/Edu  │    │ Rank     │
└──────────┘    └──────────┘    └──────────┘    └──────────┘    └──────────┘
```

| Stage | Module | Description |
|-------|--------|-------------|
| **Parsing** | `pipeline/parsing/` | PDF/DOCX text extraction, section classification, JD parsing via LLM |
| **Matching** | `pipeline/matching/` | Keyword match, semantic similarity (SBERT), skill extraction |
| **Scoring** | `pipeline/scoring/` | Weighted composite score with role-specific profiles |
| **Analysis** | `pipeline/analysis/` | ATS compatibility, impact scoring, experience/education gaps, bias audit |
| **Feedback** | `pipeline/feedback/` | LLM-generated actionable feedback, priority ranking, hallucination guard |

---

## Background Workers

Celery queues are configured for task isolation:

| Queue | Tasks |
|-------|-------|
| `parsing` | Resume parsing, JD parsing |
| `llm` | LLM-backed analysis tasks |
| `embeddings` | SBERT embedding generation |
| `default` | Scoring, feedback, notifications, cleanup |

---

## Database Schema

Core tables (managed by SQLAlchemy + Alembic):

| Table | Description |
|-------|-------------|
| `users` | User accounts with roles and plan tiers |
| `resumes` | Uploaded resumes with parsed data (JSONB) |
| `job_descriptions` | JD records with parsed requirements |
| `analyses` | Analysis results, scores, status tracking |
| `feedback_items` | Per-analysis AI feedback with accept/reject |
| `resume_embeddings` | pgvector embeddings for semantic search |
| `audit_logs` | Immutable audit trail |

---

## Deployment

### Render

| Setting | Value |
|---------|-------|
| **Root Directory** | `Backend` |
| **Build Command** | `pip install -r requirements.txt` |
| **Start Command** | `uvicorn app.main:app --host 0.0.0.0 --port $PORT` |
| **Python Version** | Set `PYTHON_VERSION=3.11.9` env var |

---

## Troubleshooting

| Issue | Fix |
|-------|-----|
| `TimeoutError` on DB connect | Use Supabase pooler URL. Check `force_ipv4.py` is imported |
| `ModuleNotFoundError` | Ensure `.venv` is activated. Run `pip install -r requirements.txt` |
| Celery tasks stuck | Check Redis is running. Restart worker |
| LLM returning bad JSON | Check `NVIDIA_API_KEY`. Pipeline falls back to rule-based feedback |
