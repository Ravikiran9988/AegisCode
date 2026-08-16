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
    """Render a reliable native Streamlit header with live context."""
    left, right = st.columns([3, 2], vertical_alignment="center")
    with left:
        st.caption("WORKSPACE")
        st.markdown(f"### {'  /  '.join(breadcrumbs)}")

    with right:
        status = "●  Operational" if backend_online else "●  Backend offline"
        model = "GPT-OSS 120B"
        run = f"  •  Run {active_run_id[:8]}" if active_run_id else ""
        st.caption("SYSTEM STATUS")
        st.caption(f"{status}  •  {model}{run}")

    st.divider()
