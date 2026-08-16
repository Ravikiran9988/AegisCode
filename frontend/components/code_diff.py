"""
Code Diff & Modifications Viewer for AegisCode.
Presents interactive syntax-highlighted diffs, before/after tabs, and file modification metrics.
"""

from __future__ import annotations

import streamlit as st


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
    st.markdown(f"Modified **{count}** source file(s) across the autonomous repair lifecycle:")

    for fp, ch in seen_files.items():
        ctype = ch.get("change_type", "modified").upper()
        display_name = fp.split("/")[-1] if "/" in fp else fp

        with st.expander(f"📝 {display_name} — ({ctype})", expanded=True):
            st.markdown(f"**Workspace File Path:** `{fp}`")
            expl = ch.get("explanation", "Code modified by Coder Agent")
            st.markdown(f"**Repair Summary:** {expl}")
            if ch.get("root_cause"):
                st.markdown(f"**Root Cause Addressed:** {ch.get('root_cause')}")

            patch_content = ch.get("patch", "")
            if patch_content:
                diff_tab1, diff_tab2 = st.tabs(["Diff / Patch View", "Raw Code"])
                with diff_tab1:
                    st.code(patch_content, language="diff")
                with diff_tab2:
                    st.code(patch_content, language="python")
