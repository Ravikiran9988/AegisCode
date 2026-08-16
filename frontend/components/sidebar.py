"""
Sidebar Navigation and Brand Shell Component for AegisCode.
"""

from __future__ import annotations

import streamlit as st


def render_sidebar(
    default_backend: str,
    backend_online: bool,
    health_data: dict,
    backend_error: str,
) -> tuple[str, str]:
    """
    Render professional dark developer-tool sidebar.
    Returns (selected_view, normalized_backend_url).
    """
    # Brand Header
    st.sidebar.markdown(
        """
        <div style="padding: 4px 0 16px 0;">
          <div style="display: flex; align-items: center; gap: 10px;">
            <span style="font-size: 1.7rem;">🛡️</span>
            <div>
              <h2 style="margin: 0; font-size: 1.35rem; font-weight: 800;
              letter-spacing: -0.02em; color: #f8fafc; line-height: 1.1;">
                AegisCode
              </h2>
              <div style="font-size: 0.72rem; color: #94a3b8; font-weight: 500;
              letter-spacing: 0.04em; text-transform: uppercase; margin-top: 3px;">
                Autonomous Engineering
              </div>
            </div>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # Backend Host Input
    raw_backend = st.sidebar.text_input(
        "Backend Host",
        value=default_backend,
        help="FastAPI backend host URL",
        key="sidebar_backend_url_input",
    )

    st.sidebar.markdown("<div style='height: 8px;'></div>", unsafe_allow_html=True)

    # Navigation Menu
    nav_options = [
        "◉ Dashboard",
        "🚀 New Repair",
        "📊 Repair History",
        "🤖 Live Repair Console",
        "❤️ System Health",
        "⚙ Settings",
        "📖 Documentation",
    ]

    current_idx = 0
    if "nav_view" in st.session_state and st.session_state["nav_view"] in nav_options:
        current_idx = nav_options.index(st.session_state["nav_view"])

    selected_nav = st.sidebar.radio(
        "Navigation",
        nav_options,
        index=current_idx,
        key="main_sidebar_nav_radio",
        label_visibility="collapsed",
    )
    st.session_state["nav_view"] = selected_nav

    st.sidebar.markdown("---")

    # Real-time Engine Status Footer
    if backend_online:
        db_stat = health_data.get("database", "connected")
        st.sidebar.markdown(
            f"""
            <div class="aegis-health-card" style="padding: 12px 14px; margin-bottom: 0;">
              <div class="aegis-health-row">
                <span class="aegis-health-key" style="font-size: 0.78rem;">Backend API</span>
                <span style="color: #34d399; font-weight: 600; font-size: 0.78rem;">
                  ● Online
                </span>
              </div>
              <div class="aegis-health-row">
                <span class="aegis-health-key" style="font-size: 0.78rem;">LLM Engine</span>
                <span style="color: #c084fc; font-weight: 600; font-size: 0.78rem;">
                  openai/gpt-oss-120b
                </span>
              </div>
              <div class="aegis-health-row">
                <span class="aegis-health-key" style="font-size: 0.78rem;">Database</span>
                <span style="color: #6ee7b7; font-weight: 600; font-size: 0.78rem;">
                  {db_stat}
                </span>
              </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    else:
        st.sidebar.markdown(
            f"""
            <div class="aegis-alert error" style="margin: 0; padding: 10px 12px;">
              <strong style="font-size: 0.8rem;">❌ Backend Offline</strong><br>
              <small style="color: #fca5a5; font-size: 0.72rem;">{backend_error[:90]}</small>
            </div>
            """,
            unsafe_allow_html=True,
        )
        if st.sidebar.button(
            "🔄 Retry Connection",
            key="btn_sidebar_retry",
            use_container_width=True,
        ):
            st.session_state["backend_online"] = False
            st.rerun()

    return selected_nav, raw_backend
