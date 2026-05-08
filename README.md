# 🧠 AI-Powered CV Analysis Platform

> Enterprise-grade AI resume analysis & ATS scoring platform.  
> **Backend** (FastAPI + PostgreSQL + Celery) · **Frontend** (React + Vite + Tailwind)

---

## Quick Start

### 1 — Backend

```powershell
cd Backend

# Create & activate virtual environment
python -m venv .venv
.\.venv\Scripts\activate        # PowerShell
# OR: .\.venv\Scripts\activate.bat   # CMD

# Install dependencies
pip install -r requirements.txt
python -m spacy download en_core_web_sm

# Configure environment
copy .env.example .env          # then fill in your values

# Run database migrations
.\.venv\Scripts\alembic.exe upgrade head

# Start the API server
uvicorn app.main:app --reload --reload-dir app --port 8000
```

API docs → http://localhost:8000/docs

### 2 — Frontend

```powershell
cd Frontend
npm install
npm run dev
```

App → http://localhost:5173

---

## Full Documentation

- 📖 [Backend README](./Backend/README.md) — setup, API reference, AI pipeline, troubleshooting
- 📖 [Frontend README](./Frontend/README.md) — setup, pages, architecture, build

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│  Browser  →  React SPA (Vite, port 5173)                    │
│              /api/* proxied to → FastAPI (port 8000)         │
└────────────────────────────┬────────────────────────────────┘
                             │
┌────────────────────────────▼────────────────────────────────┐
│  FastAPI (uvicorn)                                           │
│  ├── /api/v1/auth    JWT auth (register/login/refresh)      │
│  ├── /api/v1/users   Profile management                     │
│  ├── /api/v1/resumes Upload + parsed data                   │
│  ├── /api/v1/jobs    Job description management             │
│  ├── /api/v1/analysis Pipeline trigger + results           │
│  └── /api/v1/feedback AI feedback items                    │
└──────┬────────────────────────────────────┬─────────────────┘
       │                                    │
┌──────▼──────────┐               ┌────────▼────────┐
│  PostgreSQL      │               │  Redis           │
│  (Supabase)      │               │  Token blacklist │
│  Users, Resumes  │               │  Celery broker   │
│  Jobs, Analysis  │               │  Rate limiting   │
│  pgvector        │               └─────────────────┘
└─────────────────┘
       │
┌──────▼──────────────────────────────────────────────────────┐
│  Celery Workers                                              │
│  ├── parsing queue   → PDF/DOCX extraction, OCR fallback    │
│  ├── embeddings queue → SBERT all-mpnet-base-v2             │
│  ├── llm queue       → OpenRouter / OpenAI / Anthropic      │
│  └── default queue   → scoring, feedback generation         │
└─────────────────────────────────────────────────────────────┘
```
