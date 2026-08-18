"""
Top Bar & Header Component for AegisCode.
Enterprise SaaS navigation header with live breadcrumbs, operational status, active run badge,
and user/guest indicators.
"""

from __future__ import annotations

import html

import streamlit as st


def render_topbar(
    breadcrumbs: list[str],
    backend_online: bool = True,
    active_run_id: str | None = None,
) -> None:
    """Render a professional top navigation bar with live breadcrumbs and status."""
    status_class = "online" if backend_online else "offline"
    status_text = "Operational" if backend_online else "Backend Offline"

    crumb_parent = breadcrumbs[0] if len(breadcrumbs) > 1 else "AegisCode"
    crumb_current = breadcrumbs[-1] if breadcrumbs else "Overview"

    # Escape all dynamic values before inserting them into HTML.
    crumb_parent = html.escape(str(crumb_parent))
    crumb_current = html.escape(str(crumb_current))

    run_pill_html = ""
    if active_run_id:
        short_id = html.escape(str(active_run_id)[:8])
        run_pill_html = (
            "<div class='topbar-pill run-pill'>"
            f"<span>🤖</span> <code>RUN-{short_id}</code>"
            "</div>"
        )

    user_html = ""
    current_user = st.session_state.get("current_user")
    if current_user and (
        current_user.get("name")
        or current_user.get("full_name")
    ):
        raw_name = current_user.get("name") or current_user.get("full_name") or "User"
        user_name_short = html.escape(str(raw_name).split()[0])
        user_html = (
            "<div class='topbar-pill user-pill'>"
            f"<span>👤</span> <span>{user_name_short}</span>"
            "</div>"
        )
    elif st.session_state.get("guest_mode"):
        raw_g_name = str(st.session_state.get("guest_name", "Guest")).split()[0]
        guest_name_short = html.escape(raw_g_name)
        user_html = (
            "<div class='topbar-pill user-pill' "
            "style='border-color: rgba(245, 158, 11, 0.4); color: #fbbf24;'>"
            f"<span>👤</span> <span>{guest_name_short} (Guest)</span>"
            "</div>"
        )

    header_html = f"""
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
      <span class="status-dot">●</span>
      <span>{status_text}</span>
    </div>
  </div>
</header>
"""

    st.html(header_html)
