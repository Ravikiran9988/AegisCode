"""
Top Bar & Header Component for AegisCode.
"""

from __future__ import annotations

import streamlit as st


def render_topbar(
    breadcrumbs: list[str],
    backend_online: bool = True,
    active_run_id: str | None = None,
) -> None:
    """Render top breadcrumbs and live system indicator badges."""
    crumb_html_parts = []
    for idx, c in enumerate(breadcrumbs):
        if idx == len(breadcrumbs) - 1:
            crumb_html_parts.append(f"<span class='crumb-current'>{c}</span>")
        else:
            crumb_html_parts.append(f"<span>{c}</span> / ")

    crumbs_str = "".join(crumb_html_parts)

    if backend_online:
        status_pill = "<span class='topbar-pill online'>● Backend Online</span>"
    else:
        status_pill = (
            "<span class='topbar-pill' style='border-color: #ef4444; color: #f87171;'>"
            "● Offline</span>"
        )

    run_pill = ""
    if active_run_id:
        short_id = active_run_id[:8]
        run_pill = f"<span class='topbar-pill'>Run: <code>{short_id}</code></span>"

    st.markdown(
        f"""
        <div class="aegis-topbar">
          <div class="aegis-breadcrumbs">
            {crumbs_str}
          </div>
          <div class="aegis-topbar-badges">
            {run_pill}
            {status_pill}
            <span class="topbar-pill model">LLM: openai/gpt-oss-120b</span>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
