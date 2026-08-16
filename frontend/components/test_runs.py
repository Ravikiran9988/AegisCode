"""
Test Observability & Pytest Execution Console Component for AegisCode.
"""

from __future__ import annotations

import streamlit as st

from frontend.components.agents import render_test_panel
from frontend.utils.api_client import fetch_recent_runs, fetch_run_results


def render_test_runs_view(api_url: str) -> None:
    """Render standalone Test Runs engineering view."""
    st.markdown(
        """
        <div class="aegis-page-header">
          <h1 class="aegis-page-title">Pytest Execution & Test Observability</h1>
          <p class="aegis-page-desc">
            Direct inspection into authoritative Pytest subprocess runs, exit codes,
            assertion counts, and captured stdout/stderr streams.
          </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    active_run_id = st.session_state.get("active_run_id")
    if not active_run_id:
        recent_runs = fetch_recent_runs(api_url, limit=1)
        if recent_runs:
            active_run_id = recent_runs[0].get("run_id")

    if not active_run_id:
        st.info("ℹ️ No repair runs found. Start a new repair to inspect test execution.")
        return

    st.markdown(f"**Inspecting Active Run:** `RUN-{active_run_id[:8].upper()}`")
    rdata = fetch_run_results(api_url, active_run_id)

    if rdata:
        iterations = rdata.get("iterations", rdata.get("iteration_details", []))
        if iterations:
            for idx, it in enumerate(iterations):
                it_num = it.get("iteration_number", it.get("iteration", idx + 1))
                st.markdown(f"### Iteration {it_num} Test Sandbox")
                tres = it.get("test_results") or it.get("tests") or {}
                render_test_panel(tres)
        else:
            st.caption("No test execution records found for this run.")
    else:
        st.caption("Could not load test execution results.")
