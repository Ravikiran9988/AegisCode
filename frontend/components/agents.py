"""
Agent Observability & Traces Component for AegisCode.
Renders dedicated telemetry panels for Architect, Coder, Test, and Reviewer agents.
"""

from __future__ import annotations

import streamlit as st


def render_architect_panel(arch_plan: dict, is_already_passing: bool = False) -> None:
    """Render Architect Agent strategy and hypothesis card."""
    st.markdown(
        """
        <div class="aegis-agent-card">
          <div class="aegis-agent-header">
            <span class="aegis-agent-title">🏛️ Architect Agent</span>
            <span class="aegis-badge passed">Root Cause Analysis</span>
          </div>
        """,
        unsafe_allow_html=True,
    )
    if arch_plan:
        st.write(f"**Analysis Summary:** {arch_plan.get('summary', 'N/A')}")
        rel_files = arch_plan.get("relevant_files", [])
        if rel_files:
            files_str = ", ".join(f"`{f}`" for f in rel_files)
            st.markdown(f"**Target Source Files:** {files_str}")
        issues = arch_plan.get("suspected_issues", [])
        if issues:
            st.write(f"**Suspected Defects:** {issues}")
        if arch_plan.get("test_strategy"):
            st.write(f"**Verification Strategy:** `{arch_plan.get('test_strategy')}`")
        with st.expander("Full Architecture Diagnostics"):
            if arch_plan.get("project_type"):
                st.write(f"**Project Architecture:** `{arch_plan.get('project_type')}`")
            if arch_plan.get("confidence") is not None:
                st.write(f"**Agent Confidence Score:** `{arch_plan.get('confidence')}`")
    else:
        if is_already_passing:
            st.info("ℹ️ Baseline tests pass — no architectural diagnosis required.")
        else:
            st.caption("No architect trace recorded for this iteration.")
    st.markdown("</div>", unsafe_allow_html=True)


def render_coder_panel(coder_data: list | dict, is_already_passing: bool = False) -> None:
    """Render Coder Agent code modification card."""
    st.markdown(
        """
        <div class="aegis-agent-card">
          <div class="aegis-agent-header">
            <span class="aegis-agent-title">💻 Coder Agent</span>
            <span class="aegis-badge running">Synthesis</span>
          </div>
        """,
        unsafe_allow_html=True,
    )
    if isinstance(coder_data, dict):
        changes_list = [coder_data]
    elif isinstance(coder_data, list):
        changes_list = coder_data
    else:
        changes_list = []

    if changes_list:
        for ch in changes_list:
            fpath = ch.get("file_path", ch.get("file", "N/A"))
            ctype = ch.get("change_type", "patch").upper()
            expl = ch.get("explanation", "N/A")
            rc = ch.get("root_cause", "")
            st.markdown(
                f"**Target File:** `{fpath}` &nbsp; "
                f"<span class='aegis-badge running'>{ctype}</span>",
                unsafe_allow_html=True,
            )
            st.write(f"**Repair Rationale:** {expl}")
            if rc:
                st.write(f"**Identified Root Cause:** {rc}")
            patch_code = ch.get("patch")
            if patch_code:
                with st.expander("View Unified Patch / Replacement Content"):
                    st.code(patch_code, language="python")
    else:
        if is_already_passing:
            st.info("ℹ️ Project tests pass — no code modifications necessary.")
        else:
            st.caption("No code modifications recorded for this iteration.")
    st.markdown("</div>", unsafe_allow_html=True)


def render_test_panel(test_res: dict) -> None:
    """Render Pytest test execution observability panel."""
    st.markdown(
        """
        <div class="aegis-agent-card">
          <div class="aegis-agent-header">
            <span class="aegis-agent-title">🧪 Pytest Execution Sandbox</span>
            <span class="aegis-badge passed">Authoritative Gate</span>
          </div>
        """,
        unsafe_allow_html=True,
    )
    if test_res:
        code_val = test_res.get("exit_code", 0)
        p_val = test_res.get("passed", 0)
        f_val = test_res.get("failed", 0)
        dur_val = test_res.get("duration", 0)
        status_tag = "PASSED" if code_val == 0 else "FAILED"
        tag_class = "passed" if code_val == 0 else "failed"

        col_m1, col_m2, col_m3, col_m4 = st.columns(4)
        with col_m1:
            st.markdown(
                f"<small>Status</small><br>"
                f"<span class='aegis-badge {tag_class}'>{status_tag}</span>",
                unsafe_allow_html=True,
            )
        with col_m2:
            st.markdown(
                f"<small>Passed</small><br><strong>{p_val}</strong>",
                unsafe_allow_html=True,
            )
        with col_m3:
            st.markdown(
                f"<small>Failed</small><br><strong>{f_val}</strong>",
                unsafe_allow_html=True,
            )
        with col_m4:
            st.markdown(
                f"<small>Duration</small><br><strong>{dur_val:.2f}s</strong>",
                unsafe_allow_html=True,
            )

        if test_res.get("command"):
            cmd = test_res.get("command")
            st.markdown(
                f"<div style='margin-top: 10px;'><small style='color: #94a3b8;'>"
                f"Command:</small> <code>{cmd}</code></div>",
                unsafe_allow_html=True,
            )

        if test_res.get("stdout"):
            with st.expander("Captured Pytest Stdout Terminal"):
                st.code(test_res.get("stdout"), language="text")
        if test_res.get("stderr"):
            with st.expander("Captured Stderr Logs"):
                st.code(test_res.get("stderr"), language="text")
    else:
        st.caption("No test execution output recorded for this iteration.")
    st.markdown("</div>", unsafe_allow_html=True)


def render_reviewer_panel(review_res: dict, is_already_passing: bool = False) -> None:
    """Render Reviewer Agent independent audit card."""
    st.markdown(
        """
        <div class="aegis-agent-card">
          <div class="aegis-agent-header">
            <span class="aegis-agent-title">🔍 Reviewer Agent</span>
            <span class="aegis-badge risk-low">Independent Verification</span>
          </div>
        """,
        unsafe_allow_html=True,
    )
    if review_res:
        app_val = review_res.get("approved")
        app_str = "APPROVED" if app_val else "REJECTED"
        app_class = "passed" if app_val else "failed"

        raw_risk = review_res.get("regression_risk", "low")
        risk_val = raw_risk.upper() if raw_risk else "LOW"
        risk_class = f"risk-{raw_risk.lower()}" if raw_risk else "risk-low"

        st.markdown(
            f"**Audit Decision:** <span class='aegis-badge {app_class}'>{app_str}</span> "
            f"&nbsp;|&nbsp; **Regression Risk:** "
            f"<span class='aegis-badge {risk_class}'>{risk_val}</span>",
            unsafe_allow_html=True,
        )
        if review_res.get("root_cause_fixed") is not None:
            rc_resolved = "✓ Resolved" if review_res.get("root_cause_fixed") else "× Not Resolved"
            st.markdown(f"**Root Cause Verification:** `{rc_resolved}`")
        if review_res.get("reasoning"):
            st.write(f"**Auditor Reasoning:** {review_res.get('reasoning')}")
        if review_res.get("recommendation"):
            st.write(f"**Recommendations:** {review_res.get('recommendation')}")
    else:
        if is_already_passing:
            st.info("ℹ️ Baseline tests pass without modification — automatically approved.")
        else:
            st.caption("No reviewer audit result recorded for this iteration.")
    st.markdown("</div>", unsafe_allow_html=True)
