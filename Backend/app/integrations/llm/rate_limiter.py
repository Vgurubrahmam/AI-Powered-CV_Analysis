"""LLM rate limiter — token budget tracker backed by Redis.

Tracks per-user and per-model token consumption with sliding 1-minute
and daily windows. Raises RateLimitExceeded if a budget is exceeded.

Design:
  - Two Redis keys per scope: minute:<scope> and day:<scope>
  - INCRBY + EXPIRE for atomic sliding-window approximation
  - Gracefully skips rate limiting if Redis is unavailable (fail-open)
"""

from __future__ import annotations

import time
from typing import Optional

import structlog

from app.core.constants import TOKEN_LIMITS

log = structlog.get_logger(__name__)

# Default budgets (tokens)
DEFAULT_MINUTE_BUDGET = 40_000    # ~40k tokens/min
DEFAULT_DAY_BUDGET = 500_000      # ~500k tokens/day

# Key TTLs (seconds)
MINUTE_TTL = 70   # slightly over 60s to handle clock drift
DAY_TTL = 86_500  # slightly over 24h


class RateLimitExceeded(Exception):
    """Raised when a token budget has been exhausted."""

    def __init__(self, scope: str, window: str, used: int, limit: int) -> None:
        self.scope = scope
        self.window = window
        self.used = used
        self.limit = limit
        super().__init__(
            f"Token rate limit exceeded for scope='{scope}' window={window}: "
            f"{used}/{limit} tokens used."
        )


class LLMRateLimiter:
    """Redis-backed token budget tracker.

    Args:
        redis: An async Redis client (aioredis/redis-py async).
        minute_limit: Max tokens per minute per scope.
        day_limit: Max tokens per day per scope.
    """

    def __init__(
        self,
        redis,
        minute_limit: int = DEFAULT_MINUTE_BUDGET,
        day_limit: int = DEFAULT_DAY_BUDGET,
    ) -> None:
        self._redis = redis
        self._minute_limit = minute_limit
        self._day_limit = day_limit

    async def check_and_consume(
        self,
        tokens: int,
        scope: str = "global",
    ) -> None:
        """Record token usage and raise RateLimitExceeded if over budget.

        Args:
            tokens: Estimated tokens for this request.
            scope: Rate-limit bucket key (e.g. "user:<uuid>" or "global").

        Raises:
            RateLimitExceeded: If minute or day budget exceeded.
        """
        if not self._redis:
            return  # fail-open

        try:
            minute_key = f"rl:llm:min:{scope}"
            day_key = f"rl:llm:day:{scope}"

            # Atomic increment + TTL set (pipeline for efficiency)
            pipe = self._redis.pipeline()
            pipe.incrby(minute_key, tokens)
            pipe.expire(minute_key, MINUTE_TTL)
            pipe.incrby(day_key, tokens)
            pipe.expire(day_key, DAY_TTL)
            results = await pipe.execute()

            minute_used = results[0]
            day_used = results[2]

            if minute_used > self._minute_limit:
                raise RateLimitExceeded(scope, "minute", minute_used, self._minute_limit)
            if day_used > self._day_limit:
                raise RateLimitExceeded(scope, "day", day_used, self._day_limit)

            log.debug(
                "llm_tokens_consumed",
                scope=scope,
                tokens=tokens,
                minute_total=minute_used,
                day_total=day_used,
            )

        except RateLimitExceeded:
            raise
        except Exception as exc:
            # Redis failure → fail-open (log but don't block requests)
            log.warning("rate_limiter_redis_error", error=str(exc))

    async def get_remaining(self, scope: str = "global") -> dict:
        """Return remaining token budget for a scope."""
        if not self._redis:
            return {"minute": self._minute_limit, "day": self._day_limit}
        try:
            minute_key = f"rl:llm:min:{scope}"
            day_key = f"rl:llm:day:{scope}"
            pipe = self._redis.pipeline()
            pipe.get(minute_key)
            pipe.get(day_key)
            min_used, day_used = await pipe.execute()
            return {
                "minute": self._minute_limit - int(min_used or 0),
                "day": self._day_limit - int(day_used or 0),
            }
        except Exception:
            return {"minute": self._minute_limit, "day": self._day_limit}


def estimate_tokens(text: str) -> int:
    """Rough token count estimate: ~4 characters per token (GPT-4 heuristic)."""
    return max(1, len(text) // 4)
