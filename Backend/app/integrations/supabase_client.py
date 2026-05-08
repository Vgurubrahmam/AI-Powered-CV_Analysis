"""Supabase client helpers for FastAPI services."""

from __future__ import annotations

from functools import lru_cache

from supabase import Client, create_client

from app.config import settings


@lru_cache(maxsize=1)
def get_supabase_client() -> Client:
    """Return a cached Supabase client built from environment settings."""
    supabase_url = settings.SUPABASE_URL
    supabase_key = settings.SUPABASE_ANON_KEY.get_secret_value()

    if not supabase_url or not supabase_key:
        raise RuntimeError("Missing SUPABASE_URL or SUPABASE_ANON_KEY in environment.")

    return create_client(supabase_url, supabase_key)

