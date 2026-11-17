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
        "1. Repository Assessment",
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
    for idx, it in enumerate(iterations):

        it_num = it.get("iteration_number", it.get("iteration", idx + 1))

        # Architect
        arch = it.get("architecture_plan") or it.get("architect") or {}
        if arch:
            _render_step(
                "🏛️",
                f"Iteration {it_num} — Root Cause Analysis",
                arch.get("summary", "Root cause identified and repair plan formulated."),
                "completed",
            )
        else:
            _render_step(
                "🏛️",
                f"Iteration {it_num} — Root Cause Analysis",
                "Waiting for Root Cause Analysis...",
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
                f"Iteration {it_num} — Code Repair & Patch",
                f"Modified `{fp_val}` ({ct_val}) — {exp_val}",
                "completed",
            )
        else:
            _render_step(
                "💻",
                f"Iteration {it_num} — Code Repair & Patch",
                "Waiting for Code Repair...",
                "waiting",
            )

        # Test
        tres = it.get("test_results") or it.get("tests") or {}
        if tres:
            t_ok = tres.get("success", False)
            p_c = tres.get("passed", 0)
            f_c = tres.get("failed", 0)
            d_c = tres.get("duration", 0)
            status_text = f"{p_c} passed, {f_c} failed ({d_c:.2f}s)"
            if not t_ok and run_status == "running":
                status_text += " — Validation failed. Preparing next iteration..."
            _render_step(
                "🧪",
                f"Iteration {it_num} — Test & Validation",
                status_text,
                "completed" if t_ok else "failed",
            )
        else:
            _render_step(
                "🧪",
                f"Iteration {it_num} — Test & Validation",
                "Awaiting Test & Validation...",
                "waiting",
            )

        # Reviewer
        rev = it.get("review_result") or it.get("reviewer") or {}
        if rev:
            r_ok = rev.get("approved", False)
            risk_s = rev.get("regression_risk", "low")
            reason_s = rev.get("reasoning", "")
            rev_detail = f"Approved: {r_ok} | Regression Risk: {risk_s.upper()}"
            if not r_ok:
                rev_detail += f" ({reason_s or 'Patch rejected by independent audit'})"
                if run_status == "running":
                    rev_detail += " — Returning to repair cycle..."
            _render_step(
                "🔍",
                f"Iteration {it_num} — Reviewer Audit Gate",
                rev_detail,
                "completed" if r_ok else "failed",
            )
        else:
            _render_step(
                "🔍",
                f"Iteration {it_num} — Reviewer Audit Gate",
                "Awaiting Reviewer Audit Gate...",
                "waiting",
            )

    # Final Outcome Step
    if run_status in ("passed", "already_passing"):
        _render_step(
            "🏁",
            "Repair Complete & Verified",
            "All test assertions passed and Reviewer Audit Gate approved.",
            "completed",
        )
    elif run_status == "stalled":
        _render_step(
            "🏁",
            "Repair Stalled",
            final_summary or "Execution stalled before completing all iterations.",
            "failed",
        )
    elif run_status in ("failed", "error"):
        _render_step(
            "🏁",
            "Repair Terminated — Maximum Iterations Reached",
            final_summary or "Maximum iterations reached without a passing patch.",
            "failed",
        )
    elif run_status == "cancelled":
        _render_step(
            "🏁",
            "Repair Cancelled",
            final_summary or "Execution cancelled by user.",
            "failed",
        )
