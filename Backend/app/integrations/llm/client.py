"""Unified LLM client — NVIDIA primary + OpenRouter/OpenAI/Anthropic fallback.

Architecture:
  - Primary: NVIDIA AI (OpenAI-compatible endpoint)
  - Fallback 1: OpenRouter (single endpoint, access to many models)
  - Fallback 2: OpenAI direct (if OPENAI_API_KEY set)
  - Fallback 3: Anthropic direct (if ANTHROPIC_API_KEY set)
  - All retries use exponential backoff via the retry utility
  - Rate limiting is applied before each call if a limiter is injected

Usage:
    client = get_llm_client()
    response = await client.complete(prompt="...", model="nvidia/...")
"""

from __future__ import annotations

import asyncio
import time
from functools import lru_cache
from typing import Any, Optional

import httpx
import structlog

from app.config import settings
from app.utils.retry import retry as async_retry

log = structlog.get_logger(__name__)

# Connection pool shared across all requests
_HTTP_CLIENT: httpx.AsyncClient | None = None


def _get_http_client() -> httpx.AsyncClient:
    global _HTTP_CLIENT
    if _HTTP_CLIENT is None or _HTTP_CLIENT.is_closed:
        _HTTP_CLIENT = httpx.AsyncClient(
            timeout=httpx.Timeout(connect=5.0, read=120.0, write=10.0, pool=5.0),
            limits=httpx.Limits(max_connections=20, max_keepalive_connections=10),
        )
    return _HTTP_CLIENT


class LLMClient:
    """Unified async LLM client with provider fallback and retry."""

    def __init__(
        self,
        rate_limiter=None,
        scope: str = "global",
    ) -> None:
        self._rate_limiter = rate_limiter
        self._scope = scope

    async def complete(
        self,
        prompt: str,
        model: str | None = None,
        max_tokens: int = 2000,
        temperature: float = 0.2,
        system: str | None = None,
    ) -> str:
        """Send a completion request and return the response text.

        Tries providers in order: NVIDIA → OpenRouter → OpenAI → Anthropic.
        Raises the last exception if all providers fail.
        """
        model = model or settings.NVIDIA_DEFAULT_MODEL

        # Consume token budget before making request
        if self._rate_limiter:
            from app.integrations.llm.rate_limiter import estimate_tokens
            estimated = estimate_tokens(prompt) + max_tokens
            await self._rate_limiter.check_and_consume(estimated, self._scope)

        last_exc: Exception | None = None

        # ── Provider 1: NVIDIA AI ─────────────────────────────────────────────
        if settings.NVIDIA_API_KEY.get_secret_value():
            try:
                nvidia_model = _resolve_nvidia_model(model)
                return await self._nvidia_complete(prompt, nvidia_model, max_tokens, temperature, system)
            except Exception as exc:
                log.warning("nvidia_failed", error=str(exc), model=model)
                last_exc = exc

        # ── Provider 2: OpenRouter ────────────────────────────────────────────
        if settings.OPENROUTER_API_KEY.get_secret_value():
            try:
                return await self._openrouter_complete(prompt, model, max_tokens, temperature, system)
            except Exception as exc:
                log.warning("openrouter_failed", error=str(exc), model=model)
                last_exc = exc

        # ── Provider 3: OpenAI direct ─────────────────────────────────────────
        if settings.OPENAI_API_KEY.get_secret_value():
            try:
                oai_model = _map_to_openai_model(model)
                return await self._openai_complete(prompt, oai_model, max_tokens, temperature, system)
            except Exception as exc:
                log.warning("openai_fallback_failed", error=str(exc))
                last_exc = exc

        # ── Provider 4: Anthropic direct ──────────────────────────────────────
        if settings.ANTHROPIC_API_KEY.get_secret_value():
            try:
                return await self._anthropic_complete(prompt, max_tokens, temperature, system)
            except Exception as exc:
                log.warning("anthropic_fallback_failed", error=str(exc))
                last_exc = exc

        raise RuntimeError(
            f"All LLM providers failed. Last error: {last_exc}"
        )

    # ── NVIDIA AI ─────────────────────────────────────────────────────────────

    @async_retry(max_retries=3, base_delay=2.0, exceptions=(httpx.HTTPError, RuntimeError))
    async def _nvidia_complete(
        self,
        prompt: str,
        model: str,
        max_tokens: int,
        temperature: float,
        system: str | None,
    ) -> str:
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        headers = {
            "Authorization": f"Bearer {settings.NVIDIA_API_KEY.get_secret_value()}",
            "Content-Type": "application/json",
        }

        payload = {
            "model": model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }

        client = _get_http_client()
        response = await client.post(
            f"{settings.NVIDIA_BASE_URL}/chat/completions",
            json=payload,
            headers=headers,
        )

        if response.status_code == 429:
            retry_after = int(response.headers.get("Retry-After", 30))
            log.warning("nvidia_rate_limited", retry_after=retry_after)
            await asyncio.sleep(retry_after)
            raise RuntimeError("NVIDIA rate limited — retrying")

        if response.status_code >= 400:
            raise RuntimeError(
                f"NVIDIA HTTP {response.status_code}: {response.text[:300]}"
            )

        data = response.json()
        content = data["choices"][0]["message"]["content"]
        usage = data.get("usage", {})
        log.info(
            "llm_complete",
            provider="nvidia",
            model=model,
            prompt_tokens=usage.get("prompt_tokens"),
            completion_tokens=usage.get("completion_tokens"),
        )
        return content

    # ── OpenRouter ────────────────────────────────────────────────────────────

    @async_retry(max_retries=3, base_delay=2.0, exceptions=(httpx.HTTPError, RuntimeError))
    async def _openrouter_complete(
        self,
        prompt: str,
        model: str,
        max_tokens: int,
        temperature: float,
        system: str | None,
    ) -> str:
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        headers = {
            "Authorization": f"Bearer {settings.OPENROUTER_API_KEY.get_secret_value()}",
            "Content-Type": "application/json",
            "HTTP-Referer": settings.APP_URL,
            "X-Title": "ATS-Platform",
        }

        payload = {
            "model": model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }

        client = _get_http_client()
        response = await client.post(
            f"{settings.OPENROUTER_BASE_URL}/chat/completions",
            json=payload,
            headers=headers,
        )

        if response.status_code == 429:
            retry_after = int(response.headers.get("Retry-After", 30))
            log.warning("openrouter_rate_limited", retry_after=retry_after)
            await asyncio.sleep(retry_after)
            raise RuntimeError("OpenRouter rate limited — retrying")

        if response.status_code >= 400:
            raise RuntimeError(
                f"OpenRouter HTTP {response.status_code}: {response.text[:300]}"
            )

        data = response.json()
        content = data["choices"][0]["message"]["content"]
        usage = data.get("usage", {})
        log.info(
            "llm_complete",
            provider="openrouter",
            model=model,
            prompt_tokens=usage.get("prompt_tokens"),
            completion_tokens=usage.get("completion_tokens"),
        )
        return content

    # ── OpenAI ────────────────────────────────────────────────────────────────

    @async_retry(max_retries=2, base_delay=3.0, exceptions=(httpx.HTTPError, RuntimeError))
    async def _openai_complete(
        self,
        prompt: str,
        model: str,
        max_tokens: int,
        temperature: float,
        system: str | None,
    ) -> str:
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        headers = {
            "Authorization": f"Bearer {settings.OPENAI_API_KEY.get_secret_value()}",
            "Content-Type": "application/json",
        }

        payload = {
            "model": model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }

        client = _get_http_client()
        response = await client.post(
            "https://api.openai.com/v1/chat/completions",
            json=payload,
            headers=headers,
        )

        if response.status_code >= 400:
            raise RuntimeError(f"OpenAI HTTP {response.status_code}: {response.text[:300]}")

        data = response.json()
        return data["choices"][0]["message"]["content"]

    # ── Anthropic ─────────────────────────────────────────────────────────────

    @async_retry(max_retries=2, base_delay=3.0, exceptions=(httpx.HTTPError, RuntimeError))
    async def _anthropic_complete(
        self,
        prompt: str,
        max_tokens: int,
        temperature: float,
        system: str | None,
    ) -> str:
        headers = {
            "x-api-key": settings.ANTHROPIC_API_KEY.get_secret_value(),
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json",
        }

        payload: dict[str, Any] = {
            "model": "claude-3-haiku-20240307",
            "max_tokens": max_tokens,
            "temperature": temperature,
            "messages": [{"role": "user", "content": prompt}],
        }
        if system:
            payload["system"] = system

        client = _get_http_client()
        response = await client.post(
            "https://api.anthropic.com/v1/messages",
            json=payload,
            headers=headers,
        )

        if response.status_code >= 400:
            raise RuntimeError(f"Anthropic HTTP {response.status_code}: {response.text[:300]}")

        data = response.json()
        return data["content"][0]["text"]


