"""
AegisCode — Enterprise Autonomous Self-Healing Multi-Agent Engineering Platform.

Top-tier production dashboard integrating:
- Modular component hierarchy
- Custom developer-tool design system & theme CSS
- Live connectivity polling with cold-start tolerance
- Comprehensive multi-agent observability
- Real-time telemetry, authoritative Pytest output and syntax-highlighted diffs
- Verified project ZIP streaming
- Unauthenticated Public Landing & Personalised Guest Entry Flow
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

# Inject project root and frontend directories into sys.path before local imports.
_ROOT_DIR = Path(__file__).resolve().parent.parent
if str(_ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(_ROOT_DIR))

_FRONTEND_DIR = Path(__file__).resolve().parent
if str(_FRONTEND_DIR) not in sys.path:
    sys.path.insert(0, str(_FRONTEND_DIR))

import streamlit as st  # noqa: E402

try:
    from frontend.components.agents import render_agents_view
    from frontend.components.code_diff import render_code_changes_view
    from frontend.components.dashboard import render_dashboard
    from frontend.components.docs import render_docs
    from frontend.components.footer import render_footer
    from frontend.components.health import render_system_health
    from frontend.components.history import render_history
    from frontend.components.landing import (
        render_auth_choice,
        render_guest_name_input,
        render_public_landing,
    )
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
    from components.code_diff import render_code_changes_view
    from components.dashboard import render_dashboard
    from components.docs import render_docs
    from components.footer import render_footer
    from components.health import render_system_health
    from components.history import render_history
    from components.landing import (
        render_auth_choice,
        render_guest_name_input,
        render_public_landing,
    )
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

# Authentication/guest entry can request a one-time sidebar reset. Streamlit
# normally remembers the user's collapsed state, so use a two-step transition
# to guarantee the sidebar is expanded after entering the workspace without
# forcing it open again after the user manually collapses it.
_sidebar_transition = st.session_state.get("sidebar_open_transition")
if _sidebar_transition == "collapse_then_expand":
    st.session_state["sidebar_open_transition"] = "expand"
    _initial_sidebar_state = "collapsed"
elif _sidebar_transition == "expand":
    st.session_state.pop("sidebar_open_transition", None)
    _initial_sidebar_state = "expanded"
else:
    _initial_sidebar_state = "expanded"

st.set_page_config(
    page_title="AegisCode — Autonomous Engineering Platform",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state=_initial_sidebar_state,
)

if _sidebar_transition == "collapse_then_expand":
    st.rerun()

if "theme_mode" not in st.session_state:
    st.session_state["theme_mode"] = "light"
if "theme_toggle" not in st.session_state:
    st.session_state["theme_toggle"] = st.session_state["theme_mode"] == "dark"

_CSS_PATH = Path(__file__).parent / "styles" / "theme.css"
if _CSS_PATH.exists():
    with open(_CSS_PATH, encoding="utf-8") as f:
        st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

# UX overrides kept here so the public landing and native Streamlit controls
# remain readable even when the base theme changes between light/dark modes.
st.markdown(
    """
    <style>
    /* Landing hero: compact, readable and visually balanced. */
    .aegis-hero {
      padding-top: 0 !important;
      padding-bottom: 8px !important;
      margin-top: -34px !important;
    }
    .aegis-hero-title {
      background: none !important;
      color: var(--text-primary) !important;
      -webkit-text-fill-color: var(--text-primary) !important;
      text-shadow: none !important;
    }
    .aegis-hero-subtitle {
      color: var(--text-secondary) !important;
    }

    /* Reduce excessive vertical whitespace around application pages. */
    section[data-testid="stMain"] > div[data-testid="stMainBlockContainer"] {
      padding-top: 0.35rem !important;
    }
    .aegis-topbar {
      margin-bottom: 12px !important;
    }
    .aegis-page-header {
      margin-top: 0 !important;
      margin-bottom: 18px !important;
    }

    /* Obvious, accessible sidebar open control across Streamlit DOM versions. */
    [data-testid="stExpandSidebarButton"],
    [data-testid="stSidebarCollapsedControl"],
    [data-testid="collapsedControl"] {
      z-index: 999990 !important;
    }
    [data-testid="stExpandSidebarButton"] button,
    [data-testid="stSidebarCollapsedControl"] button,
    [data-testid="collapsedControl"] button {
      width: 44px !important;
      height: 44px !important;
      min-width: 44px !important;
      min-height: 44px !important;
      border-radius: 10px !important;
      background: var(--bg-panel-elevated) !important;
      border: 1px solid var(--border-muted) !important;
      color: var(--text-primary) !important;
      box-shadow: 0 4px 14px rgba(15, 23, 42, 0.16) !important;
    }
    [data-testid="stExpandSidebarButton"] button svg,
    [data-testid="stSidebarCollapsedControl"] button svg,
    [data-testid="collapsedControl"] button svg {
      display: none !important;
    }
    [data-testid="stExpandSidebarButton"] button::after,
    [data-testid="stSidebarCollapsedControl"] button::after,
    [data-testid="collapsedControl"] button::after {
      content: "☰" !important;
      font-size: 1.35rem !important;
      font-weight: 800 !important;
      line-height: 1 !important;
      color: var(--text-primary) !important;
    }
    [data-testid="stExpandSidebarButton"] button:hover,
    [data-testid="stSidebarCollapsedControl"] button:hover,
    [data-testid="collapsedControl"] button:hover {
      border-color: var(--brand-primary) !important;
      background: var(--bg-panel-hover) !important;
    }

    /* Keep the close control equally easy to hit on touch devices. */
    [data-testid="stSidebarCollapseButton"] button {
      width: 44px !important;
      height: 44px !important;
      min-width: 44px !important;
      min-height: 44px !important;
      border-radius: 10px !important;
    }

    @media (max-width: 768px) {
      .aegis-hero {
        padding: 0 8px 6px 8px !important;
        margin-top: -18px !important;
      }
      .aegis-hero-title {
        font-size: clamp(1.85rem, 8vw, 2.35rem) !important;
        line-height: 1.08 !important;
        margin-bottom: 8px !important;
      }
      .aegis-hero-subtitle {
        font-size: 0.92rem !important;
        line-height: 1.42 !important;
        margin-bottom: 10px !important;
      }
      .aegis-hero-badge {
        margin-bottom: 7px !important;
      }
      .aegis-topbar {
        margin-bottom: 8px !important;
      }
      .aegis-page-header {
        margin-bottom: 14px !important;
      }
      .topbar-pill {
        white-space: nowrap;
      }
    }
    </style>
    """,
    unsafe_allow_html=True,
)

st.markdown(
    """
    <script>
    (function updateNavAccessibility() {
      const expandSelectors = [
        '[data-testid="stExpandSidebarButton"] button',
        '[data-testid="stSidebarCollapsedControl"] button',
        '[data-testid="collapsedControl"] button'
      ];
      for (const selector of expandSelectors) {
        const expandBtn = document.querySelector(selector);
        if (expandBtn) {
          expandBtn.setAttribute('title', 'Open navigation');
          expandBtn.setAttribute('aria-label', 'Open navigation');
        }
      }
      const collapseBtn = document.querySelector('[data-testid="stSidebarCollapseButton"] button');
      if (collapseBtn) {
        collapseBtn.setAttribute('title', 'Close navigation');
        collapseBtn.setAttribute('aria-label', 'Close navigation');
      }
    })();
    </script>
    """,
    unsafe_allow_html=True,
)

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

DEFAULT_BACKEND = os.environ.get(
    "BACKEND_URL", "https://aegiscode-vrob.onrender.com"
)

if "backend_online" not in st.session_state:
    st.session_state["backend_online"] = False
if "health_data" not in st.session_state:
    st.session_state["health_data"] = {}
if "backend_error" not in st.session_state:
    st.session_state["backend_error"] = ""
if "nav_view" not in st.session_state:
    st.session_state["nav_view"] = "◉ Overview"
if "guest_mode" not in st.session_state:
    st.session_state["guest_mode"] = False
if "guest_name" not in st.session_state:
    st.session_state["guest_name"] = ""
if "auth_flow_step" not in st.session_state:
    st.session_state["auth_flow_step"] = "public_dashboard"

base_backend_url = _normalize_backend_url(DEFAULT_BACKEND)

if not st.session_state["backend_online"]:
    online, h_data, err_msg = check_backend_with_retry(base_backend_url)
    st.session_state["backend_online"] = online
    st.session_state["health_data"] = h_data
    st.session_state["backend_error"] = err_msg

try:
    import json

    from streamlit_cookies_controller import CookieController

    cookie_controller = CookieController()
    cookie_token = cookie_controller.get("aegis_auth_token")
    if cookie_token and not st.session_state.get("auth_token"):
        st.session_state["auth_token"] = cookie_token
        cookie_user_str = cookie_controller.get("aegis_user")
        if cookie_user_str:
            try:
                st.session_state["current_user"] = json.loads(cookie_user_str)
            except (TypeError, json.JSONDecodeError):
                pass
        st.rerun()
except ImportError:
    pass

# Detect a fresh workspace entry (real account or guest) and request a one-time
# sidebar expansion. Reset the marker whenever the user returns to public auth.
if not st.session_state.get("auth_token") and not st.session_state.get("guest_mode"):
    st.session_state["workspace_entry_initialized"] = False
elif not st.session_state.get("workspace_entry_initialized", False):
    st.session_state["workspace_entry_initialized"] = True
    st.session_state["sidebar_open_transition"] = "collapse_then_expand"
    st.rerun()

# Unauthenticated & Non-Guest Entry Flow Router
if not st.session_state.get("auth_token") and not st.session_state.get("guest_mode"):
    st.markdown(
        """
        <style>
        /* Hide sidebar container and all sidebar UI when unauthenticated & not guest. */
        [data-testid="stSidebar"],
        [data-testid="stSidebarContent"],
        [data-testid="stSidebarHeader"],
        [data-testid="stSidebarCollapseButton"],
        [data-testid="stExpandSidebarButton"],
        [data-testid="stSidebarCollapsedControl"],
        [data-testid="collapsedControl"],
        [data-testid="stToolbar"],
        button[aria-label="Collapse sidebar"],
        button[aria-label="Expand sidebar"] {
          display: none !important;
          visibility: hidden !important;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    flow_step = st.session_state.get("auth_flow_step", "public_dashboard")
    api_url = f"{base_backend_url}/api"

    if flow_step == "auth_choice":
        render_auth_choice(api_url=api_url)
    elif flow_step == "guest_name_input":
        render_guest_name_input()
    else:
        render_public_landing()

    render_footer()
    st.stop()

selected_nav, raw_backend = render_sidebar(
    default_backend=DEFAULT_BACKEND,
    backend_online=st.session_state["backend_online"],
    health_data=st.session_state["health_data"],
    backend_error=st.session_state["backend_error"],
)

normalized_backend = _normalize_backend_url(raw_backend)
api_url = f"{normalized_backend}/api"
active_run_id = st.session_state.get("active_run_id")

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

render_footer()
