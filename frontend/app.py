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
import sys
from pathlib import Path

# Inject project root and frontend directories into sys.path before any local imports
_ROOT_DIR = Path(__file__).resolve().parent.parent
if str(_ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(_ROOT_DIR))

_FRONTEND_DIR = Path(__file__).resolve().parent
if str(_FRONTEND_DIR) not in sys.path:
    sys.path.insert(0, str(_FRONTEND_DIR))

import streamlit as st  # noqa: E402
from streamlit.delta_generator import DeltaGenerator
import textwrap

_orig_markdown = DeltaGenerator.markdown

def _patched_markdown(self, body, unsafe_allow_html=False, *args, **kwargs):
    if unsafe_allow_html and isinstance(body, str):
        # Remove all leading whitespace to prevent Markdown from ever parsing 
        # indented HTML lines as code blocks, even if there are blank lines.
        body = "\n".join(line.lstrip() for line in body.splitlines())
    return _orig_markdown(self, body, unsafe_allow_html=unsafe_allow_html, *args, **kwargs)

DeltaGenerator.markdown = _patched_markdown

try:
    from frontend.components.agents import render_agents_view
    from frontend.components.auth import render_auth
    from frontend.components.code_diff import render_code_changes_view
    from frontend.components.dashboard import render_dashboard
    from frontend.components.docs import render_docs
    from frontend.components.footer import render_footer
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
except ImportError:
    from components.agents import render_agents_view
    from components.auth import render_auth
    from components.code_diff import render_code_changes_view
    from components.dashboard import render_dashboard
    from components.docs import render_docs
    from components.footer import render_footer
    from components.health import render_system_health
    from components.history import render_history
    from components.live_repair import render_live_repair
    from components.settings import render_settings
    from components.sidebar import render_sidebar
    from components.test_runs import render_test_runs_view
    from components.topbar import render_topbar
    from components.upload import render_upload
    from utils.api_client import (
        _check_backend_once,
        _safe_get,
        _safe_post,
        check_backend_with_retry,
    )
    from utils.helpers import (
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

if "theme_mode" not in st.session_state:
    st.session_state["theme_mode"] = "light"
if "theme_toggle" not in st.session_state:
    st.session_state["theme_toggle"] = st.session_state["theme_mode"] == "dark"

_CSS_PATH = Path(__file__).parent / "styles" / "theme.css"
if _CSS_PATH.exists():
    with open(_CSS_PATH, encoding="utf-8") as f:
        st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

if st.session_state["theme_mode"] == "light":
    st.markdown(
        """
        <style>
        :root {
          --bg-app: #f5f7fb;
          --bg-panel: #ffffff;
          --bg-panel-elevated: #f8fafc;
          --bg-panel-hover: #eef2ff;
          --bg-sidebar: #ffffff;
          --bg-glass: rgba(255, 255, 255, 0.88);
          --border-subtle: rgba(15, 23, 42, 0.10);
          --border-muted: rgba(15, 23, 42, 0.16);
          --border-hover: rgba(79, 70, 229, 0.42);
          --text-primary: #172033;
          --text-secondary: #526179;
          --text-muted: #71809a;
          --text-dim: #94a3b8;
          --shadow-card: 0 8px 24px rgba(15, 23, 42, 0.08);
          --shadow-glow: 0 0 28px rgba(79, 70, 229, 0.12);
        }
        [data-testid="stAppViewContainer"], [data-testid="stApp"], .stApp {
          background:
            radial-gradient(circle at 84% -12%, rgba(99, 102, 241, 0.13), transparent 30rem),
            radial-gradient(circle at 12% 115%, rgba(14, 165, 233, 0.08), transparent 32rem),
            var(--bg-app) !important;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

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

# ── Authentication Gate ───────────────────────────────────────────────────────

try:
    from streamlit_cookies_controller import CookieController
    cookie_controller = CookieController()
    cookie_token = cookie_controller.get("aegis_auth_token")
    if cookie_token and not st.session_state.get("auth_token"):
        st.session_state["auth_token"] = cookie_token
        try:
            import json
            cookie_user_str = cookie_controller.get("aegis_user")
            if cookie_user_str:
                st.session_state["current_user"] = json.loads(cookie_user_str)
        except Exception:
            pass
        st.rerun()
except ImportError:
    pass

if not st.session_state.get("auth_token"):
    render_auth(api_url=f"{base_backend_url}/api")
    render_footer()
    st.stop()

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

# ── Global Footer ─────────────────────────────────────────────────────────────

render_footer()
