"""
Robust HTTP API Client for the AegisCode frontend.
Includes automatic retries for backend cold starts and rate limit handling.
"""

from __future__ import annotations

import time

import requests
import streamlit as st

try:
    from frontend.utils.helpers import _normalize_backend_url
except ImportError:
    from utils.helpers import _normalize_backend_url

_COLD_START_RETRY_DELAYS = [0, 2, 4, 8, 12]


def _get_auth_headers() -> dict[str, str]:
    """Get Authorization header if an auth token is stored in Streamlit session state."""
    token = st.session_state.get("auth_token") if hasattr(st, "session_state") else None
    if token:
        return {"Authorization": f"Bearer {token}"}
    return {}


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
    headers = _get_auth_headers()
    if "headers" in kwargs:
        headers.update(kwargs.pop("headers"))
    try:
        return requests.get(url, timeout=timeout, headers=headers, **kwargs)
    except Exception:
        return None


def _safe_post(url: str, timeout: int = 30, **kwargs) -> requests.Response | None:
    """Safely execute an HTTP POST request catching connection exceptions."""
    headers = _get_auth_headers()
    if "headers" in kwargs:
        headers.update(kwargs.pop("headers"))
    try:
        return requests.post(url, timeout=timeout, headers=headers, **kwargs)
    except Exception:
        return None


def _format_http_error(resp: requests.Response, default_msg: str) -> str:
    """Format user-friendly error message from HTTP response."""
    try:
        data = resp.json()
        if isinstance(data, dict) and data.get("detail"):
            detail = data["detail"]
            if isinstance(detail, list):
                msgs = [d.get("msg", str(d)) for d in detail if isinstance(d, dict)]
                return ", ".join(msgs) if msgs else "Please check the email and password fields."
            return str(detail)
    except Exception:
        pass

    if resp.status_code == 409:
        return "An account with this email address already exists."
    if resp.status_code == 422:
        return "Please check the email and password fields."
    if resp.status_code == 400:
        return "Invalid input data. Please check the fields and try again."
    if resp.status_code == 401:
        return "Invalid email or password."
    if resp.status_code == 403:
        return "Account access is restricted."
    if resp.status_code == 404:
        return "Authentication service endpoint not found."
    if resp.status_code >= 500:
        return "Something went wrong on the server. Please try again."
    return default_msg


def api_register(
    api_url: str,
    full_name: str,
    email: str,
    password: str,
    confirm_password: str,
) -> tuple[bool, dict | str]:
    """Register a new account on backend API."""
    norm_url = _normalize_backend_url(api_url)
    clean_email = email.strip().lower()
    clean_name = full_name.strip()
    payload = {
        "full_name": clean_name,
        "name": clean_name,
        "email": clean_email,
        "password": password,
        "confirm_password": confirm_password,
    }
    target_url = f"{norm_url}/api/auth/register"
    try:
        resp = requests.post(target_url, json=payload, timeout=15)
        if resp.status_code == 201:
            return True, resp.json()
        err = _format_http_error(resp, "Registration failed")
        return False, err
    except (requests.exceptions.ConnectionError, requests.exceptions.Timeout):
        return False, "Unable to connect to AegisCode services. Please try again."
    except Exception as exc:
        return False, str(exc)


def api_login(
    api_url: str,
    email: str,
    password: str,
) -> tuple[bool, dict | str]:
    """Authenticate with backend API."""
    norm_url = _normalize_backend_url(api_url)
    clean_email = email.strip().lower()
    payload = {"email": clean_email, "password": password}
    target_url = f"{norm_url}/api/auth/login"
    try:
        resp = requests.post(target_url, json=payload, timeout=15)
        if resp.status_code == 200:
            return True, resp.json()
        err = _format_http_error(resp, "Invalid email or password.")
        return False, err
    except (requests.exceptions.ConnectionError, requests.exceptions.Timeout):
        return False, "Unable to connect to AegisCode services. Please try again."
    except Exception as exc:
        return False, str(exc)


def api_get_current_user(api_url: str, token: str) -> dict | None:
    """Fetch current user profile using JWT token."""
    norm_url = _normalize_backend_url(api_url)
    target_url = f"{norm_url}/api/auth/me"
    try:
        resp = requests.get(
            target_url,
            headers={"Authorization": f"Bearer {token}"},
            timeout=10,
        )
        if resp.status_code == 200:
            return resp.json()
        return None
    except Exception:
        return None


def fetch_recent_runs(api_url: str, limit: int = 50) -> list[dict]:
    """Fetch real historical repair runs from backend API."""
    res = _safe_get(f"{api_url}/runs?limit={limit}", timeout=10)
    if res and res.status_code == 200:
        try:
            data = res.json()
            if isinstance(data, list):
                return data
            if isinstance(data, dict):
                return data.get("runs", data.get("items", []))
            return []
        except Exception:
            return []
    return []


def fetch_active_runs(api_url: str, limit: int = 50) -> list[dict]:
    """Fetch currently active / running repair runs from backend API."""
    res = _safe_get(f"{api_url}/runs/active?limit={limit}", timeout=10)
    if res and res.status_code == 200:
        try:
            data = res.json()
            if isinstance(data, list):
                return data
            if isinstance(data, dict):
                return data.get("runs", data.get("items", []))
            return []
        except Exception:
            return []
    return []


def fetch_history_runs(
    api_url: str,
    limit: int = 50,
    status: str | None = None,
) -> list[dict]:
    """Fetch completed / historical repair runs with optional status filter."""
    url = f"{api_url}/runs/history?limit={limit}"
    if status:
        url += f"&status={status}"
    res = _safe_get(url, timeout=10)
    if res and res.status_code == 200:
        try:
            data = res.json()
            if isinstance(data, list):
                return data
            if isinstance(data, dict):
                return data.get("runs", data.get("items", []))
            return []
        except Exception:
            return []
    return fetch_recent_runs(api_url, limit=limit)


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