# ─── Factory ──────────────────────────────────────────────────────────────────

@lru_cache(maxsize=1)
def get_llm_client(scope: str = "global") -> LLMClient:
    """Return a cached LLMClient instance."""
    return LLMClient(rate_limiter=None, scope=scope)


def _resolve_nvidia_model(model: str) -> str:
    """Resolve model name to NVIDIA-compatible model identifier."""
    # If already a NVIDIA model path, use as-is
    if "/" in model and not model.startswith(("openai/", "anthropic/", "deepseek/", "meta-llama/", "google/")):
        return model
    # Map common OpenRouter models to NVIDIA equivalents
    mapping = {
        "google/gemma-3-27b-it:free": "meta/llama-3.1-8b-instruct",
        "meta-llama/llama-3.1-8b-instruct:free": "meta/llama-3.1-8b-instruct",
        "deepseek/deepseek-chat-v3-0324:free": "meta/llama-3.1-70b-instruct",
    }
    return mapping.get(model, settings.NVIDIA_DEFAULT_MODEL)


def _map_to_openai_model(openrouter_model: str) -> str:
    """Map OpenRouter model names to OpenAI equivalents."""
    mapping = {
        "openai/gpt-4o": "gpt-4o",
        "openai/gpt-4o-mini": "gpt-4o-mini",
        "openai/gpt-3.5-turbo": "gpt-3.5-turbo",
    }
    return mapping.get(openrouter_model, "gpt-4o-mini")


async def close_http_client() -> None:
    """Gracefully close the shared HTTP client (call on app shutdown)."""
    global _HTTP_CLIENT
    if _HTTP_CLIENT and not _HTTP_CLIENT.is_closed:
        await _HTTP_CLIENT.aclose()
        _HTTP_CLIENT = None
