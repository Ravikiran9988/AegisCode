"""
Live Repair Console & Interactive Execution Workspace for AegisCode.
Features real-time polling, progress timeline stepper, agent tabs, and hero completion screens.
"""

from __future__ import annotations

import time

import streamlit as st

from frontend.components.agents import (
    render_architect_panel,
    render_coder_panel,
    render_reviewer_panel,
    render_test_panel,
)
from frontend.components.code_diff import render_code_diff_viewer
from frontend.components.states import (
    render_empty_state,
    render_error_alert,
    render_rate_limit_alert,
    render_warning_alert,
)
from frontend.components.timeline import render_timeline
from frontend.utils.api_client import _safe_get, fetch_run_results, fetch_run_status
from frontend.utils.helpers import (
    _detect_rate_limit_error,
    _duration_str,
    _extract_filename_from_content_disposition,
)


def render_live_repair(api_url: str) -> None:
    """Render the live execution console for active or past repair runs."""
    active_run_id = st.session_state.get("active_run_id", "")

    # Search / Switch bar
    col_s1, col_s2 = st.columns([3, 1])
    with col_s1:
        manual_id = st.text_input(
            "Active Run ID",
            value=active_run_id,
            placeholder="e.g. 3fa85f64-5717-4562-b3fc-2c963f66afa6",
            key="input_live_run_id",
            label_visibility="collapsed",
        )
        if manual_id.strip() != active_run_id:
            active_run_id = manual_id.strip()
            st.session_state["active_run_id"] = active_run_id

    with col_s2:
        if st.button("🔄 Refresh Data", key="btn_live_refresh", use_container_width=True):
            st.rerun()

    if not active_run_id:
        render_empty_state(
            title="No Active Repair Run Selected",
            description=(
                "Launch a new self-healing repair from the 🚀 New Repair "
                "workspace or select a historical run from the dashboard."
            ),
            icon="🛡️",
            cta_label="🚀 Start New Repair",
            cta_key="live_empty_cta",
        )
        return

    # Fetch status & results
    with st.spinner("Fetching execution telemetry from backend..."):
        sdata = fetch_run_status(api_url, active_run_id)
        rdata = fetch_run_results(api_url, active_run_id)

    if sdata is None or rdata is None:
        render_error_alert(
            "Run Not Found or Unreachable",
            f"Could not retrieve execution data for Run ID <code>{active_run_id}</code>.",
        )
        return

    run_status: str = sdata.get("status", "unknown")
    iterations: list = rdata.get("iterations", rdata.get("iteration_details", []))
    final_summary: str | None = sdata.get("final_summary", "")
    current_iter = sdata.get("current_iteration", 0)
    max_iter = sdata.get("max_iterations", 5)
    is_rate_limit_err = _detect_rate_limit_error(final_summary)

    duration_str = _duration_str(sdata.get("started_at"), sdata.get("finished_at"))
    if duration_str == "—" and rdata.get("duration") is not None:
        duration_str = f"{rdata.get('duration'):.1f}s"

    # Live auto-refresh if running
    if run_status == "running":
        st.info("🔄 Autonomous Repair Graph is running in background — auto-refreshing in 3s…")
        time.sleep(3)
        st.rerun()

    # ── Header Console Bar ────────────────────────────────────────────────────
    short_id = active_run_id[:8].upper()
    p_name = st.session_state.get("project_name", "Python Project")
    status_label = run_status.upper()
    if run_status in ("passed", "already_passing"):
        badge_class = "passed"
    elif run_status in ("failed", "error"):
        badge_class = "failed"
    else:
        badge_class = "running"

    st.markdown(
        f"""
        <div style="display: flex; justify-content: space-between; align-items: center;
        margin-bottom: 18px; flex-wrap: wrap; gap: 10px; background: var(--bg-panel);
        padding: 14px 18px; border-radius: var(--radius-md);
        border: 1px solid var(--border-subtle);">
          <div>
            <div style="font-size: 0.74rem; color: #94a3b8; text-transform: uppercase;
            letter-spacing: 0.06em; font-weight: 700;">
              Autonomous Engineering Console
            </div>
            <h2 style="margin: 2px 0 0 0; font-size: 1.35rem; font-weight: 800; color: #f8fafc;">
              Repair Run <code>RUN-{short_id}</code>
            </h2>
            <div style="font-size: 0.84rem; color: #94a3b8; margin-top: 3px;">
              Project: <strong style="color: #f8fafc;">{p_name}</strong> &nbsp;•&nbsp;
              Elapsed: <strong style="color: #38bdf8;">{duration_str}</strong> &nbsp;•&nbsp;
              Iteration: <strong style="color: #c084fc;">{current_iter}/{max_iter}</strong>
            </div>
          </div>
          <div>
            <span class="aegis-badge {badge_class}" style="font-size: 0.85rem; padding: 6px 14px;">
              ● {status_label}
            </span>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # ── Top Progress Lifecycle Stepper ────────────────────────────────────────
    render_timeline(run_status, iterations, final_summary)

    # ── Metric KPI Summary Grid ───────────────────────────────────────────────
    latest_it = iterations[-1] if iterations else {}
    tres_last = latest_it.get("test_results") or latest_it.get("tests") or {}
    rev_last = latest_it.get("review_result") or latest_it.get("reviewer") or {}

    passed_count = rdata.get("tests_passed", tres_last.get("passed", "—"))
    failed_count = rdata.get("tests_failed", tres_last.get("failed", "—"))

    rev_approved = rdata.get("reviewer_approved")
    if rev_approved is None and rev_last:
        rev_approved = rev_last.get("approved")
    if run_status in ("passed", "already_passing") and rev_approved is None:
        rev_approved = True

    if rev_approved is True:
        rev_str = "Approved"
    elif rev_approved is False:
        rev_str = "Rejected"
    else:
        rev_str = "Pending"

    default_risk = "low" if run_status in ("passed", "already_passing") else "—"
    raw_risk = rev_last.get("regression_risk", default_risk)
    risk_level = raw_risk.upper() if raw_risk else "LOW"
    exit_c = tres_last.get("exit_code", "0" if run_status == "passed" else "—")

    st.markdown(
        f"""
        <div class="aegis-metric-grid">
          <div class="aegis-metric-card">
            <div class="aegis-metric-label"><span>🛡️</span> Execution State</div>
            <div class="aegis-metric-val">{run_status.upper()}</div>
            <div class="aegis-metric-sub">Run: RUN-{short_id}</div>
          </div>
          <div class="aegis-metric-card">
            <div class="aegis-metric-label"><span>🧪</span> Pytest Assertion State</div>
            <div class="aegis-metric-val">
              {passed_count} <small style='font-size: 0.85rem; color: #94a3b8;'>passed</small>
              / {failed_count} <small style='font-size: 0.85rem; color: #94a3b8;'>failed</small>
            </div>
            <div class="aegis-metric-sub">Exit Code: {exit_c}</div>
          </div>
          <div class="aegis-metric-card">
            <div class="aegis-metric-label"><span>🔍</span> Reviewer Gate</div>
            <div class="aegis-metric-val">{rev_str}</div>
            <div class="aegis-metric-sub">Risk Rating: <strong>{risk_level}</strong></div>
          </div>
          <div class="aegis-metric-card">
            <div class="aegis-metric-label"><span>⚡</span> Lifecycle Stats</div>
            <div class="aegis-metric-val">
              {current_iter} / {max_iter}
              <small style='font-size: 0.85rem; color: #94a3b8;'>iters</small>
            </div>
            <div class="aegis-metric-sub">Duration: {duration_str}</div>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # ── Status Hero / Completion Banners ──────────────────────────────────────
    if is_rate_limit_err:
        render_rate_limit_alert()
    elif run_status in ("passed", "already_passing"):
        st.markdown(
            """
            <div class="aegis-status-banner passed">
              <div>
                <h3 class="aegis-banner-title">✓ REPAIR SUCCESSFUL</h3>
                <p class="aegis-banner-desc">
                  Your project has been repaired and independently verified. All authoritative
                  pytest tests passed and the Reviewer approved the patch without regressions.
                </p>
                <div style="margin-top: 10px; font-size: 0.82rem; color: #a7f3d0;
                display: flex; gap: 16px; flex-wrap: wrap;">
                  <span>✓ Root cause identified</span>
                  <span>✓ Patch applied</span>
                  <span>✓ Tests passed</span>
                  <span>✓ Reviewer approved</span>
                </div>
              </div>
              <div style="font-size: 2.2rem;">🛡️</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        # Prominent Download CTA Card
        download_url = f"{api_url}/runs/{active_run_id}/download"
        try:
            with st.spinner("Preparing repaired workspace archive..."):
                dl_resp = _safe_get(download_url, timeout=60, stream=True)
            if dl_resp and dl_resp.status_code == 200:
                zip_bytes = dl_resp.content
                filename = _extract_filename_from_content_disposition(dl_resp, active_run_id)

                col_dl_l, col_dl_r = st.columns([3, 1])
                with col_dl_l:
                    st.markdown(
                        """
                        <div class="aegis-download-hero">
                          <div class="aegis-download-hero-text">
                            <h3>📦 Download Repaired Project Workspace</h3>
                            <p>Get the fully repaired and verified repository archive (.zip).</p>
                          </div>
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )
                with col_dl_r:
                    st.write("")
                    st.write("")
                    st.download_button(
                        label="⬇️ Download Repaired Project",
                        data=zip_bytes,
                        file_name=filename,
                        mime="application/zip",
                        type="primary",
                        key="btn_live_download_zip",
                        use_container_width=True,
                    )
            elif dl_resp and dl_resp.status_code == 405:
                render_error_alert(
                    "Method Not Allowed",
                    "Download endpoint returned HTTP 405.",
                )
            else:
                render_warning_alert(
                    "Finalizing Archive",
                    "Repaired project ZIP is being prepared.",
                )
        except Exception as exc:
            render_error_alert("Download Error", str(exc))

    elif run_status in ("failed", "error"):
        st.markdown(
            f"""
            <div class="aegis-status-banner failed">
              <div>
                <h3 class="aegis-banner-title">🔴 REPAIR COULD NOT BE COMPLETED</h3>
                <p class="aegis-banner-desc">
                  {final_summary or 'Maximum iterations reached or unrecoverable defect.'}
                </p>
                <div style="margin-top: 8px; font-size: 0.82rem; color: #fca5a5;">
                  Prior agent telemetry and diagnostics have been preserved below.
                </div>
              </div>
              <div style="font-size: 2.2rem;">🛑</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    # ── Multi-Tab Execution Workspace ─────────────────────────────────────────
    st.markdown("---")
    console_tabs = st.tabs([
        "📅 Overview & Timeline",
        "🏛️ Architect Agent",
        "💻 Coder Agent",
        "🧪 Pytest Results",
        "🔍 Reviewer Audit",
        "🔀 Code Changes",
    ])

    is_already_passing = (run_status == "already_passing")

    # Tab 1: Timeline
    with console_tabs[0]:
        st.markdown("### 📅 Execution Timeline & State History")
        render_timeline(run_status, iterations, final_summary)

    # Tab 2: Architect
    with console_tabs[1]:
        st.markdown("### 🏛️ Architect Agent Analysis")
        if iterations:
            for idx, it in enumerate(iterations):
                it_num = it.get("iteration_number", it.get("iteration", idx + 1))
                st.markdown(f"#### Iteration {it_num}")
                arch = it.get("architecture_plan") or it.get("architect") or {}
                render_architect_panel(arch, is_already_passing)
        else:
            st.caption("No architect trace recorded for this run.")

    # Tab 3: Coder
    with console_tabs[2]:
        st.markdown("### 💻 Coder Agent Synthesis")
        if iterations:
            for idx, it in enumerate(iterations):
                it_num = it.get("iteration_number", it.get("iteration", idx + 1))
                st.markdown(f"#### Iteration {it_num}")
                coder_d = it.get("code_changes") or it.get("coder") or []
                render_coder_panel(coder_d, is_already_passing)
        else:
            st.caption("No code modifications recorded for this run.")

    # Tab 4: Pytest
    with console_tabs[3]:
        st.markdown("### 🧪 Authoritative Pytest Execution")
        if iterations:
            for idx, it in enumerate(iterations):
                it_num = it.get("iteration_number", it.get("iteration", idx + 1))
                st.markdown(f"#### Iteration {it_num}")
                tres = it.get("test_results") or it.get("tests") or {}
                render_test_panel(tres)
        else:
            st.caption("No test execution logs recorded for this run.")

    # Tab 5: Reviewer
    with console_tabs[4]:
        st.markdown("### 🔍 Independent Reviewer Audit")
        if iterations:
            for idx, it in enumerate(iterations):
                it_num = it.get("iteration_number", it.get("iteration", idx + 1))
                st.markdown(f"#### Iteration {it_num}")
                rev = it.get("review_result") or it.get("reviewer") or {}
                render_reviewer_panel(rev, is_already_passing)
        else:
            st.caption("No reviewer audit recorded for this run.")

    # Tab 6: Code Changes
    with console_tabs[5]:
        render_code_diff_viewer(iterations, is_already_passing)
