"""
Code Diff & Modifications Viewer for AegisCode.
Presents GitHub/IDE-style diffs, file navigation list, and before/after views.
"""

from __future__ import annotations

import streamlit as st

try:
    from frontend.utils.api_client import fetch_recent_runs, fetch_run_results
except ImportError:
    from utils.api_client import fetch_recent_runs, fetch_run_results


def render_code_diff_viewer(iterations: list[dict], is_already_passing: bool = False) -> None:
    """Render unified before/after and diff viewer for all code changes."""
    st.markdown("### 🔀 Code Changes & Git Diffs")

    all_changes = []
    for it in iterations:
        c_raw = it.get("code_changes") or it.get("coder") or []
        if isinstance(c_raw, dict):
            c_list = [c_raw]
        elif isinstance(c_raw, list):
            c_list = c_raw
        else:
            c_list = []
        all_changes.extend(c_list)

    if not all_changes:
        if is_already_passing:
            st.info("ℹ️ Baseline tests passed on initial execution — zero source files modified.")
        else:
            st.caption("No code modifications recorded for this repair run.")
        return

    # Deduplicate modified files by path
    seen_files: dict[str, dict] = {}
    for ch in all_changes:
        fp = ch.get("file_path", ch.get("file", ""))
        if fp:
            seen_files[fp] = ch

    count = len(seen_files)
    st.markdown(
        f"<div style='margin-bottom: 12px;'><strong style='color: #38bdf8;'>"
        f"{count} file(s) modified</strong> by autonomous agents:</div>",
        unsafe_allow_html=True,
    )

    for fp, ch in seen_files.items():
        ctype = ch.get("change_type", "modified").upper()
        display_name = fp.split("/")[-1] if "/" in fp else fp
        badge_prefix = (
            "M" if ctype in ("PATCH", "MODIFIED") else ("A" if ctype == "CREATE" else "D")
        )

        with st.expander(f"📝 {badge_prefix} {display_name} — ({ctype})", expanded=True):
            st.markdown(f"**Workspace File Path:** `{fp}`")
            expl = ch.get("explanation", "Code modified by Coder Agent")
            st.markdown(f"**Repair Rationale:** {expl}")
            if ch.get("root_cause"):
                st.markdown(f"**Root Cause Addressed:** {ch.get('root_cause')}")

            patch_content = ch.get("patch", "")
            if patch_content:
                diff_tab1, diff_tab2 = st.tabs(["Unified Diff View", "Synthesized Source"])
                with diff_tab1:
                    st.code(patch_content, language="diff")
                with diff_tab2:
                    st.code(patch_content, language="python")


def render_code_changes_view(api_url: str) -> None:
    """Render standalone Code Changes engineering view."""
    st.markdown(
        """
        <div class="aegis-page-header">
          <h1 class="aegis-page-title">Synthesized Code Changes & Git Diffs</h1>
          <p class="aegis-page-desc">
            Inspect source file modifications, AST-verified replacements, and unified diffs.
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
        st.info("ℹ️ No repair runs found. Start a new repair to inspect code changes.")
        return

    st.markdown(f"**Inspecting Active Run:** `RUN-{active_run_id[:8].upper()}`")
    rdata = fetch_run_results(api_url, active_run_id)
    if rdata:
        iterations = rdata.get("iterations", rdata.get("iteration_details", []))
        run_status = rdata.get("status", "")
        render_code_diff_viewer(iterations, is_already_passing=(run_status == "already_passing"))
    else:
        st.caption("Could not load code change telemetry for this run.")
