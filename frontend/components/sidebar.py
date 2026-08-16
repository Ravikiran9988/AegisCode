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

        dark_mode = st.toggle("Dark mode", key="theme_toggle")
        selected_theme = "dark" if dark_mode else "light"
        if selected_theme != st.session_state.get("theme_mode"):
            st.session_state["theme_mode"] = selected_theme
            st.rerun()

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

        # Sidebar Footer: Live Engine & Infrastructure Status
        st.markdown("<div style='height: 20px;'></div>", unsafe_allow_html=True)
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
