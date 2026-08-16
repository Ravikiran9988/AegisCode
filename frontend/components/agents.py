"""
Agent Observability & Traces Component for AegisCode.
Provides dedicated telemetry cards and standalone multi-agent engineering dashboard.
"""

from __future__ import annotations

import streamlit as st

try:
    from frontend.utils.api_client import fetch_recent_runs, fetch_run_results
except ImportError:
    from utils.api_client import fetch_recent_runs, fetch_run_results


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


def render_agents_view(api_url: str) -> None:
    """Render standalone Agent Observability dashboard."""
    st.markdown(
        """
        <div class="aegis-page-header">
          <h1 class="aegis-page-title">Multi-Agent Observability & Telemetry</h1>
          <p class="aegis-page-desc">
            Deep inspection into the specialized roles, telemetry, and runtime behavior
            of the 4 core AegisCode autonomous engineering agents.
          </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # 4 Agent Architecture Grid
    col_ag1, col_ag2 = st.columns(2)
    with col_ag1:
        st.markdown(
            """
            <div class="aegis-agent-card">
              <div class="aegis-agent-header">
                <span class="aegis-agent-title">🏛️ Architect Agent</span>
                <span class="aegis-badge passed">Root Cause Diagnosis</span>
              </div>
              <p style="font-size: 0.86rem; color: #cbd5e1; line-height: 1.5; margin: 0 0 10px 0;">
                Ingests pytest tracebacks, syntax error positions, and project context.
                Formulates root cause hypotheses and establishes a targeted repair blueprint.
              </p>
              <div style="font-size: 0.78rem; color: #94a3b8;">
                <div>• Read-only access to repository context</div>
                <div>• Generates structured JSON architecture plans</div>
                <div>• Identifies relevant source files and verification strategies</div>
              </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        st.markdown(
            """
            <div class="aegis-agent-card">
              <div class="aegis-agent-header">
                <span class="aegis-agent-title">🧪 Test Execution Node</span>
                <span class="aegis-badge passed">Authoritative Gate</span>
              </div>
              <p style="font-size: 0.86rem; color: #cbd5e1; line-height: 1.5; margin: 0 0 10px 0;">
                Spawns authoritative pytest processes inside the isolated execution sandbox.
                Test exit code 0 is an invariant requirement for resolution.
              </p>
              <div style="font-size: 0.78rem; color: #94a3b8;">
                <div>• Captures raw stdout and stderr streams</div>
                <div>• Measures sub-second assertion execution times</div>
                <div>• Read-only test files guard prevents agent tampering</div>
              </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with col_ag2:
        st.markdown(
            """
            <div class="aegis-agent-card">
              <div class="aegis-agent-header">
                <span class="aegis-agent-title">💻 Coder Agent</span>
                <span class="aegis-badge running">Code Synthesis</span>
              </div>
              <p style="font-size: 0.86rem; color: #cbd5e1; line-height: 1.5; margin: 0 0 10px 0;">
                Translates Architect plans into AST-verified file replacements or unified diffs.
                Executes surgical source code repairs.
              </p>
              <div style="font-size: 0.78rem; color: #94a3b8;">
                <div>• AST validation prevents syntax regressions</div>
                <div>• Enforces strict file-modification policies</div>
                <div>• Path traversal protection blocks outside writes</div>
              </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        st.markdown(
            """
            <div class="aegis-agent-card">
              <div class="aegis-agent-header">
                <span class="aegis-agent-title">🔍 Reviewer Agent</span>
                <span class="aegis-badge risk-low">Independent Verification</span>
              </div>
              <p style="font-size: 0.86rem; color: #cbd5e1; line-height: 1.5; margin: 0 0 10px 0;">
                Audits all synthesized code modifications against the original workspace.
                Evaluates regression risk and must explicitly approve the fix.
              </p>
              <div style="font-size: 0.78rem; color: #94a3b8;">
                <div>• Rates regression risk: LOW, MEDIUM, HIGH</div>
                <div>• Verifies root cause defect was genuinely resolved</div>
                <div>• Second gate of double-gated resolution model</div>
              </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    # Active or Recent Run Agent Traces
    active_run_id = st.session_state.get("active_run_id")
    if not active_run_id:
        recent_runs = fetch_recent_runs(api_url, limit=1)
        if recent_runs:
            active_run_id = recent_runs[0].get("run_id")

    if active_run_id:
        st.markdown("---")
        st.markdown(
            f"### 📋 Live Agent Traces for Active Run (`RUN-{active_run_id[:8].upper()}`)"
        )
        rdata = fetch_run_results(api_url, active_run_id)
        if rdata:
            iterations = rdata.get("iterations", rdata.get("iteration_details", []))
            for idx, it in enumerate(iterations):
                it_num = it.get("iteration_number", it.get("iteration", idx + 1))
                st.markdown(f"#### Iteration {it_num}")
                col_t1, col_t2 = st.columns(2)
                with col_t1:
                    render_architect_panel(
                        it.get("architecture_plan") or it.get("architect") or {}
                    )
                    render_coder_panel(it.get("code_changes") or it.get("coder") or [])
                with col_t2:
                    render_test_panel(it.get("test_results") or it.get("tests") or {})
                    render_reviewer_panel(it.get("review_result") or it.get("reviewer") or {})
