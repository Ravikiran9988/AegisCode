"""
Left Sidebar Shell & Navigation for AegisCode.
Structured into Control Center, Engineering, and System navigation groups.
"""

from __future__ import annotations

import streamlit as st


def render_sidebar(
    default_backend: str,
    backend_online: bool = True,
    health_data: dict | None = None,
    backend_error: str = "",
) -> tuple[str, str]:
    """Render the left navigation sidebar and return the selected view and backend URL."""
    health_data = health_data or {}

    with st.sidebar:
        # Brand Header
        st.markdown(
            """
            <div class="aegis-sidebar-brand">
              <div class="aegis-brand-title">
                <span>🛡️</span> AegisCode
              </div>
              <div class="aegis-brand-subtitle">
                Autonomous Software Engineering
              </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        def _on_theme_change() -> None:
            is_dark = st.session_state.get("theme_toggle", True)
            st.session_state["theme_mode"] = "dark" if is_dark else "light"

        dark_mode = st.toggle("Dark mode", key="theme_toggle", on_change=_on_theme_change)

        nav_options = [
            # Control Center
            "◉ Overview",
            "🚀 New Repair",
            "🤖 Active Repairs",
            "📊 Repair History",
            # Engineering
            "🏛️ Agents",
            "🔀 Code Changes",
            "🧪 Test Runs",
            "❤️ System Health",
            # System
            "📖 Documentation",
            "⚙ Settings",
        ]

        current_nav = st.session_state.get("nav_view", "◉ Overview")
        if current_nav not in nav_options:
            current_nav = "◉ Overview"

        # Synchronize radio widget state if nav_view was modified programmatically
        if st.session_state.get("app_navigation_radio") != current_nav:
            st.session_state["app_navigation_radio"] = current_nav

        def _on_nav_change() -> None:
            st.session_state["nav_view"] = st.session_state.get(
                "app_navigation_radio", "◉ Overview"
            )

        st.markdown(
            "<div class='aegis-nav-group-header'>CONTROL CENTER</div>",
            unsafe_allow_html=True,
        )
        selected_nav = st.radio(
            "Navigation",
            options=nav_options,
            index=nav_options.index(current_nav),
            key="app_navigation_radio",
            on_change=_on_nav_change,
            label_visibility="collapsed",
        )
        st.session_state["nav_view"] = selected_nav

        # Backend URL configuration drawer
        with st.expander("🔌 Backend Connection", expanded=False):
            raw_backend = st.text_input(
                "Backend URL",
                value=default_backend,
                key="input_backend_url",
                help="Enter base URL of the AegisCode FastAPI backend.",
            )
        backend_to_use = raw_backend if "raw_backend" in locals() else default_backend

        # User Account & Logout section
        current_user = st.session_state.get("current_user")
        if current_user:
            u_name = (
                current_user.get("nickname")
                or current_user.get("name")
                or current_user.get("full_name", "User")
            )
            u_email = current_user.get("email", "")
            st.markdown(
                f"""
                <div style="background: rgba(99, 102, 241, 0.08);
                border: 1px solid var(--border-subtle); border-radius: var(--radius-md);
                padding: 10px 12px; margin-top: 14px; margin-bottom: 8px;">
                  <div style="font-weight: 700; font-size: 0.84rem; color: var(--text-primary);">
                    👤 {u_name}
                  </div>
                  <div style="font-size: 0.72rem; color: var(--text-secondary); margin-top: 2px;">
                    {u_email}
                  </div>
                </div>
                """,
                unsafe_allow_html=True,
            )
            if st.button("Sign Out", key="btn_sidebar_logout", use_container_width=True):
                st.session_state.pop("auth_token", None)
                st.session_state.pop("current_user", None)
                try:
                    from streamlit_cookies_controller import CookieController
                    cookies = CookieController()
                    cookies.remove("aegis_auth_token")
                    cookies.remove("aegis_user")
                except ImportError:
                    pass
                st.rerun()

        # Sidebar Footer: Live Engine & Infrastructure Status
        st.markdown("<div style='height: 10px;'></div>", unsafe_allow_html=True)
        db_stat = health_data.get("database", "connected").capitalize()
        status_dot = "●"
        status_color = "#34d399" if backend_online else "#f87171"
        status_text = "Engine Operational" if backend_online else "Engine Offline"

        st.markdown(
            f"""
            <div class="aegis-health-card" style="padding: 10px 12px; margin-top: 10px;">
              <div style="display: flex; align-items: center; justify-content: space-between;
              margin-bottom: 6px;">
                <span style="font-weight: 700; font-size: 0.78rem; color: var(--text-primary);">
                  <span style="color: {status_color}; margin-right: 4px;">{status_dot}</span>
                  {status_text}
                </span>
              </div>
              <div style="font-size: 0.72rem; color: var(--text-secondary); line-height: 1.5;">
                <div>LLM: <strong style="color: #c084fc;">openai/gpt-oss-120b</strong></div>
                <div>Database: <strong style="color: #38bdf8;">{db_stat}</strong></div>
                <div>
                  Backend: <strong style="color: var(--text-primary);">FastAPI REST</strong>
                </div>
              </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        if not backend_online and backend_error:
            st.caption(f"⚠️ {backend_error[:60]}")

    return selected_nav, backend_to_use
