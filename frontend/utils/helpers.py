"""
Common helper and formatting functions for the AegisCode frontend.
Preserves required helpers for compatibility with tests.
"""

from __future__ import annotations

import re
from datetime import datetime
from typing import Any

import requests


def _normalize_backend_url(url: str) -> str:
    """
    Normalize backend URL by stripping whitespace, trailing slashes,
    and path suffixes like /health or /api.
    """
    u = url.strip().rstrip("/")
    if u.endswith("/health"):
        u = u[:-7].rstrip("/")
    elif u.endswith("/api"):
        u = u[:-4].rstrip("/")
    return u


def _parse_api_error(resp: requests.Response) -> str:
    """Extract a user-friendly error message from an HTTP response."""
    try:
        data = resp.json()
        detail = data.get("detail", "")
        if detail:
            return f"HTTP {resp.status_code}: {detail}"
    except Exception:
        pass
    text = resp.text[:200] if resp.text else "Unknown error"
    return f"HTTP {resp.status_code}: {text}"


def _extract_filename_from_content_disposition(
    resp: requests.Response, run_id: str
) -> str:
    """
    Parse filename from Content-Disposition header.
    Falls back to aegiscode-repaired-{run_id}.zip.
    """
    cd = resp.headers.get("Content-Disposition", "")
    match = re.search(r'filename="([^"]+)"', cd)
    if match:
        return match.group(1)
    return f"aegiscode-repaired-{run_id}.zip"


def _duration_str(started_at: str | None, finished_at: str | None) -> str:
    """Compute human-readable duration from ISO timestamps."""
    if not started_at or not finished_at:
        return "—"
    try:
        def _parse(s: str) -> datetime | None:
            for f in (
                "%Y-%m-%dT%H:%M:%S.%f%z",
                "%Y-%m-%dT%H:%M:%S%z",
                "%Y-%m-%dT%H:%M:%S.%f",
                "%Y-%m-%dT%H:%M:%S",
            ):
                try:
                    return datetime.strptime(s, f)
                except ValueError:
                    continue
            return None

        t0 = _parse(started_at)
        t1 = _parse(finished_at)
        if t0 and t1:
            diff = abs((t1 - t0).total_seconds())
            return f"{diff:.1f}s"
    except Exception:
        pass
    return "—"


def _detect_rate_limit_error(final_summary: str | None) -> bool:
    """
    Detect whether the run's final_summary indicates an LLM
    rate-limit issue (429) for openai/gpt-oss-120b.
    """
    if not final_summary:
        return False
    s = final_summary.lower()
    keywords = (
        "rate_limit",
        "rate limit",
        "429",
        "ratelimit",
        "too many requests",
        "quota",
    )
    return any(k in s for k in keywords)


def format_file_size(size_bytes: int | float | None) -> str:
    """Format bytes into human readable KB/MB string."""
    if size_bytes is None or size_bytes < 0:
        return "—"
    if size_bytes < 1024:
        return f"{size_bytes} B"
    if size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    return f"{size_bytes / (1024 * 1024):.2f} MB"


def format_timestamp(iso_str: str | None) -> str:
    """Format ISO timestamp into clean UI date and time."""
    if not iso_str:
        return "—"
    try:
        dt = datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
        return dt.strftime("%b %d, %Y • %H:%M:%S")
    except Exception:
        return str(iso_str)[:19]


def safe_get_nested(data: dict[str, Any], *keys: str, default: Any = None) -> Any:
    """Safely traverse nested dictionary keys."""
    curr = data
    for k in keys:
        if not isinstance(curr, dict):
            return default
        curr = curr.get(k)
        if curr is None:
            return default
    return curr
