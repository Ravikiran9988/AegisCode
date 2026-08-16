"""
Robust HTTP API Client for the AegisCode frontend.
Implements exponential backoff, health connectivity polling, and error normalization.
"""

from __future__ import annotations

import time
from typing import Any

import requests

from frontend.utils.helpers import _normalize_backend_url

_DEFAULT_HEALTH_TIMEOUT = 10
_DEFAULT_API_TIMEOUT = 30
_COLD_START_RETRY_DELAYS = [0, 2, 4, 8, 15, 30]


def _check_backend_once(
    backend_url: str, timeout: int = _DEFAULT_HEALTH_TIMEOUT
) -> tuple[bool, dict[str, Any], str]:
    """Single health check attempt against GET /health."""
    base_url = _normalize_backend_url(backend_url)
    health_url = f"{base_url}/health"
    try:
        resp = requests.get(health_url, timeout=timeout)
        if resp.status_code == 200:
            data = resp.json()
            if isinstance(data, dict) and data.get("status") in ("ok", "healthy"):
                return True, data, ""
            status_val = data.get("status", "unknown") if isinstance(data, dict) else "unknown"
            return False, data, f"Unexpected health status: {status_val}"
        return False, {}, f"Health endpoint returned HTTP {resp.status_code}"
    except requests.exceptions.Timeout:
        return False, {}, "Connection timed out — the backend may be slow to respond."
    except requests.exceptions.ConnectionError:
        return (
            False, {},
            "Connection refused — the backend may be starting up or unavailable.",
        )
    except Exception as exc:
        return False, {}, f"Health check error: {exc}"


def check_backend_with_retry(
    backend_url: str,
    retry_delays: list[int] = _COLD_START_RETRY_DELAYS,
) -> tuple[bool, dict[str, Any], str]:
    """Check backend connectivity via GET /health with automatic retry and backoff."""
    last_error = ""
    last_data: dict[str, Any] = {}

    for delay in retry_delays:
        if delay > 0:
            time.sleep(delay)

        online, data, err = _check_backend_once(backend_url)
        if online:
            return True, data, ""

        last_error = err
        last_data = data

    return False, last_data, last_error


def _safe_get(
    url: str,
    timeout: int = _DEFAULT_API_TIMEOUT,
    retries: int = 3,
    backoff: float = 1.5,
    **kwargs: Any,
) -> requests.Response | None:
    """GET request with retry for transient network errors."""
    for attempt in range(retries):
        try:
            return requests.get(url, timeout=timeout, **kwargs)
        except (requests.exceptions.Timeout, requests.exceptions.ConnectionError):
            if attempt < retries - 1:
                time.sleep(backoff ** attempt)
        except Exception:
            return None
    return None


def _safe_post(url: str, **kwargs: Any) -> requests.Response | None:
    """POST request with retry for transient network errors."""
    timeout = kwargs.pop("timeout", _DEFAULT_API_TIMEOUT)
    retries = kwargs.pop("retries", 3)
    backoff = kwargs.pop("backoff", 1.5)

    for attempt in range(retries):
        try:
            return requests.post(url, timeout=timeout, **kwargs)
        except (requests.exceptions.Timeout, requests.exceptions.ConnectionError):
            if attempt < retries - 1:
                time.sleep(backoff ** attempt)
        except Exception:
            return None
    return None


def fetch_recent_runs(api_url: str, limit: int = 50) -> list[dict[str, Any]]:
    """Fetch historical runs from the backend database."""
    resp = _safe_get(f"{api_url}/runs?limit={limit}", timeout=10)
    if resp and resp.status_code == 200:
        try:
            data = resp.json()
            if isinstance(data, list):
                return data
        except Exception:
            pass
    return []


def fetch_run_status(api_url: str, run_id: str) -> dict[str, Any] | None:
    """Fetch live run status and summary."""
    resp = _safe_get(f"{api_url}/runs/{run_id}/status", timeout=15)
    if resp and resp.status_code == 200:
        try:
            return resp.json()
        except Exception:
            pass
    return None


def fetch_run_results(api_url: str, run_id: str) -> dict[str, Any] | None:
    """Fetch detailed iteration results and agent traces."""
    resp = _safe_get(f"{api_url}/runs/{run_id}/results", timeout=15)
    if resp and resp.status_code == 200:
        try:
            return resp.json()
        except Exception:
            pass
    return None
