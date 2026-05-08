"""Master API router — mounts all v1 sub-routers."""

from __future__ import annotations

from fastapi import APIRouter

from app.api.v1 import auth, users, resumes, jobs, analysis, feedback, admin, webhooks

api_router = APIRouter()

# ── v1 routes ─────────────────────────────────────────────────────────────────
api_router.include_router(auth.router,     prefix="/v1/auth",     tags=["auth"])
api_router.include_router(users.router,    prefix="/v1/users",    tags=["users"])
api_router.include_router(resumes.router,  prefix="/v1/resumes",  tags=["resumes"])
api_router.include_router(jobs.router,     prefix="/v1/jobs",     tags=["jobs"])
api_router.include_router(analysis.router, prefix="/v1/analysis", tags=["analysis"])
api_router.include_router(feedback.router, prefix="/v1/feedback",  tags=["feedback"])
api_router.include_router(admin.router,    prefix="/v1/admin",    tags=["admin"])
api_router.include_router(webhooks.router, prefix="/v1/webhooks", tags=["webhooks"])
