"""Schemas package."""
from app.schemas.analysis import (
    AnalysisCreateResponse,
    AnalysisRead,
    AnalysisRequest,
    AnalysisResultRead,
    ScoreBreakdown,
)
from app.schemas.auth import LoginRequest, LogoutRequest, RefreshRequest, TokenPair
from app.schemas.common import APIResponse, CursorPage, HealthCheck
from app.schemas.feedback import FeedbackAcceptRequest, FeedbackItemRead, RewriteRequest, RewriteResult
from app.schemas.job import JDCreate, JDRead, ParsedJDData, ParsedJDRead
from app.schemas.resume import ParsedResumeRead, ResumeRead, ResumeUploadResponse
from app.schemas.user import UserAdminUpdate, UserCreate, UserRead, UserUpdate

__all__ = [
    "APIResponse", "CursorPage", "HealthCheck",
    "LoginRequest", "TokenPair", "RefreshRequest", "LogoutRequest",
    "UserCreate", "UserRead", "UserUpdate", "UserAdminUpdate",
    "ResumeUploadResponse", "ResumeRead", "ParsedResumeRead",
    "JDCreate", "JDRead", "ParsedJDRead", "ParsedJDData",
    "AnalysisRequest", "AnalysisRead", "AnalysisResultRead",
    "AnalysisCreateResponse", "ScoreBreakdown",
    "FeedbackItemRead", "FeedbackAcceptRequest", "RewriteRequest", "RewriteResult",
]
