"""Robust HTTP API Client for the AegisCode frontend."""
from __future__ import annotations
import time
import uuid
import requests
import streamlit as st
try:
    from frontend.utils.helpers import _normalize_backend_url
except ImportError:
    from utils.helpers import _normalize_backend_url
_COLD_START_RETRY_DELAYS = [0, 2, 4, 8, 12]

def _get_auth_headers() -> dict[str, str]:
    headers: dict[str, str] = {}
    token = st.session_state.get("auth_token")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    elif st.session_state.get("guest_mode"):
        session_id = st.session_state.get("guest_session_id")
        if not session_id:
            session_id = str(uuid.uuid4())
            st.session_state["guest_session_id"] = session_id
        headers["X-Guest-Session-ID"] = session_id
    return headers

def _check_backend_once(backend_url: str, timeout: int = 10) -> tuple[bool, dict, str]:
    try:
        resp = requests.get(f"{_normalize_backend_url(backend_url)}/health", timeout=timeout)
        if resp.status_code == 200:
            try:
                data = resp.json(); return True, data if isinstance(data, dict) else {}, ""
            except Exception: return True, {}, ""
        return False, {}, f"Backend returned HTTP {resp.status_code}"
    except requests.exceptions.ConnectionError: return False, {}, "Cannot connect to backend (Connection Refused)"
    except requests.exceptions.Timeout: return False, {}, f"Backend timed out after {timeout}s"
    except Exception as exc: return False, {}, f"Backend error: {str(exc)}"

def check_backend_with_retry(backend_url: str, retry_delays: list[int] = _COLD_START_RETRY_DELAYS) -> tuple[bool, dict, str]:
    if not st.session_state.get("auth_token") and not st.session_state.get("guest_mode"):
        return False, {}, "Backend check deferred until workspace entry"
    last_err = ""
    with st.spinner("Connecting to AegisCode backend…"):
        for idx, delay in enumerate(retry_delays):
            if delay: time.sleep(delay)
            online, data, err_msg = _check_backend_once(backend_url, timeout=10 if idx == 0 else 15)
            if online: return True, data, ""
            last_err = err_msg
    return False, {}, last_err

def _safe_get(url: str, timeout: int = 30, **kwargs) -> requests.Response | None:
    headers = _get_auth_headers(); headers.update(kwargs.pop("headers", {}))
    try: return requests.get(url, timeout=timeout, headers=headers, **kwargs)
    except Exception: return None

def _safe_post(url: str, timeout: int = 30, **kwargs) -> requests.Response | None:
    headers = _get_auth_headers(); headers.update(kwargs.pop("headers", {}))
    try: return requests.post(url, timeout=timeout, headers=headers, **kwargs)
    except Exception: return None

def _format_http_error(resp: requests.Response, default_msg: str) -> str:
    try:
        data = resp.json(); detail = data.get("detail") if isinstance(data, dict) else None
        if detail:
            if isinstance(detail, list): return ", ".join(d.get("msg", str(d)) for d in detail if isinstance(d, dict)) or default_msg
            return str(detail)
    except Exception: pass
    if resp.status_code == 409: return "An account with this email address already exists."
    if resp.status_code == 422: return "Please check the email and password fields."
    if resp.status_code == 400: return "Invalid input data. Please check the fields and try again."
    if resp.status_code == 401: return "Invalid email or password."
    if resp.status_code == 403: return "Account access is restricted."
    if resp.status_code == 404: return "Authentication service endpoint not found."
    if resp.status_code >= 500: return "Something went wrong on the server. Please try again."
    return default_msg

def api_register(api_url: str, full_name: str, email: str, password: str, confirm_password: str) -> tuple[bool, dict | str]:
    try:
        name, clean_email = full_name.strip(), email.strip().lower()
        resp = requests.post(f"{_normalize_backend_url(api_url)}/api/auth/register", json={"full_name": name, "name": name, "email": clean_email, "password": password, "confirm_password": confirm_password}, timeout=15)
        if resp.status_code == 201: return True, resp.json()
        return False, _format_http_error(resp, "Registration failed")
    except (requests.exceptions.ConnectionError, requests.exceptions.Timeout): return False, "Unable to connect to AegisCode services. Please try again."
    except Exception as exc: return False, str(exc)

def api_login(api_url: str, email: str, password: str) -> tuple[bool, dict | str]:
    try:
        resp = requests.post(f"{_normalize_backend_url(api_url)}/api/auth/login", json={"email": email.strip().lower(), "password": password}, timeout=15)
        if resp.status_code == 200: return True, resp.json()
        return False, _format_http_error(resp, "Invalid email or password.")
    except (requests.exceptions.ConnectionError, requests.exceptions.Timeout): return False, "Unable to connect to AegisCode services. Please try again."
    except Exception as exc: return False, str(exc)

def api_get_current_user(api_url: str, token: str) -> dict | None:
    try:
        resp = requests.get(f"{_normalize_backend_url(api_url)}/api/auth/me", headers={"Authorization": f"Bearer {token}"}, timeout=10)
        return resp.json() if resp.status_code == 200 else None
    except Exception: return None

def api_persist_guest_identity(api_url: str, name: str, session_id: str) -> tuple[bool, dict | str]:
    try:
        resp = requests.post(f"{_normalize_backend_url(api_url)}/api/guests", json={"name": name.strip(), "session_id": session_id}, timeout=10)
        if resp.status_code == 200: return True, resp.json()
        return False, _format_http_error(resp, "Unable to save guest session.")
    except (requests.exceptions.ConnectionError, requests.exceptions.Timeout): return False, "Unable to connect to AegisCode services. Please try again."
    except Exception as exc: return False, str(exc)

def fetch_recent_runs(api_url: str, limit: int = 50) -> list[dict]:
    res = _safe_get(f"{api_url}/runs?limit={limit}", timeout=10)
    if res and res.status_code == 200:
        try:
            data = res.json(); return data if isinstance(data, list) else data.get("runs", data.get("items", [])) if isinstance(data, dict) else []
        except Exception: pass
    return []

def fetch_active_runs(api_url: str, limit: int = 50) -> list[dict]:
    res = _safe_get(f"{api_url}/runs/active?limit={limit}", timeout=10)
    if res and res.status_code == 200:
        try:
            data = res.json(); return data if isinstance(data, list) else data.get("runs", data.get("items", [])) if isinstance(data, dict) else []
        except Exception: pass
    return []

def fetch_history_runs(api_url: str, limit: int = 50, status: str | None = None) -> list[dict]:
    url = f"{api_url}/runs/history?limit={limit}" + (f"&status={status}" if status else "")
    res = _safe_get(url, timeout=10)
    if res and res.status_code == 200:
        try:
            data = res.json(); return data if isinstance(data, list) else data.get("runs", data.get("items", [])) if isinstance(data, dict) else []
        except Exception: pass
    return fetch_recent_runs(api_url, limit=limit)

def fetch_run_status(api_url: str, run_id: str) -> dict | None:
    res = _safe_get(f"{api_url}/runs/{run_id}/status", timeout=10)
    if res and res.status_code == 200:
        try: return res.json()
        except Exception: pass
    return None

def fetch_run_results(api_url: str, run_id: str) -> dict | None:
    res = _safe_get(f"{api_url}/runs/{run_id}/results", timeout=10)
    if res and res.status_code == 200:
        try: return res.json()
        except Exception: pass
    return None
