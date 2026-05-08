"""ClamAV antivirus scanner — file scanning via clamd socket/TCP.

Integration strategy:
  - Connects to ClamAV daemon (clamd) via TCP socket
  - Gracefully degrades: if ClamAV is not running or not configured,
    scanning is SKIPPED (logged as warning, not an error)
  - Raises VirusDetectedError if a threat is found
  - Timeouts are strict: 10s connection, 30s scan max

Configuration:
  CLAMAV_HOST: hostname of clamd (default "localhost")
  CLAMAV_PORT: TCP port (default 3310)

If CLAMAV_HOST is empty, the scanner is disabled entirely.
"""

from __future__ import annotations

import asyncio
import io
import struct
from dataclasses import dataclass
from typing import Optional

import structlog

from app.config import settings

log = structlog.get_logger(__name__)

# ClamAV protocol constants
_INSTREAM_CHUNK_SIZE = 1024 * 64   # 64 KB chunks
_CONNECT_TIMEOUT = 10.0
_SCAN_TIMEOUT = 30.0


class VirusDetectedError(Exception):
    """Raised when ClamAV detects a threat in the uploaded file."""

    def __init__(self, threat_name: str) -> None:
        self.threat_name = threat_name
        super().__init__(f"Virus/malware detected: {threat_name}")


@dataclass
class ScanResult:
    """Result of an AV scan."""
    scanned: bool                   # False if ClamAV unavailable
    clean: bool                     # True if no threats found
    threat_name: Optional[str]      # Name of threat if found
    scanner: str                    # "clamav" | "skipped"
    bytes_scanned: int


async def scan_bytes(file_bytes: bytes) -> ScanResult:
    """Scan file bytes for viruses using ClamAV.

    Args:
        file_bytes: Raw file content to scan.

    Returns:
        ScanResult. If ClamAV is unavailable, returns a SKIPPED result
        rather than raising — callers should log this but not block uploads.

    Raises:
        VirusDetectedError: If a threat is detected.
    """
    if not settings.CLAMAV_HOST:
        log.debug("clamav_not_configured_skipping")
        return ScanResult(
            scanned=False,
            clean=True,
            threat_name=None,
            scanner="skipped",
            bytes_scanned=0,
        )

    try:
        result = await asyncio.wait_for(
            _scan_via_clamd(file_bytes),
            timeout=_SCAN_TIMEOUT,
        )
        return result
    except asyncio.TimeoutError:
        log.warning("clamav_scan_timeout", host=settings.CLAMAV_HOST, port=settings.CLAMAV_PORT)
        return ScanResult(
            scanned=False, clean=True, threat_name=None,
            scanner="timeout", bytes_scanned=len(file_bytes),
        )
    except (ConnectionRefusedError, OSError) as exc:
        log.warning("clamav_unavailable", error=str(exc))
        return ScanResult(
            scanned=False, clean=True, threat_name=None,
            scanner="unavailable", bytes_scanned=0,
        )


async def _scan_via_clamd(file_bytes: bytes) -> ScanResult:
    """Send file bytes to clamd via INSTREAM protocol."""
    reader, writer = await asyncio.wait_for(
        asyncio.open_connection(settings.CLAMAV_HOST, settings.CLAMAV_PORT),
        timeout=_CONNECT_TIMEOUT,
    )

    try:
        # Send INSTREAM command
        writer.write(b"zINSTREAM\0")

        # Send data in chunks: 4-byte big-endian length + chunk
        offset = 0
        total = len(file_bytes)
        while offset < total:
            chunk = file_bytes[offset: offset + _INSTREAM_CHUNK_SIZE]
            writer.write(struct.pack("!I", len(chunk)))
            writer.write(chunk)
            offset += len(chunk)

        # Terminate stream
        writer.write(struct.pack("!I", 0))
        await writer.drain()

        # Read response
        response_raw = await reader.read(4096)
        response = response_raw.decode("utf-8", errors="replace").strip().rstrip("\0")

    finally:
        writer.close()
        try:
            await writer.wait_closed()
        except Exception:
            pass

    log.debug("clamav_response", response=response)

    # Parse clamd response: "stream: OK" or "stream: <THREAT_NAME> FOUND"
    if response.endswith("OK"):
        return ScanResult(
            scanned=True,
            clean=True,
            threat_name=None,
            scanner="clamav",
            bytes_scanned=len(file_bytes),
        )
    elif "FOUND" in response:
        # Extract threat name: "stream: Eicar-Test-Signature FOUND"
        parts = response.split(":", 1)
        threat = parts[1].strip().replace(" FOUND", "") if len(parts) > 1 else "unknown"
        log.error("virus_detected", threat=threat, bytes=len(file_bytes))
        raise VirusDetectedError(threat)
    else:
        log.warning("clamav_unexpected_response", response=response)
        # Unknown response — fail-open (don't block uploads)
        return ScanResult(
            scanned=True,
            clean=True,
            threat_name=None,
            scanner="clamav",
            bytes_scanned=len(file_bytes),
        )


async def ping_clamav() -> bool:
    """Check if ClamAV daemon is reachable. Returns True if available."""
    if not settings.CLAMAV_HOST:
        return False
    try:
        reader, writer = await asyncio.wait_for(
            asyncio.open_connection(settings.CLAMAV_HOST, settings.CLAMAV_PORT),
            timeout=3.0,
        )
        writer.write(b"zPING\0")
        await writer.drain()
        pong = await reader.read(10)
        writer.close()
        return b"PONG" in pong
    except Exception:
        return False
