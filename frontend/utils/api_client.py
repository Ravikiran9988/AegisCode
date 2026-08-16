"""
Robust HTTP API Client for the AegisCode frontend.
Includes automatic retries for backend cold starts and rate limit handling.
"""

from __future__ import annotations

import time

import requests

try:
    from frontend.utils.helpers import _normalize_backend_url
except ImportError:
    from utils.helpers import _normalize_backend_url

_COLD_START_RETRY_DELAYS = [0, 2, 4, 8, 12]


def _check_backend_once(backend_url: str, timeout: int = 10) -> tuple[bool, dict, str]:
    """Single attempt to check backend /health endpoint."""
    normalized_url = _normalize_backend_url(backend_url)
    health_url = f"{normalized_url}/health"
    try:
        resp = requests.get(health_url, timeout=timeout)
        if resp.status_code == 200:
            try:
                data = resp.json()
                if isinstance(data, dict):
                    return True, data, ""
                return True, {}, ""
            except Exception:
                return True, {}, ""
        return False, {}, f"Backend returned HTTP {resp.status_code}"
    except requests.exceptions.ConnectionError:
        return False, {}, "Cannot connect to backend (Connection Refused)"
    except requests.exceptions.Timeout:
        return False, {}, f"Backend timed out after {timeout}s"
    except Exception as exc:
        return False, {}, f"Backend error: {str(exc)}"


def check_backend_with_retry(
    backend_url: str,
    retry_delays: list[int] = _COLD_START_RETRY_DELAYS,
) -> tuple[bool, dict, str]:
    """Check backend health with automatic retry delays to accommodate cold starts."""
    last_err = ""
    for idx, delay in enumerate(retry_delays):
        if delay > 0:
            time.sleep(delay)
        timeout = 10 if idx == 0 else 15
        online, data, err_msg = _check_backend_once(backend_url, timeout=timeout)
        if online:
            return True, data, ""
        last_err = err_msg
    return False, {}, last_err


def _safe_get(url: str, timeout: int = 30, **kwargs) -> requests.Response | None:
    """Safely execute an HTTP GET request catching connection exceptions."""
    try:
        return requests.get(url, timeout=timeout, **kwargs)
    except Exception:
        return None


def _safe_post(url: str, timeout: int = 30, **kwargs) -> requests.Response | None:
    """Safely execute an HTTP POST request catching connection exceptions."""
    try:
        return requests.post(url, timeout=timeout, **kwargs)
    except Exception:
        return None


def fetch_recent_runs(api_url: str, limit: int = 50) -> list[dict]:
    """Fetch real historical repair runs from backend API."""
    res = _safe_get(f"{api_url}/runs?limit={limit}", timeout=10)
    if res and res.status_code == 200:
        try:
            return res.json().get("runs", [])
        except Exception:
            return []
    return []


def fetch_run_status(api_url: str, run_id: str) -> dict | None:
    """Fetch real-time status of a repair run."""
    res = _safe_get(f"{api_url}/runs/{run_id}/status", timeout=10)
    if res and res.status_code == 200:
        try:
            return res.json()
        except Exception:
            return None
    return None


def fetch_run_results(api_url: str, run_id: str) -> dict | None:
    """Fetch comprehensive iteration details and telemetry for a repair run."""
    res = _safe_get(f"{api_url}/runs/{run_id}/results", timeout=10)
    if res and res.status_code == 200:
        try:
            return res.json()
        except Exception:
            return None
    return None
