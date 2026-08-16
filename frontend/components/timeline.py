"""
Lifecycle Stepper & Timeline Visualizer for AegisCode.
"""

from __future__ import annotations

import streamlit as st


def render_timeline(
    run_status: str,
    iterations: list[dict],
    final_summary: str | None = None,
) -> None:
    """Render the step-based autonomous repair lifecycle."""
    st.markdown("### 📅 Autonomous Repair Lifecycle")

    def _render_step(icon: str, title: str, detail: str, state: str) -> None:
        st.markdown(
            f"""
            <div class="aegis-timeline-step">
              <div class="aegis-timeline-icon {state}">{icon}</div>
              <div class="aegis-timeline-body">
                <div class="aegis-timeline-step-title">{title}</div>
                <div class="aegis-timeline-step-detail">{detail}</div>
              </div>
            </div>
            <div class="aegis-timeline-connector"></div>
            """,
            unsafe_allow_html=True,
        )

    # Step 1: Upload
    _render_step(
        "📦",
        "1. Project Workspace Initialized",
        "ZIP extracted into sandbox and Git baseline snapshot created.",
        "completed",
    )

    # Step 2: Initial Test
    first_it = iterations[0] if iterations else {}
    init_tres = first_it.get("test_results") or first_it.get("tests") or {}
    if init_tres:
        pass_c = init_tres.get("passed", 0)
        fail_c = init_tres.get("failed", 0)
        init_ok = init_tres.get("success", False)
        code_s = init_tres.get("exit_code", 0)
        _render_step(
            "🧪",
            "2. Baseline Test Execution",
            f"{pass_c} passed, {fail_c} failed (Pytest exit code {code_s})",
            "completed" if init_ok else "failed",
        )
    else:
        _render_step(
            "🧪",
            "2. Baseline Test Execution",
            "Awaiting baseline test execution...",
            "waiting",
        )

    # Iteration steps
    for it in iterations:
        it_num = it.get("iteration_number", it.get("iteration", 1))

        # Architect
        arch = it.get("architecture_plan") or it.get("architect") or {}
        if arch:
            _render_step(
                "🏛️",
                f"Iteration {it_num} — Architect Analysis",
                arch.get("summary", "Analysis completed."),
                "completed",
            )
        else:
            _render_step(
                "🏛️",
                f"Iteration {it_num} — Architect Analysis",
                "Waiting for architecture plan...",
                "waiting",
            )

        # Coder
        coder_raw = it.get("code_changes") or it.get("coder") or []
        if isinstance(coder_raw, dict):
            changes = [coder_raw]
        elif isinstance(coder_raw, list):
            changes = coder_raw
        else:
            changes = []

        if changes:
            ch0 = changes[0]
            fp_val = ch0.get("file_path", ch0.get("file", "code"))
            ct_val = ch0.get("change_type", "patch")
            exp_val = ch0.get("explanation", "")
            _render_step(
                "💻",
                f"Iteration {it_num} — Code Repair",
                f"Modified `{fp_val}` ({ct_val}) — {exp_val}",
                "completed",
            )
        else:
            _render_step(
                "💻",
                f"Iteration {it_num} — Code Repair",
                "Waiting for code repair...",
                "waiting",
            )

        # Test
        tres = it.get("test_results") or it.get("tests") or {}
        if tres:
            t_ok = tres.get("success", False)
            p_c = tres.get("passed", 0)
            f_c = tres.get("failed", 0)
            d_c = tres.get("duration", 0)
            _render_step(
                "🧪",
                f"Iteration {it_num} — Pytest Verification",
                f"{p_c} passed, {f_c} failed ({d_c:.2f}s)",
                "completed" if t_ok else "failed",
            )
        else:
            _render_step(
                "🧪",
                f"Iteration {it_num} — Pytest Verification",
                "Awaiting test results...",
                "waiting",
            )

        # Reviewer
        rev = it.get("review_result") or it.get("reviewer") or {}
        if rev:
            r_ok = rev.get("approved", False)
            risk_s = rev.get("regression_risk", "low")
            _render_step(
                "🔍",
                f"Iteration {it_num} — Reviewer Audit",
                f"Approved: {r_ok} | Regression Risk: {risk_s}",
                "completed" if r_ok else "failed",
            )
        else:
            _render_step(
                "🔍",
                f"Iteration {it_num} — Reviewer Audit",
                "Awaiting reviewer audit...",
                "waiting",
            )

    # Final Outcome Step
    if run_status in ("passed", "already_passing"):
        _render_step(
            "🏁",
            "Repair Complete & Verified",
            "All test assertions passed and reviewer signed off.",
            "completed",
        )
    elif run_status in ("failed", "error"):
        _render_step(
            "🏁",
            "Repair Terminated",
            final_summary or "Max iterations reached or error encountered.",
            "failed",
        )
