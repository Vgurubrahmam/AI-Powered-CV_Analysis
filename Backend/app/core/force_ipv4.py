"""Force Python to resolve DNS using IPv4 (AF_INET) only.

Many ISPs and local networks cannot route IPv6 traffic, causing connection
timeouts when asyncpg resolves Supabase hostnames to AAAA (IPv6) records.
Importing this module patches ``socket.getaddrinfo`` so that **all** DNS
lookups in the process prefer IPv4 addresses.

Import this module as early as possible — before SQLAlchemy engines, asyncpg
connections, or any other networking code runs.
"""

from __future__ import annotations

import socket

_original_getaddrinfo = socket.getaddrinfo


def _ipv4_only_getaddrinfo(host, port, family=0, type=0, proto=0, flags=0):
    """Wrapper that forces ``family=AF_INET`` (IPv4) for all lookups."""
    return _original_getaddrinfo(host, port, socket.AF_INET, type, proto, flags)


def patch() -> None:
    """Apply the IPv4-only monkey-patch (idempotent)."""
    if socket.getaddrinfo is not _ipv4_only_getaddrinfo:
        socket.getaddrinfo = _ipv4_only_getaddrinfo  # type: ignore[assignment]


# Auto-patch on import
patch()
