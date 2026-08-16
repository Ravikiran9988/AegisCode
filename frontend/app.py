"""
AegisCode — Premium Autonomous Self-Healing Multi-Agent SE Dashboard.

Modern Dark Developer-Tool Interface with:
- Sidebar navigation: New Repair, Repair Dashboard, Repair History, System & Settings.
- Real-time Backend Health widget with connection retry for Render cold starts.
- Top KPI dashboard metric cards.
- Animated / Step-based Architect → Coder → Test → Reviewer lifecycle timeline.
- Detailed iteration agent cards (Architect Plan, Coder Mod, Pytest Results, Reviewer Audit).
- Before/after code diff viewer with syntax highlighting and file badges.
- Prominent Download Repaired Project section streaming verified ZIP archives.
- System & Settings page detailing LLM, model, database, and execution environment safely.
- Robust rate-limit (429) detection and informative error/empty states.
"""

from __future__ import annotations

import os
import re
import time
from typing import Any

import requests
import streamlit as st

st.set_page_config(
    page_title="AegisCode — Autonomous Self-Healing AI Dashboard",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Global Constants & Configuration ──────────────────────────────────────────

DEFAULT_BACKEND = os.environ.get(
    "BACKEND_URL", "https://aegiscode-vrob.onrender.com"
)
_COLD_START_RETRY_DELAYS = [0, 2, 4, 8, 15, 30]
_HEALTH_TIMEOUT = 10
_API_TIMEOUT = 30

_PATCH_ERROR_KEYWORDS = (
    "patch application failed", "failed to patch", "no hunks found",
)


# ── Design System: Custom CSS ──────────────────────────────────────────────────

st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800&family=JetBrains+Mono:wght@400;500;600&display=swap');

    html, body, [class*="css"], .stMarkdown, .stText {
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
    }
    code, pre, .stCodeBlock {
        font-family: 'JetBrains Mono', monospace !important;
    }

    .main .block-container {
        padding-top: 2rem;
        padding-bottom: 3rem;
        max-width: 1400px;
    }

    .hero-header {
        display: flex;
        align-items: center;
        justify-content: space-between;
        padding-bottom: 1.25rem;
        margin-bottom: 1.5rem;
        border-bottom: 1px solid rgba(255, 255, 255, 0.08);
    }
    .hero-title-container {
        display: flex;
        flex-direction: column;
    }
    .hero-title {
        font-size: 2.2rem;
        font-weight: 800;
        letter-spacing: -0.03em;
        background: linear-gradient(135deg, #6366f1 0%, #a855f7 50%, #ec4899 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin: 0;
        line-height: 1.2;
    }
    .hero-subtitle {
        font-size: 0.95rem;
        color: #94a3b8;
        font-weight: 400;
        margin-top: 0.35rem;
    }
    .hero-badge-pill {
        display: inline-flex;
        align-items: center;
        gap: 6px;
        background: rgba(99, 102, 241, 0.12);
        border: 1px solid rgba(99, 102, 241, 0.3);
        color: #c7d2fe;
        padding: 4px 12px;
        border-radius: 9999px;
        font-size: 0.8rem;
        font-weight: 600;
    }

    .metric-grid {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
        gap: 16px;
        margin-bottom: 24px;
    }
    .metric-card {
        background: linear-gradient(145deg, #0e1524, #131b2e);
        border: 1px solid rgba(255, 255, 255, 0.07);
        border-radius: 12px;
        padding: 16px 20px;
        position: relative;
        overflow: hidden;
        box-shadow: 0 4px 20px rgba(0, 0, 0, 0.25);
        transition: transform 0.15s ease, border-color 0.15s ease;
    }
    .metric-card:hover {
        border-color: rgba(99, 102, 241, 0.35);
        transform: translateY(-2px);
    }
    .metric-label {
        font-size: 0.78rem;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.06em;
        color: #94a3b8;
        margin-bottom: 6px;
        display: flex;
        align-items: center;
        gap: 6px;
    }
    .metric-value {
        font-size: 1.55rem;
        font-weight: 700;
        color: #f8fafc;
        line-height: 1.2;
    }
    .metric-subtext {
        font-size: 0.8rem;
        color: #64748b;
        margin-top: 4px;
    }

    .status-banner {
        border-radius: 12px;
        padding: 18px 24px;
        margin-bottom: 24px;
        display: flex;
        align-items: center;
        justify-content: space-between;
        border: 1px solid;
    }
    .status-banner.passed {
        background: linear-gradient(135deg, rgba(16, 185, 129, 0.1), rgba(6, 95, 70, 0.15));
        border-color: #10b981;
        color: #ecfdf5;
    }
    .status-banner.failed {
        background: linear-gradient(135deg, rgba(239, 68, 68, 0.1), rgba(153, 27, 27, 0.15));
        border-color: #ef4444;
        color: #fef2f2;
    }
    .status-banner.running {
        background: linear-gradient(135deg, rgba(59, 130, 246, 0.1), rgba(29, 78, 216, 0.15));
        border-color: #3b82f6;
        color: #eff6ff;
    }
    .status-banner.stalled {
        background: linear-gradient(135deg, rgba(245, 158, 11, 0.1), rgba(180, 83, 9, 0.15));
        border-color: #f59e0b;
        color: #fffbeb;
    }
    .status-banner-title {
        font-size: 1.35rem;
        font-weight: 700;
        margin: 0;
        display: flex;
        align-items: center;
        gap: 10px;
    }
    .status-banner-desc {
        font-size: 0.9rem;
        color: #cbd5e1;
        margin: 6px 0 0 0;
    }

    .timeline-container {
        background: #0b1120;
        border: 1px solid rgba(255, 255, 255, 0.08);
        border-radius: 14px;
        padding: 20px 24px;
        margin-bottom: 28px;
    }
    .timeline-step {
        display: flex;
        align-items: flex-start;
        gap: 16px;
        padding: 8px 0;
    }
    .timeline-icon-box {
        min-width: 38px;
        height: 38px;
        border-radius: 10px;
        display: flex;
        align-items: center;
        justify-content: center;
        font-size: 1.1rem;
        border: 1px solid;
    }
    .timeline-icon-box.completed {
        background: rgba(16, 185, 129, 0.15);
        border-color: rgba(16, 185, 129, 0.4);
        color: #10b981;
    }
    .timeline-icon-box.running {
        background: rgba(59, 130, 246, 0.18);
        border-color: rgba(59, 130, 246, 0.5);
        color: #60a5fa;
        animation: pulse-glow 2s infinite;
    }
    .timeline-icon-box.failed {
        background: rgba(239, 68, 68, 0.15);
        border-color: rgba(239, 68, 68, 0.4);
        color: #ef4444;
    }
    .timeline-icon-box.waiting {
        background: rgba(148, 163, 184, 0.05);
        border-color: rgba(148, 163, 184, 0.15);
        color: #64748b;
    }
    .timeline-content {
        flex: 1;
    }
    .timeline-title {
        font-size: 0.95rem;
        font-weight: 600;
        color: #f1f5f9;
        display: flex;
        align-items: center;
        gap: 8px;
    }
    .timeline-detail {
        font-size: 0.84rem;
        color: #94a3b8;
        margin-top: 3px;
    }
    .timeline-connector {
        width: 2px;
        height: 18px;
        background: rgba(255, 255, 255, 0.1);
        margin-left: 18px;
    }

    @keyframes pulse-glow {
        0%, 100% { box-shadow: 0 0 0 0 rgba(59, 130, 246, 0.4); }
        50% { box-shadow: 0 0 0 8px rgba(59, 130, 246, 0); }
    }

    .agent-card {
        background: #0f172a;
        border: 1px solid rgba(255, 255, 255, 0.08);
        border-radius: 12px;
        padding: 18px 20px;
        margin-bottom: 16px;
    }
    .agent-card-header {
        display: flex;
        align-items: center;
        justify-content: space-between;
        margin-bottom: 12px;
        padding-bottom: 8px;
        border-bottom: 1px solid rgba(255, 255, 255, 0.06);
    }
    .agent-card-title {
        font-size: 1.05rem;
        font-weight: 700;
        color: #f8fafc;
        display: flex;
        align-items: center;
        gap: 8px;
    }

    .badge-tag {
        display: inline-flex;
        align-items: center;
        gap: 4px;
        padding: 3px 8px;
        border-radius: 6px;
        font-size: 0.75rem;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.04em;
    }
    .badge-tag.pass {
        background: rgba(16, 185, 129, 0.15);
        color: #34d399;
        border: 1px solid rgba(16, 185, 129, 0.3);
    }
    .badge-tag.fail {
        background: rgba(239, 68, 68, 0.15);
        color: #f87171;
        border: 1px solid rgba(239, 68, 68, 0.3);
    }
    .badge-tag.risk-low {
        background: rgba(16, 185, 129, 0.15);
        color: #34d399;
        border: 1px solid rgba(16, 185, 129, 0.3);
    }
    .badge-tag.risk-med {
        background: rgba(245, 158, 11, 0.15);
        color: #fbbf24;
        border: 1px solid rgba(245, 158, 11, 0.3);
    }
    .badge-tag.risk-high {
        background: rgba(239, 68, 68, 0.15);
        color: #f87171;
        border: 1px solid rgba(239, 68, 68, 0.3);
    }
    .badge-tag.diff-mod {
        background: rgba(59, 130, 246, 0.15);
        color: #93c5fd;
        border: 1px solid rgba(59, 130, 246, 0.3);
    }

    .download-hero {
        background: linear-gradient(135deg, #0b192c 0%, #1e1b4b 100%);
        border: 1px solid rgba(99, 102, 241, 0.4);
        border-radius: 14px;
        padding: 24px 28px;
        margin: 20px 0 28px 0;
        box-shadow: 0 8px 30px rgba(99, 102, 241, 0.15);
        display: flex;
        align-items: center;
        justify-content: space-between;
        flex-wrap: wrap;
        gap: 16px;
    }
    .download-hero-text h3 {
        color: #e0e7ff;
        font-size: 1.25rem;
        font-weight: 700;
        margin: 0 0 6px 0;
        display: flex;
        align-items: center;
        gap: 8px;
    }
    .download-hero-text p {
        color: #a5b4fc;
        font-size: 0.88rem;
        margin: 0;
    }

    .system-health-box {
        background: #090e1a;
        border: 1px solid rgba(255, 255, 255, 0.08);
        border-radius: 10px;
        padding: 14px 16px;
        margin: 12px 0;
    }
    .system-health-row {
        display: flex;
        justify-content: space-between;
        align-items: center;
        padding: 6px 0;
        font-size: 0.85rem;
        border-bottom: 1px solid rgba(255, 255, 255, 0.04);
    }
    .system-health-row:last-child {
        border-bottom: none;
    }
    .system-health-key {
        color: #94a3b8;
    }
    .system-health-val {
        color: #f1f5f9;
        font-weight: 600;
    }

    .alert-custom {
        border-radius: 10px;
        padding: 14px 18px;
        margin: 14px 0;
        font-size: 0.9rem;
        border-left: 4px solid;
    }
    .alert-custom.error {
        background: rgba(239, 68, 68, 0.12);
        border-color: #ef4444;
        color: #fca5a5;
    }
    .alert-custom.warning {
        background: rgba(245, 158, 11, 0.12);
        border-color: #f59e0b;
        color: #fde68a;
    }
    .alert-custom.info {
        background: rgba(59, 130, 246, 0.12);
        border-color: #3b82f6;
        color: #bfdbfe;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


# ── Preserved Helper Functions (Required by Test Suite) ────────────────────────

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


def _check_backend_once(
    backend_url: str, timeout: int = _HEALTH_TIMEOUT
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
    timeout: int = _API_TIMEOUT,
    retries: int = 3,
    backoff: float = 1.5,
    **kwargs,
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


def _safe_post(url: str, **kwargs) -> requests.Response | None:
    """POST request with retry for transient network errors."""
    timeout = kwargs.pop("timeout", _API_TIMEOUT)
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


def _duration_str(started_at: str | None, finished_at: str | None) -> str:
    """Compute human-readable duration from ISO timestamps."""
    if not started_at or not finished_at:
        return "—"
    try:
        from datetime import datetime

        def _parse(s: str):
            for f in (
                "%Y-%m-%dT%H:%M:%S.%f%z", "%Y-%m-%dT%H:%M:%S%z",
                "%Y-%m-%dT%H:%M:%S.%f", "%Y-%m-%dT%H:%M:%S",
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
        "rate_limit", "rate limit", "429",
        "ratelimit", "too many requests", "quota",
    )
    return any(k in s for k in keywords)


# ── Session State Initialization ──────────────────────────────────────────────

if "backend_online" not in st.session_state:
    st.session_state["backend_online"] = False
if "health_data" not in st.session_state:
    st.session_state["health_data"] = {}
if "backend_error" not in st.session_state:
    st.session_state["backend_error"] = ""
if "run_history" not in st.session_state:
    st.session_state["run_history"] = []


# ── Sidebar Navigation & Health Widget ────────────────────────────────────────

st.sidebar.markdown(
    """
    <div style="padding: 6px 0 16px 0;">
      <h2 style="margin: 0; font-size: 1.4rem; font-weight: 800; color: #f8fafc;">
        🛡️ AegisCode
      </h2>
      <div style="font-size: 0.78rem; color: #94a3b8; margin-top: 2px;">
        Autonomous Self-Healing SE Engine
      </div>
    </div>
    """,
    unsafe_allow_html=True,
)

raw_backend_url = st.sidebar.text_input(
    "Backend Endpoint",
    value=DEFAULT_BACKEND,
    help="FastAPI backend host URL",
    key="backend_url_input",
)
base_backend_url = _normalize_backend_url(raw_backend_url)
api_url = f"{base_backend_url}/api"

# Health Check execution
if not st.session_state["backend_online"]:
    with st.sidebar:
        st.markdown("🔄 **Connecting to backend...**")
        st.caption("Render instances may take ~30-60s on cold start.")
    online, health_data, error = check_backend_with_retry(base_backend_url)
    st.session_state["backend_online"] = online
    st.session_state["health_data"] = health_data
    st.session_state["backend_error"] = error
    st.rerun()

# Sidebar Health Box
if st.session_state["backend_online"]:
    hdata = st.session_state["health_data"]
    db_stat = hdata.get("database", "connected")
    st.sidebar.markdown(
        f"""
        <div class="system-health-box">
          <div class="system-health-row">
            <span class="system-health-key">Status</span>
            <span class="system-health-val" style="color: #34d399;">● Online</span>
          </div>
          <div class="system-health-row">
            <span class="system-health-key">Model</span>
            <span class="system-health-val" style="color: #c084fc;">gpt-oss-120b</span>
          </div>
          <div class="system-health-row">
            <span class="system-health-key">Provider</span>
            <span class="system-health-val">Groq REST</span>
          </div>
          <div class="system-health-row">
            <span class="system-health-key">Database</span>
            <span class="system-health-val" style="color: #6ee7b7;">{db_stat}</span>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
else:
    st.sidebar.markdown(
        f"""
        <div class="alert-custom error">
          <strong>❌ Backend Unreachable</strong><br>
          <small>{st.session_state['backend_error']}</small>
        </div>
        """,
        unsafe_allow_html=True,
    )
    if st.sidebar.button("🔄 Retry Connection", key="btn_retry_conn", use_container_width=True):
        st.session_state["backend_online"] = False
        st.rerun()
    st.stop()

st.sidebar.markdown("---")

# Navigation Menu
nav_selection = st.sidebar.radio(
    "Navigation",
    [
        "🚀 Launch Repair Run",
        "📊 Repair Results & Timeline",
        "📜 Repair History",
        "⚙️ System & Settings",
    ],
    index=0 if "active_run_id" not in st.session_state else 1,
    key="main_nav_radio",
)

st.sidebar.markdown("---")
st.sidebar.markdown(
    """
    <div style="font-size: 0.78rem; color: #64748b; line-height: 1.5;">
      <strong>Agentic Workflow:</strong><br>
      • 🏛️ <strong>Architect</strong>: Hypothesizes fix<br>
      • 💻 <strong>Coder</strong>: Writes AST/patch repair<br>
      • 🧪 <strong>Test</strong>: Authoritative Pytest<br>
      • 🔍 <strong>Reviewer</strong>: Independent audit<br>
      • 🛡️ <strong>Safety</strong>: Read-only tests guard
    </div>
    """,
    unsafe_allow_html=True,
)


# ── Main Header ────────────────────────────────────────────────────────────────

st.markdown(
    """
    <div class="hero-header">
      <div class="hero-title-container">
        <h1 class="hero-title">AegisCode Engineering Console</h1>
        <div class="hero-subtitle">
          Autonomous Multi-Agent Self-Healing Pipeline for Python Codebases
        </div>
      </div>
      <div>
        <span class="hero-badge-pill">
          <span style="color: #34d399;">●</span> LLM: openai/gpt-oss-120b
        </span>
      </div>
    </div>
    """,
    unsafe_allow_html=True,
)


# ══════════════════════════════════════════════════════════════════════════════
# VIEW 1: 🚀 LAUNCH REPAIR RUN
# ══════════════════════════════════════════════════════════════════════════════

if nav_selection == "🚀 Launch Repair Run":
    st.markdown("### 1. Upload Broken Python Project (.zip)")
    st.write(
        "Upload a `.zip` archive of your Python repository. "
        "AegisCode will extract it into an isolated workspace, execute pytest, "
        "and activate the Architect → Coder → Test → Reviewer autonomous loop."
    )

    uploaded_file = st.file_uploader(
        "Choose project ZIP archive",
        type=["zip"],
        help="Upload a .zip file containing your Python source files and pytest test files.",
        key="project_file_uploader",
    )

    col_up1, col_up2 = st.columns([1, 1])

    if uploaded_file is not None:
        with col_up1:
            size_kb = len(uploaded_file.getvalue()) / 1024
            st.info(f"📦 Selected: **{uploaded_file.name}** ({size_kb:.1f} KB)")
            if st.button(
                "📤 Upload & Initialize Workspace",
                type="primary",
                key="btn_upload_project",
            ):
                with st.spinner("Extracting workspace and initializing git snapshot..."):
                    try:
                        file_tuple = (
                            uploaded_file.name,
                            uploaded_file.getvalue(),
                            "application/zip",
                        )
                        files = {"file": file_tuple}
                        res = _safe_post(f"{api_url}/projects/upload", files=files, timeout=30)
                        if res is None:
                            st.error("❌ Connection error during upload. Please retry.")
                        elif res.status_code == 201:
                            data = res.json()
                            st.session_state["project_id"] = data["project_id"]
                            st.session_state["project_name"] = data.get("name", uploaded_file.name)
                            st.session_state["file_count"] = data.get("file_count", 0)
                            st.session_state.pop("active_run_id", None)
                            st.success(
                                f"✅ Workspace Initialized!  \n"
                                f"**Project ID:** `{data['project_id']}`  \n"
                                f"**Extracted Files:** {data['file_count']} source file(s)"
                            )
                        elif res.status_code == 413:
                            st.error("❌ File exceeds maximum upload size limit (50 MB).")
                        elif res.status_code == 415:
                            st.error("❌ Unsupported format — only .zip archives are allowed.")
                        elif res.status_code == 422:
                            st.error(f"❌ ZIP validation failed: {_parse_api_error(res)}")
                        else:
                            st.error(f"❌ Upload failed: {_parse_api_error(res)}")
                    except Exception as exc:
                        st.error(f"❌ Upload error: {exc}")

    if "project_id" in st.session_state:
        st.markdown("---")
        st.markdown("### 2. Configure & Launch Autonomous Repair Graph")

        col_cfg1, col_cfg2 = st.columns([1, 1])
        with col_cfg1:
            max_iters = st.slider(
                "Maximum Repair Iterations",
                min_value=1,
                max_value=10,
                value=5,
                help="Max cycles of Architect → Coder → Test → Reviewer before halting.",
                key="max_iters_slider",
            )
            pid = st.session_state["project_id"]
            pname = st.session_state.get("project_name", "project")
            st.caption(f"Active Project: `{pid}` ({pname})")

        with col_cfg2:
            st.markdown(
                """
                <div style="background: #0f172a; border: 1px solid rgba(255,255,255,0.08);
                border-radius: 10px; padding: 14px 18px;">
                  <strong style="color: #e2e8f0; font-size: 0.9rem;">
                    🛡️ Autonomous Safety Guarantees:
                  </strong>
                  <ul style="margin: 6px 0 0 0; padding-left: 18px; color: #94a3b8;
                  font-size: 0.82rem;">
                    <li>Isolated sandbox workspace prevents host filesystem leakage.</li>
                    <li>Test files are read-only — agents cannot delete or tamper with tests.</li>
                    <li>Double gate: Pytest 100% exit code 0 + Reviewer LLM audit required.</li>
                  </ul>
                </div>
                """,
                unsafe_allow_html=True,
            )

        if st.button("⚡ Start Autonomous Repair Graph", type="primary", key="btn_start_graph"):
            with st.spinner("Spawning autonomous LangGraph engine..."):
                try:
                    payload = {
                        "project_id": st.session_state["project_id"],
                        "max_iterations": max_iters,
                    }
                    create_res = _safe_post(f"{api_url}/runs", json=payload, timeout=30)
                    if create_res is None:
                        st.error("❌ Connection error creating run. Please retry.")
                    elif create_res.status_code == 201:
                        run_id = create_res.json()["run_id"]
                        st.session_state["active_run_id"] = run_id

                        # Record in history
                        st.session_state["run_history"].append({
                            "run_id": run_id,
                            "project_name": st.session_state.get("project_name", "project"),
                            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
                        })

                        # Trigger background repair workflow
                        repair_res = _safe_post(f"{api_url}/runs/{run_id}/repair", timeout=10)
                        if repair_res and repair_res.status_code in (200, 202):
                            st.success(f"🚀 Repair Graph Launched! Run ID: `{run_id}`")
                            time.sleep(1)
                            st.rerun()
                        else:
                            st.warning("⚠️ Run created, opening dashboard to monitor progress...")
                            time.sleep(1)
                            st.rerun()
                    else:
                        st.error(f"❌ Failed to create run: {_parse_api_error(create_res)}")
                except Exception as exc:
                    st.error(f"❌ Error launching graph: {exc}")


# ══════════════════════════════════════════════════════════════════════════════
# VIEW 2: 📊 REPAIR RESULTS & TIMELINE DASHBOARD
# ══════════════════════════════════════════════════════════════════════════════

elif nav_selection == "📊 Repair Results & Timeline":
    active_run_id = st.session_state.get("active_run_id", "")

    # Run selector / manual input bar
    col_sel1, col_sel2 = st.columns([3, 1])
    with col_sel1:
        manual_id = st.text_input(
            "Active Run ID",
            value=active_run_id,
            placeholder="e.g. 3fa85f64-5717-4562-b3fc-2c963f66afa6",
            key="input_active_run_id",
        )
        if manual_id.strip() != active_run_id:
            active_run_id = manual_id.strip()
            st.session_state["active_run_id"] = active_run_id

    with col_sel2:
        st.write("")
        st.write("")
        if st.button("🔄 Refresh Data", key="btn_manual_refresh", use_container_width=True):
            st.rerun()

    if not active_run_id:
        st.markdown(
            """
            <div style="background: #0f172a; border: 1px dashed rgba(255,255,255,0.15);
            border-radius: 14px; padding: 48px 24px; text-align: center; margin-top: 24px;">
              <div style="font-size: 2.5rem; margin-bottom: 12px;">🔍</div>
              <h3 style="color: #f8fafc; margin: 0 0 8px 0;">
                No Active Repair Run Selected
              </h3>
              <p style="color: #94a3b8; max-width: 480px; margin: 0 auto; font-size: 0.9rem;">
                Launch a new repair run in <strong>🚀 Launch Repair Run</strong>,
                or enter an existing Run ID above.
              </p>
            </div>
            """,
            unsafe_allow_html=True,
        )
        st.stop()

    # ── Fetch Run Status and Iteration Results from API ───────────────────────
    with st.spinner("Fetching execution metrics from backend..."):
        status_resp = _safe_get(f"{api_url}/runs/{active_run_id}/status", timeout=15)
        results_resp = _safe_get(f"{api_url}/runs/{active_run_id}/results", timeout=15)

    if status_resp is None or results_resp is None:
        st.markdown(
            """
            <div class="alert-custom error">
              <strong>⚠️ Backend Communication Error</strong><br>
              Could not reach backend API to retrieve run details. Please check connection.
            </div>
            """,
            unsafe_allow_html=True,
        )
        st.stop()

    if status_resp.status_code == 404 or results_resp.status_code == 404:
        st.markdown(
            f"""
            <div class="alert-custom warning">
              <strong>⚠️ Run Not Found</strong>: No record for ID <code>{active_run_id}</code>.
            </div>
            """,
            unsafe_allow_html=True,
        )
        st.stop()

    if status_resp.status_code != 200 or results_resp.status_code != 200:
        st.error(f"API Error (HTTP {status_resp.status_code}/{results_resp.status_code})")
        st.stop()

    try:
        sdata = status_resp.json()
        rdata = results_resp.json()
    except Exception as exc:
        st.error(f"Failed to parse API JSON: {exc}")
        st.stop()

    run_status: str = sdata.get("status", "unknown")
    iterations: list = rdata.get("iterations", rdata.get("iteration_details", []))
    final_summary: str | None = sdata.get("final_summary", "")
    current_iter = sdata.get("current_iteration", 0)
    max_iter = sdata.get("max_iterations", 5)
    is_rate_limit_err = _detect_rate_limit_error(final_summary)

    duration_str = _duration_str(sdata.get("started_at"), sdata.get("finished_at"))
    if duration_str == "—" and rdata.get("duration") is not None:
        duration_str = f"{rdata.get('duration'):.1f}s"

    # Auto-refresh if running
    if run_status == "running":
        st.info("🔄 Repair Graph running in background — auto-refreshing in 3 seconds…")
        time.sleep(3)
        st.rerun()

    # ── Top KPI Metrics Grid ──────────────────────────────────────────────────
    latest_it = iterations[-1] if iterations else {}
    tres_last = latest_it.get("test_results") or latest_it.get("tests") or {}
    rev_last = latest_it.get("review_result") or latest_it.get("reviewer") or {}

    passed_count = rdata.get("tests_passed", tres_last.get("passed", "—"))
    failed_count = rdata.get("tests_failed", tres_last.get("failed", "—"))

    rev_approved = rdata.get("reviewer_approved")
    if rev_approved is None and rev_last:
        rev_approved = rev_last.get("approved")
    if run_status in ("passed", "already_passing") and rev_approved is None:
        rev_approved = True

    if rev_approved is True:
        rev_str = "✅ Approved"
    elif rev_approved is False:
        rev_str = "❌ Rejected"
    else:
        rev_str = "⏳ Pending"

    default_risk = "low" if run_status in ("passed", "already_passing") else "—"
    risk_level = rev_last.get("regression_risk", default_risk).upper()
    exit_c = tres_last.get("exit_code", "0" if run_status == "passed" else "—")

    status_icon_map = {
        "passed": "🟢 PASSED",
        "already_passing": "🟢 HEALTHY",
        "failed": "🔴 FAILED",
        "error": "🔴 ERROR",
        "stalled": "🟠 STALLED",
        "running": "🔵 RUNNING",
    }
    status_display = status_icon_map.get(run_status, run_status.upper())

    st.markdown(
        f"""
        <div class="metric-grid">
          <div class="metric-card">
            <div class="metric-label"><span>🛡️</span> Run Status</div>
            <div class="metric-value">{status_display}</div>
            <div class="metric-subtext">ID: {active_run_id[:8]}...</div>
          </div>
          <div class="metric-card">
            <div class="metric-label"><span>🧪</span> Pytest Results</div>
            <div class="metric-value">
              {passed_count} <span style="font-size: 0.9rem; color: #94a3b8;">passed</span>
              / {failed_count} <span style="font-size: 0.9rem; color: #94a3b8;">failed</span>
            </div>
            <div class="metric-subtext">Exit Code: {exit_c}</div>
          </div>
          <div class="metric-card">
            <div class="metric-label"><span>🔍</span> Reviewer Audit</div>
            <div class="metric-value">{rev_str}</div>
            <div class="metric-subtext">Risk Rating: <strong>{risk_level}</strong></div>
          </div>
          <div class="metric-card">
            <div class="metric-label"><span>⚡</span> Lifecycle Stats</div>
            <div class="metric-value">
              {current_iter} / {max_iter}
              <span style="font-size: 0.9rem; color: #94a3b8;">iters</span>
            </div>
            <div class="metric-subtext">Total Duration: {duration_str}</div>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # ── Status Notification Banner ────────────────────────────────────────────
    if is_rate_limit_err:
        st.markdown(
            """
            <div class="alert-custom warning">
              <strong>⏳ LLM Rate Limit Reached (Groq 429 Too Many Requests)</strong><br>
              The rate limit for <code>openai/gpt-oss-120b</code> was reached.<br>
              AegisCode enforces strict single-model fidelity without fallback.
              Please wait 1-2 minutes for your Groq token bucket to refill.
            </div>
            """,
            unsafe_allow_html=True,
        )
    elif run_status in ("passed", "already_passing"):
        st.markdown(
            """
            <div class="status-banner passed">
              <div>
                <h3 class="status-banner-title">✅ Autonomous Repair Successful</h3>
                <p class="status-banner-desc">
                  All authoritative Pytest test cases passed (exit code 0) and the
                  independent Reviewer agent approved all modifications without regression risk.
                </p>
              </div>
              <div style="font-size: 1.8rem;">🎉</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    elif run_status in ("failed", "error"):
        st.markdown(
            f"""
            <div class="status-banner failed">
              <div>
                <h3 class="status-banner-title">❌ Repair Run Terminated</h3>
                <p class="status-banner-desc">
                  {final_summary or 'Review iteration details below for agent failure analysis.'}
                </p>
              </div>
              <div style="font-size: 1.8rem;">🛑</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    # ── Prominent Download Section ────────────────────────────────────────────
    if run_status in ("passed", "already_passing"):
        download_url = f"{api_url}/runs/{active_run_id}/download"
        try:
            with st.spinner("Preparing repaired workspace archive..."):
                dl_resp = _safe_get(download_url, timeout=60, stream=True)
            if dl_resp and dl_resp.status_code == 200:
                zip_bytes = dl_resp.content
                filename = _extract_filename_from_content_disposition(dl_resp, active_run_id)

                col_dl_left, col_dl_right = st.columns([3, 1])
                with col_dl_left:
                    st.markdown(
                        """
                        <div class="download-hero">
                          <div class="download-hero-text">
                            <h3>📦 Download Repaired Project</h3>
                            <p>Get the complete repaired project workspace with verified fixes.</p>
                          </div>
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )
                with col_dl_right:
                    st.write("")
                    st.write("")
                    st.download_button(
                        label="⬇️ Download Repaired Project (.zip)",
                        data=zip_bytes,
                        file_name=filename,
                        mime="application/zip",
                        type="primary",
                        key="btn_download_repaired_zip",
                        use_container_width=True,
                    )
            elif dl_resp and dl_resp.status_code == 405:
                st.error("❌ Download HTTP 405 Method Not Allowed.")
            else:
                st.warning("⚠️ Repaired project archive currently being finalized.")
        except Exception as exc:
            st.error(f"❌ Download error: {exc}")

    # ── Visual Lifecycle Stepper Timeline ─────────────────────────────────────
    st.markdown("### 📅 Autonomous Repair Lifecycle")

    def _render_step(icon: str, title: str, detail: str, state: str) -> None:
        st.markdown(
            f"""
            <div class="timeline-step">
              <div class="timeline-icon-box {state}">{icon}</div>
              <div class="timeline-content">
                <div class="timeline-title">{title}</div>
                <div class="timeline-detail">{detail}</div>
              </div>
            </div>
            <div class="timeline-connector"></div>
            """,
            unsafe_allow_html=True,
        )

    # Step 1: Upload
    _render_step(
        "📦",
        "1. Project Workspace Initialized",
        "ZIP extracted and Git baseline snapshot created.",
        "completed",
    )

    # Step 2: Initial Test
    first_it = iterations[0] if iterations else {}
    init_tres = first_it.get("test_results") or first_it.get("tests") or {}
    if init_tres:
        pass_c = init_tres.get("passed", 0)
        fail_c = init_tres.get("failed", 0)
        init_ok = init_tres.get("success", False)
        code_s = init_tres.get("exit_code", 0)
        _render_step(
            "🧪",
            "2. Baseline Test Execution",
            f"{pass_c} passed, {fail_c} failed (Pytest exit code {code_s})",
            "completed" if init_ok else "failed",
        )
    else:
        _render_step(
            "🧪",
            "2. Baseline Test Execution",
            "Awaiting initial test output...",
            "waiting",
        )

    # Iteration steps
    for it in iterations:
        it_num = it.get("iteration_number", it.get("iteration", 1))

        # Architect
        arch = it.get("architecture_plan") or it.get("architect") or {}
        if arch:
            _render_step(
                "🏛️",
                f"Iteration {it_num} — Architect Analysis",
                arch.get("summary", "Analysis completed."),
                "completed",
            )
        else:
            _render_step(
                "🏛️",
                f"Iteration {it_num} — Architect Analysis",
                "Waiting for plan...",
                "waiting",
            )

        # Coder
        coder_raw = it.get("code_changes") or it.get("coder") or []
        if isinstance(coder_raw, dict):
            changes = [coder_raw]
        elif isinstance(coder_raw, list):
            changes = coder_raw
        else:
            changes = []

        if changes:
            ch0 = changes[0]
            fp_val = ch0.get("file_path", ch0.get("file", "code"))
            ct_val = ch0.get("change_type", "patch")
            exp_val = ch0.get("explanation", "")
            _render_step(
                "💻",
                f"Iteration {it_num} — Code Repair",
                f"Modified `{fp_val}` ({ct_val}) — {exp_val}",
                "completed",
            )
        else:
            _render_step(
                "💻",
                f"Iteration {it_num} — Code Repair",
                "Waiting for code repair...",
                "waiting",
            )

        # Test
        tres = it.get("test_results") or it.get("tests") or {}
        if tres:
            t_ok = tres.get("success", False)
            p_c = tres.get("passed", 0)
            f_c = tres.get("failed", 0)
            d_c = tres.get("duration", 0)
            _render_step(
                "🧪",
                f"Iteration {it_num} — Pytest Verification",
                f"{p_c} passed, {f_c} failed ({d_c:.2f}s)",
                "completed" if t_ok else "failed",
            )
        else:
            _render_step(
                "🧪",
                f"Iteration {it_num} — Pytest Verification",
                "Awaiting pytest results...",
                "waiting",
            )

        # Reviewer
        rev = it.get("review_result") or it.get("reviewer") or {}
        if rev:
            r_ok = rev.get("approved", False)
            risk_s = rev.get("regression_risk", "low")
            _render_step(
                "🔍",
                f"Iteration {it_num} — Reviewer Audit",
                f"Approved: {r_ok} | Risk: {risk_s}",
                "completed" if r_ok else "failed",
            )
        else:
            _render_step(
                "🔍",
                f"Iteration {it_num} — Reviewer Audit",
                "Awaiting reviewer audit...",
                "waiting",
            )

    # Final Outcome Step
    if run_status in ("passed", "already_passing"):
        _render_step(
            "🏁",
            "Repair Complete & Verified",
            "All test assertions passed and reviewer signed off.",
            "completed",
        )
    elif run_status in ("failed", "error"):
        _render_step(
            "🏁",
            "Repair Terminated",
            final_summary or "Max iterations reached or error encountered.",
            "failed",
        )

    st.markdown("---")

    # ── Iteration-by-Iteration Details Accordions / Tabs ───────────────────────
    if iterations:
        st.markdown("### 🔬 Iteration-by-Iteration Agent Traces")
        tab_titles = [
            f"Iteration {it.get('iteration_number', it.get('iteration', idx + 1))}"
            for idx, it in enumerate(iterations)
        ]
        it_tabs = st.tabs(tab_titles)

        for idx, it in enumerate(iterations):
            with it_tabs[idx]:
                arch_plan = it.get("architecture_plan") or it.get("architect") or {}
                coder_data = it.get("code_changes") or it.get("coder") or []
                if isinstance(coder_data, dict):
                    changes_list = [coder_data]
                elif isinstance(coder_data, list):
                    changes_list = coder_data
                else:
                    changes_list = []
                test_res = it.get("test_results") or it.get("tests") or {}
                review_res = it.get("review_result") or it.get("reviewer") or {}

                col_top_l, col_top_r = st.columns(2)

                # Architect Card
                with col_top_l:
                    st.markdown(
                        """
                        <div class="agent-card">
                          <div class="agent-card-header">
                            <span class="agent-card-title">🏛️ Architect Agent</span>
                            <span class="badge-tag pass">Strategy</span>
                          </div>
                        """,
                        unsafe_allow_html=True,
                    )
                    if arch_plan:
                        st.write(f"**Summary:** {arch_plan.get('summary', 'N/A')}")
                        rel = arch_plan.get("relevant_files", [])
                        if rel:
                            st.write(f"**Target Files:** `{', '.join(rel)}`")
                        issues = arch_plan.get("suspected_issues", [])
                        if issues:
                            st.write(f"**Suspected Issues:** {issues}")
                        if arch_plan.get("test_strategy"):
                            st.write(f"**Strategy:** {arch_plan.get('test_strategy')}")
                        with st.expander("Full Architecture Plan"):
                            if arch_plan.get("project_type"):
                                st.write(f"**Project Type:** `{arch_plan.get('project_type')}`")
                            if arch_plan.get("confidence") is not None:
                                st.write(f"**Confidence:** `{arch_plan.get('confidence')}`")
                    else:
                        if run_status == "already_passing":
                            st.info("ℹ️ Baseline tests pass — no architect analysis needed.")
                        else:
                            st.caption("No architect result recorded for this iteration.")
                    st.markdown("</div>", unsafe_allow_html=True)

                # Coder Card
                with col_top_r:
                    st.markdown(
                        """
                        <div class="agent-card">
                          <div class="agent-card-header">
                            <span class="agent-card-title">💻 Coder Agent</span>
                            <span class="badge-tag diff-mod">Modification</span>
                          </div>
                        """,
                        unsafe_allow_html=True,
                    )
                    if changes_list:
                        for ch in changes_list:
                            fpath = ch.get("file_path", ch.get("file", "N/A"))
                            ctype = ch.get("change_type", "patch").upper()
                            expl = ch.get("explanation", "N/A")
                            rc = ch.get("root_cause", "")
                            st.write(
                                f"**File:** `{fpath}` &nbsp; "
                                f"<span class='badge-tag diff-mod'>{ctype}</span>",
                                unsafe_allow_html=True,
                            )
                            st.write(f"**Explanation:** {expl}")
                            if rc:
                                st.write(f"**Root Cause:** {rc}")
                            patch_code = ch.get("patch")
                            if patch_code:
                                with st.expander("View Code Changes / Patch"):
                                    st.code(patch_code, language="python")
                    else:
                        if run_status == "already_passing":
                            st.info("ℹ️ Project healthy — no code modifications required.")
                        else:
                            st.caption("No code changes recorded for this iteration.")
                    st.markdown("</div>", unsafe_allow_html=True)

                col_bot_l, col_bot_r = st.columns(2)

                # Test Results Card
                with col_bot_l:
                    st.markdown(
                        """
                        <div class="agent-card">
                          <div class="agent-card-header">
                            <span class="agent-card-title">🧪 Pytest Execution</span>
                            <span class="badge-tag pass">Verification</span>
                          </div>
                        """,
                        unsafe_allow_html=True,
                    )
                    if test_res:
                        code_val = test_res.get("exit_code", 0)
                        p_val = test_res.get("passed", 0)
                        f_val = test_res.get("failed", 0)
                        dur_val = test_res.get("duration", 0)
                        st.write(
                            f"**Exit Code:** `{code_val}` &nbsp;|&nbsp; "
                            f"**Passed:** {p_val} &nbsp;|&nbsp; "
                            f"**Failed:** {f_val} &nbsp;|&nbsp; "
                            f"**Duration:** {dur_val:.2f}s"
                        )
                        if test_res.get("command"):
                            st.write(f"**Command:** `{test_res.get('command')}`")
                        if test_res.get("stdout"):
                            with st.expander("Captured Stdout"):
                                st.code(test_res.get("stdout"), language="text")
                        if test_res.get("stderr"):
                            with st.expander("Captured Stderr"):
                                st.code(test_res.get("stderr"), language="text")
                    else:
                        st.caption("No test results recorded for this iteration.")
                    st.markdown("</div>", unsafe_allow_html=True)

                # Reviewer Card
                with col_bot_r:
                    st.markdown(
                        """
                        <div class="agent-card">
                          <div class="agent-card-header">
                            <span class="agent-card-title">🔍 Reviewer Agent</span>
                            <span class="badge-tag risk-low">Audit</span>
                          </div>
                        """,
                        unsafe_allow_html=True,
                    )
                    if review_res:
                        app_val = review_res.get("approved")
                        app_str = "✅ Approved" if app_val else "❌ Rejected"
                        risk_val = review_res.get("regression_risk", "low").upper()
                        st.write(
                            f"**Decision:** {app_str} &nbsp;|&nbsp; "
                            f"**Risk:** <span class='badge-tag risk-{risk_val.lower()}'>"
                            f"{risk_val}</span>",
                            unsafe_allow_html=True,
                        )
                        if review_res.get("root_cause_fixed") is not None:
                            rc_fixed = review_res.get("root_cause_fixed")
                            st.write(f"**Root Cause Resolved:** `{rc_fixed}`")
                        if review_res.get("reasoning"):
                            st.write(f"**Reasoning:** {review_res.get('reasoning')}")
                        if review_res.get("recommendation"):
                            st.write(f"**Recommendation:** {review_res.get('recommendation')}")
                    else:
                        if run_status == "already_passing":
                            st.info("ℹ️ Baseline tests pass — automatically approved.")
                        else:
                            st.caption("No reviewer result recorded for this iteration.")
                    st.markdown("</div>", unsafe_allow_html=True)

    st.markdown("---")

    # ── Code Changes / Git Diff ───────────────────────────────────────────────
    st.markdown("### 🔀 Code Changes & Git Diffs")
    all_changes = []
    for it in iterations:
        c_raw = it.get("code_changes") or it.get("coder") or []
        if isinstance(c_raw, dict):
            c_list = [c_raw]
        elif isinstance(c_raw, list):
            c_list = c_raw
        else:
            c_list = []
        all_changes.extend(c_list)

    if not all_changes:
        if run_status in ("passed", "already_passing"):
            st.info("ℹ️ Project passed baseline tests — no code modifications were required.")
        else:
            st.caption("No code changes recorded for this run.")
    else:
        seen_files: dict[str, dict] = {}
        for ch in all_changes:
            fp = ch.get("file_path", ch.get("file", ""))
            if fp:
                seen_files[fp] = ch

        st.write(f"Modified **{len(seen_files)}** file(s) across the repair lifecycle:")
        for fp, ch in seen_files.items():
            ctype = ch.get("change_type", "modified").upper()
            display_name = fp.split("/")[-1] if "/" in fp else fp
            with st.expander(f"📝 {display_name} — ({ctype})", expanded=True):
                st.write(f"**Path:** `{fp}`")
                st.write(f"**Explanation:** {ch.get('explanation', 'N/A')}")
                if ch.get("root_cause"):
                    st.write(f"**Root Cause:** {ch.get('root_cause')}")
                if ch.get("patch"):
                    st.code(ch["patch"], language="python")


# ══════════════════════════════════════════════════════════════════════════════
# VIEW 3: 📜 REPAIR HISTORY
# ══════════════════════════════════════════════════════════════════════════════

elif nav_selection == "📜 Repair History":
    st.markdown("### 📜 Repair Run History")
    st.write("Browse repair runs initiated in this session or search by ID.")

    history = st.session_state.get("run_history", [])

    if history:
        for item in reversed(history):
            col_h1, col_h2, col_h3 = st.columns([3, 2, 1])
            with col_h1:
                p_name = item.get("project_name", "Project")
                r_id = item.get("run_id", "")
                st.write(f"📁 **{p_name}** &nbsp; (`{r_id}`)")
            with col_h2:
                st.caption(f"Launched: {item.get('timestamp', '')}")
            with col_h3:
                if st.button("Open Dashboard", key=f"btn_open_{item['run_id']}"):
                    st.session_state["active_run_id"] = item["run_id"]
                    st.rerun()
            st.markdown(
                "<hr style='margin: 8px 0; border-color: rgba(255,255,255,0.05);'>",
                unsafe_allow_html=True,
            )
    else:
        st.markdown(
            """
            <div style="background: #0f172a; border: 1px dashed rgba(255,255,255,0.1);
            border-radius: 12px; padding: 36px 20px; text-align: center;">
              <p style="color: #94a3b8; margin: 0;">
                No repair runs launched in this session yet.
              </p>
            </div>
            """,
            unsafe_allow_html=True,
        )


# ══════════════════════════════════════════════════════════════════════════════
# VIEW 4: ⚙️ SYSTEM & SETTINGS
# ══════════════════════════════════════════════════════════════════════════════

elif nav_selection == "⚙️ System & Settings":
    st.markdown("### ⚙️ System Configuration & Engine Status")
    st.write("Live operational status and production constraints for AegisCode autonomous engine.")

    hdata = st.session_state.get("health_data", {})

    col_s1, col_s2 = st.columns(2)

    with col_s1:
        st.markdown(
            """
            <div class="agent-card">
              <div class="agent-card-header">
                <span class="agent-card-title">🤖 Production LLM Engine</span>
                <span class="badge-tag pass">Active</span>
              </div>
              <div class="system-health-row">
                <span class="system-health-key">Provider</span>
                <span class="system-health-val">Groq OpenAI-Compatible REST</span>
              </div>
              <div class="system-health-row">
                <span class="system-health-key">Production Model</span>
                <span class="system-health-val" style="color: #c084fc;">openai/gpt-oss-120b</span>
              </div>
              <div class="system-health-row">
                <span class="system-health-key">API Base URL</span>
                <span class="system-health-val">https://api.groq.com/openai/v1</span>
              </div>
              <div class="system-health-row">
                <span class="system-health-key">Rate Limit Backoff</span>
                <span class="system-health-val">Exponential Retry Enabled (TPM Aware)</span>
              </div>
              <div class="system-health-row">
                <span class="system-health-key">Fallback Policy</span>
                <span class="system-health-val" style="color: #38bdf8;">
                  Strict Single-Model (No Fallback)
                </span>
              </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with col_s2:
        app_name_val = hdata.get("app_name", "AegisCode")
        ver_val = hdata.get("version", "0.1.0")
        db_val = hdata.get("database", "connected")
        st.markdown(
            f"""
            <div class="agent-card">
              <div class="agent-card-header">
                <span class="agent-card-title">🖥️ Backend & Sandbox Environment</span>
                <span class="badge-tag pass">Healthy</span>
              </div>
              <div class="system-health-row">
                <span class="system-health-key">Backend Service</span>
                <span class="system-health-val">{app_name_val} v{ver_val}</span>
              </div>
              <div class="system-health-row">
                <span class="system-health-key">Database State</span>
                <span class="system-health-val" style="color: #34d399;">{db_val}</span>
              </div>
              <div class="system-health-row">
                <span class="system-health-key">Execution Backend</span>
                <span class="system-health-val">LocalExecutionBackend (Isolated Workspace)</span>
              </div>
              <div class="system-health-row">
                <span class="system-health-key">Test Isolation</span>
                <span class="system-health-val">Authoritative Pytest Subprocess</span>
              </div>
              <div class="system-health-row">
                <span class="system-health-key">Security Boundaries</span>
                <span class="system-health-val" style="color: #34d399;">
                  Read-Only Tests + Path Traversal Guard
                </span>
              </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.markdown("### 🛡️ State Machine Architecture")
    st.code(
        """
        START
          │
          ▼
        Initial Test Node ──(All Passed)──► [already_passing] ──► END (Success)
          │
          ▼ (Tests Failed)
        Architect Node (Analyzes logs, hypothesizes root cause, designs plan)
          │
          ▼
        Coder Node (Applies targeted AST / patch modification to source files)
          │
          ▼
        Test Node (Executes authoritative Pytest in isolated workspace)
          │
          ▼
        Reviewer Node (Independent audit: checks regressions & approves/rejects)
          │
          ▼
        Decision Router
          ├── All Passed & Approved  ──► [passed]  ──► END (Success + ZIP Download)
          ├── Max Iterations Reached ──► [failed]  ──► END (Max Iterations)
          ├── Repeated Failure       ──► [stalled] ──► END (Loop Stalled)
          └── Retry Needed           ──► ARCHITECT NODE (Iteration N+1)
        """,
        language="text",
    )
