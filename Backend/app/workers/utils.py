"""Shared async helper for Celery workers.

All tasks MUST use this shared event loop to avoid the
'Future attached to a different loop' error when the DB
connection pool is shared across tasks.
"""

from __future__ import annotations

import asyncio

_worker_loop: asyncio.AbstractEventLoop | None = None


def run_in_worker_loop(coro):
    """Run async code on a single persistent loop per worker process."""
    global _worker_loop

    if _worker_loop is None or _worker_loop.is_closed():
        _worker_loop = asyncio.new_event_loop()
        asyncio.set_event_loop(_worker_loop)

    return _worker_loop.run_until_complete(coro)
