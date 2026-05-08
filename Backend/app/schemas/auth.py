"""Auth Pydantic schemas."""

from __future__ import annotations

from pydantic import BaseModel, EmailStr, Field


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)


class TokenPair(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int       # seconds
    refresh_token: str    # returned in response body (store in memory, NOT localStorage)


class RefreshRequest(BaseModel):
    refresh_token: str


class LogoutRequest(BaseModel):
    access_token: str
