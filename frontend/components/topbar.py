"""
Top Bar & Header Component for AegisCode.
Enterprise SaaS navigation header with live breadcrumbs, operational status, and active run badge.
"""

from __future__ import annotations

import streamlit as st


def render_topbar(
    breadcrumbs: list[str],
    backend_online: bool = True,
    active_run_id: str | None = None,
) -> None:
    """Render a professional top navigation bar with breadcrumbs and live status."""
    status_class = "online" if backend_online else "offline"
    status_text = "Operational" if backend_online else "Backend Offline"
    status_dot = "●"

    crumb_parent = breadcrumbs[0] if len(breadcrumbs) > 1 else "AegisCode"
    crumb_current = breadcrumbs[-1] if breadcrumbs else "Overview"

    run_pill_html = ""
    if active_run_id:
        short_id = active_run_id[:8]
        run_pill_html = (
            f"<div class='topbar-pill run-pill'>"
            f"<span>🤖</span> <code>RUN-{short_id}</code>"
            f"</div>"
        )

    user_html = ""
    current_user = st.session_state.get("current_user")
    if current_user and current_user.get("name"):
        user_name_short = current_user.get("name").split()[0]
        user_html = (
            f"<div class='topbar-pill' style='background: rgba(99, 102, 241, 0.12); "
            f"color: #818cf8; border-color: rgba(99, 102, 241, 0.3); font-weight: 600;'>"
            f"<span>👤</span> <span>{user_name_short}</span>"
            f"</div>"
        )

    st.markdown(
        f"""
        <header class="aegis-topbar">
          <div class="aegis-topbar-left">
            <div class="aegis-topbar-brand-mark">
              <span class="aegis-topbar-logo">🛡️</span>
              <span class="aegis-topbar-name">AegisCode</span>
            </div>
            <div class="aegis-breadcrumbs">
              <span class="crumb-separator">/</span>
              <span class="crumb-parent">{crumb_parent}</span>
              <span class="crumb-separator">/</span>
              <span class="crumb-current">{crumb_current}</span>
            </div>
          </div>
          <div class="aegis-topbar-right">
            {run_pill_html}
            {user_html}
            <div class="topbar-pill model">
              <span>🧠</span> <span>GPT-OSS 120B</span>
            </div>
            <div class="topbar-pill {status_class}">
              <span class="status-dot">{status_dot}</span>
              <span>{status_text}</span>
            </div>
          </div>
        </header>
        """,
        unsafe_allow_html=True,
    )
