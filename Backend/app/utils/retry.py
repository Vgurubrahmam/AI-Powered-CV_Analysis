"""Exponential backoff retry decorator."""

from __future__ import annotations

import asyncio
import functools
import time
from typing import Any, Callable, Type


def retry(
    *,
    max_retries: int = 3,
    base_delay: float = 2.0,
    exceptions: tuple[Type[Exception], ...] = (Exception,),
    reraise: bool = True,
):
    """Decorator: retry an async function with exponential backoff.

    Args:
        max_retries: Maximum number of retry attempts.
        base_delay: Base delay in seconds (doubles each retry).
        exceptions: Exception types to catch and retry on.
        reraise: If True, re-raise the last exception after retries exhausted.
    """

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            last_exc: Exception | None = None
            for attempt in range(max_retries + 1):
                try:
                    return await func(*args, **kwargs)
                except exceptions as exc:
                    last_exc = exc
                    if attempt < max_retries:
                        delay = base_delay * (2 ** attempt)
                        await asyncio.sleep(delay)
                    else:
                        break
            if reraise and last_exc is not None:
                raise last_exc
            return None

        return wrapper

    return decorator


def retry_sync(
    *,
    max_retries: int = 3,
    base_delay: float = 1.0,
    exceptions: tuple[Type[Exception], ...] = (Exception,),
):
    """Synchronous version of the retry decorator."""

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            last_exc: Exception | None = None
            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except exceptions as exc:
                    last_exc = exc
                    if attempt < max_retries:
                        time.sleep(base_delay * (2 ** attempt))
            if last_exc:
                raise last_exc

        return wrapper

    return decorator
