"""Robust HTTP API Client for the AegisCode frontend."""
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
    """Build auth/guest identity headers for API requests."""
    headers: dict[str, str] = {}
    token = st.session_state.get("auth_token") if hasattr(st, "session_state") else None
    if token:
        headers["Authorization"] = f"Bearer {token}"
    guest_session_id = st.session_state.get("guest_session_id") if hasattr(st, "session_state") else None
    if guest_session_id and st.session_state.get("guest_mode") and not token:
        headers["X-Guest-Session-ID"] = guest_session_id
    return headers


def _check_backend_once(backend_url: str, timeout: int = 10) -> tuple[bool, dict, str]:
    normalized_url = _normalize_backend_url(backend_url)
    try:
        resp = requests.get(f"{normalized_url}/health", timeout=timeout)
        if resp.status_code == 200:
            try:
                data = resp.json()
                return True, data if isinstance(data, dict) else {}, ""
            except Exception:
                return True, {}, ""
        return False, {}, f"Backend returned HTTP {resp.status_code}"
    except requests.exceptions.ConnectionError:
        return False, {}, "Cannot connect to backend (Connection Refused)"
    except requests.exceptions.Timeout:
        return False, {}, f"Backend timed out after {timeout}s"
    except Exception as exc:
        return False, {}, f"Backend error: {str(exc)}"


def check_backend_with_retry(backend_url: str, retry_delays: list[int] = _COLD_START_RETRY_DELAYS) -> tuple[bool, dict, str]:
    """Check backend only when entering the authenticated/guest workspace."""
    if not st.session_state.get("auth_token") and not st.session_state.get("guest_mode"):
        return False, {}, "Backend check deferred until workspace entry"
    last_err = ""
    with st.spinner("Connecting to AegisCode backend…"):
        for idx, delay in enumerate(retry_delays):
            if delay:
                time.sleep(delay)
            online, data, err_msg = _check_backend_once(backend_url, timeout=10 if idx == 0 else 15)
            if online:
                return True, data, ""
            last_err = err_msg
    return False, {}, last_err


def _safe_get(url: str, timeout: int = 30, **kwargs) -> requests.Response | None:
    headers = _get_auth_headers()
    if "headers" in kwargs:
        headers.update(kwargs.pop("headers"))
    try:
        return requests.get(url, timeout=timeout, headers=headers, **kwargs)
    except Exception:
        return None


def _safe_post(url: str, timeout: int = 30, **kwargs) -> requests.Response | None:
    headers = _get_auth_headers()
    if "headers" in kwargs:
        headers.update(kwargs.pop("headers"))
    try:
        return requests.post(url, timeout=timeout, headers=headers, **kwargs)
    except Exception:
        return None


def api_register(api_url: str, full_name: str, email: str, password: str, confirm_password: str) -> tuple[bool, dict | str]:
    norm_url = _normalize_backend_url(api_url)
    payload = {"full_name": full_name.strip(), "name": full_name.strip(), "email": email.strip().lower(), "password": password, "confirm_password": confirm_password}
    try:
        resp = requests.post(f"{norm_url}/api/auth/register", json=payload, timeout=15)
        if resp.status_code == 201:
            return True, resp.json()
        return False, _format_http_error(resp, "Registration failed")
    except (requests.exceptions.ConnectionError, requests.exceptions.Timeout):
        return False, "Unable to connect to AegisCode services. Please try again."
    except Exception as exc:
        return False, str(exc)


def api_login(api_url: str, email: str, password: str) -> tuple[bool, dict | str]:
    norm_url = _normalize_backend_url(api_url)
    try:
        resp = requests.post(f"{norm_url}/api/auth/login", json={"email": email.strip().lower(), "password": password}, timeout=15)
        if resp.status_code == 200:
            return True, resp.json()
        return False, _format_http_error(resp, "Invalid email or password.")
    except (requests.exceptions.ConnectionError, requests.exceptions.Timeout):
        return False, "Unable to connect to AegisCode services. Please try again."
    except Exception as exc:
        return False, str(exc)


def api_get_current_user(api_url: str, token: str) -> dict | None:
    try:
        resp = requests.get(f"{_normalize_backend_url(api_url)}/api/auth/me", headers={"Authorization": f"Bearer {token}"}, timeout=10)
        return resp.json() if resp.status_code == 200 else None
    except Exception:
        return None


def api_persist_guest_identity(api_url: str, name: str, session_id: str) -> tuple[bool, dict | str]:
    """Persist the guest identity and return the authoritative guest record."""
    try:
        resp = requests.post(
            f"{_normalize_backend_url(api_url)}/api/guests",
            json={"name": name.strip(), "session_id": session_id},
            timeout=10,
        )
        if resp.status_code == 200:
            return True, resp.json()
        return False, _format_http_error(resp, "Unable to save guest session.")
    except (requests.exceptions.ConnectionError, requests.exceptions.Timeout):
        return False, "Unable to connect to AegisCode services. Please try again."
    except Exception as exc:
        return False, str(exc)


def _format_http_error(resp: requests.Response, default_msg: str) -> str:
    try:
        data = resp.json()
        if isinstance(data, dict) and data.get("detail"):
            detail = data["detail"]
            if isinstance(detail, list):
                return ", ".join(d.get("msg", str(d)) for d in detail if isinstance(d, dict)) or default_msg
            return str(detail)
    except Exception:
        pass
    if resp.status_code == 401:
        return "Invalid email or password."
    if resp.status_code == 403:
        return "Account access is restricted."
    if resp.status_code >= 500:
        return "Something went wrong on the server. Please try again."
    return default_msg


def fetch_recent_runs(api_url: str, limit: int = 50) -> list[dict]:
    res = _safe_get(f"{api_url}/runs?limit={min(max(limit, 1), 100)}", timeout=10)
    if res and res.status_code == 200:
        try:
            data = res.json()
            return data if isinstance(data, list) else data.get("runs", data.get("items", [])) if isinstance(data, dict) else []
        except Exception:
            pass
    return []


def fetch_active_runs(api_url: str, limit: int = 50) -> list[dict]:
    res = _safe_get(f"{api_url}/runs/active?limit={min(max(limit, 1), 100)}", timeout=10)
    if res and res.status_code == 200:
        try:
            data = res.json()
            return data if isinstance(data, list) else data.get("runs", data.get("items", [])) if isinstance(data, dict) else []
        except Exception:
            pass
    return []


def fetch_history_runs(api_url: str, limit: int = 50, status: str | None = None) -> list[dict]:
    url = f"{api_url}/runs/history?limit={min(max(limit, 1), 100)}"
    if status:
        url += f"&status={status}"
    res = _safe_get(url, timeout=10)
    if res and res.status_code == 200:
        try:
            data = res.json()
            return data if isinstance(data, list) else data.get("runs", data.get("items", [])) if isinstance(data, dict) else []
        except Exception:
            pass
    return fetch_recent_runs(api_url, limit=limit)


def fetch_run_status(api_url: str, run_id: str) -> dict | None:
    res = _safe_get(f"{api_url}/runs/{run_id}/status", timeout=10)
    if res and res.status_code == 200:
        try:
            return res.json()
        except Exception:
            pass
    return None


def fetch_run_results(api_url: str, run_id: str) -> dict | None:
    res = _safe_get(f"{api_url}/runs/{run_id}/results", timeout=10)
    if res and res.status_code == 200:
        try:
            return res.json()
        except Exception:
            pass
    return None
