"""
AegisCode — Enterprise Autonomous Self-Healing Multi-Agent Engineering Platform.

Top-tier production dashboard integrating:
- Modular component hierarchy
- Custom dark developer-tool design system & theme CSS
- Live connectivity polling with cold-start tolerance
- Comprehensive multi-agent observability (Architect, Coder, Test, Reviewer)
- Real-time telemetry, authoritative Pytest test output & syntax-highlighted diffs
- Verified project ZIP streaming
"""

from __future__ import annotations

import os
from pathlib import Path

import streamlit as st

from frontend.components.agents import render_agents_view
from frontend.components.code_diff import render_code_changes_view
from frontend.components.dashboard import render_dashboard
from frontend.components.docs import render_docs
from frontend.components.health import render_system_health
from frontend.components.history import render_history
from frontend.components.live_repair import render_live_repair
from frontend.components.settings import render_settings
from frontend.components.sidebar import render_sidebar
from frontend.components.test_runs import render_test_runs_view
from frontend.components.topbar import render_topbar
from frontend.components.upload import render_upload
from frontend.utils.api_client import (
    _check_backend_once,
    _safe_get,
    _safe_post,
    check_backend_with_retry,
)
from frontend.utils.helpers import (
    _detect_rate_limit_error,
    _duration_str,
    _extract_filename_from_content_disposition,
    _normalize_backend_url,
    _parse_api_error,
)

# Export helper functions for test suite compatibility
__all__ = [
    "_normalize_backend_url",
    "_check_backend_once",
    "check_backend_with_retry",
    "_detect_rate_limit_error",
    "_parse_api_error",
    "_extract_filename_from_content_disposition",
    "_safe_get",
    "_safe_post",
    "_duration_str",
]

st.set_page_config(
    page_title="AegisCode — Autonomous Engineering Platform",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Load Design System CSS ────────────────────────────────────────────────────

_CSS_PATH = Path(__file__).parent / "styles" / "theme.css"
if _CSS_PATH.exists():
    with open(_CSS_PATH, encoding="utf-8") as f:
        st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

# ── Configuration & Defaults ──────────────────────────────────────────────────

DEFAULT_BACKEND = os.environ.get(
    "BACKEND_URL", "https://aegiscode-vrob.onrender.com"
)

# ── Session State Initialization ──────────────────────────────────────────────

if "backend_online" not in st.session_state:
    st.session_state["backend_online"] = False
if "health_data" not in st.session_state:
    st.session_state["health_data"] = {}
if "backend_error" not in st.session_state:
    st.session_state["backend_error"] = ""
if "nav_view" not in st.session_state:
    st.session_state["nav_view"] = "◉ Overview"

# ── Initial Connectivity Check ────────────────────────────────────────────────

base_backend_url = _normalize_backend_url(DEFAULT_BACKEND)

if not st.session_state["backend_online"]:
    online, h_data, err_msg = check_backend_with_retry(base_backend_url)
    st.session_state["backend_online"] = online
    st.session_state["health_data"] = h_data
    st.session_state["backend_error"] = err_msg

# ── Render Application Shell (Sidebar + Topbar) ───────────────────────────────

selected_nav, raw_backend = render_sidebar(
    default_backend=DEFAULT_BACKEND,
    backend_online=st.session_state["backend_online"],
    health_data=st.session_state["health_data"],
    backend_error=st.session_state["backend_error"],
)

normalized_backend = _normalize_backend_url(raw_backend)
api_url = f"{normalized_backend}/api"

active_run_id = st.session_state.get("active_run_id")

# Breadcrumbs Map
breadcrumb_map = {
    "◉ Overview": ["Control Center", "Overview"],
    "🚀 New Repair": ["Control Center", "New Repair"],
    "🤖 Active Repairs": ["Control Center", "Active Repairs"],
    "📊 Repair History": ["Control Center", "Repair History"],
    "🏛️ Agents": ["Engineering", "Agent Observability"],
    "🔀 Code Changes": ["Engineering", "Synthesized Code Diffs"],
    "🧪 Test Runs": ["Engineering", "Pytest Execution Logs"],
    "❤️ System Health": ["Engineering", "System Health & Telemetry"],
    "⚙ Settings": ["System", "Configuration & Settings"],
    "📖 Documentation": ["System", "Architecture & Documentation"],
}

breadcrumbs = breadcrumb_map.get(selected_nav, ["AegisCode", "Overview"])

render_topbar(
    breadcrumbs=breadcrumbs,
    backend_online=st.session_state["backend_online"],
    active_run_id=active_run_id,
)

# ── Main View Routing (All 10 Dedicated Views) ────────────────────────────────

if selected_nav == "◉ Overview":
    render_dashboard(api_url=api_url, health_data=st.session_state["health_data"])

elif selected_nav == "🚀 New Repair":
    render_upload(api_url=api_url)

elif selected_nav == "🤖 Active Repairs":
    render_live_repair(api_url=api_url)

elif selected_nav == "📊 Repair History":
    render_history(api_url=api_url)

elif selected_nav == "🏛️ Agents":
    render_agents_view(api_url=api_url)

elif selected_nav == "🔀 Code Changes":
    render_code_changes_view(api_url=api_url)

elif selected_nav == "🧪 Test Runs":
    render_test_runs_view(api_url=api_url)

elif selected_nav == "❤️ System Health":
    render_system_health(
        backend_url=normalized_backend,
        initial_health_data=st.session_state["health_data"],
    )

elif selected_nav == "⚙ Settings":
    render_settings(
        backend_url=normalized_backend,
        health_data=st.session_state["health_data"],
    )

elif selected_nav == "📖 Documentation":
    render_docs()
