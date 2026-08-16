"""
Live Repair Console & Interactive Execution Workspace for AegisCode.
Features real-time LangGraph execution pipeline, agent observability, live test metrics,
and authoritative completion and failure screens.
"""

from __future__ import annotations

import time

import streamlit as st

try:
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
    from frontend.utils.api_client import (
        _safe_get,
        fetch_recent_runs,
        fetch_run_results,
        fetch_run_status,
    )
    from frontend.utils.helpers import (
        _detect_rate_limit_error,
        _duration_str,
        _extract_filename_from_content_disposition,
    )
except ImportError:
    from components.agents import (
        render_architect_panel,
        render_coder_panel,
        render_reviewer_panel,
        render_test_panel,
    )
    from components.code_diff import render_code_diff_viewer
    from components.states import (
        render_empty_state,
        render_error_alert,
        render_rate_limit_alert,
        render_warning_alert,
    )
    from components.timeline import render_timeline
    from utils.api_client import (
        _safe_get,
        fetch_recent_runs,
        fetch_run_results,
        fetch_run_status,
    )
    from utils.helpers import (
        _detect_rate_limit_error,
        _duration_str,
        _extract_filename_from_content_disposition,
    )


def render_live_repair(api_url: str) -> None:
    """Render the real-time autonomous repair execution dashboard."""
    active_run_id = st.session_state.get("active_run_id", "")

    # Auto-recover active running run if session state was cleared on browser reload
    if not active_run_id:
        recent = fetch_recent_runs(api_url, limit=5)
        for r in recent:
            if r.get("status") == "running":
                active_run_id = r.get("run_id", "")
                st.session_state["active_run_id"] = active_run_id
                break
        if not active_run_id and recent:
            active_run_id = recent[0].get("run_id", "")
            st.session_state["active_run_id"] = active_run_id

    # Run ID search / switcher bar
    col_s1, col_s2, col_s3 = st.columns([4, 1, 1])
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
        if st.button("🔄 Refresh", key="btn_live_refresh", use_container_width=True):
            st.rerun()

    with col_s3:
        if st.button("➕ New Repair", key="btn_live_nav_new", use_container_width=True):
            st.session_state["nav_view"] = "🚀 New Repair"
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
    current_iter = sdata.get("current_iteration", sdata.get("iteration", 1))
    max_iter = sdata.get("max_iterations", 5)
    progress_pct = sdata.get("progress_percent", 0)
    current_phase = sdata.get("current_phase", "Autonomous Execution")
    current_action = sdata.get("current_action", {})
    pipeline_nodes = sdata.get("pipeline_nodes", [])
    timeline_events = sdata.get("timeline", [])
    tests_info = sdata.get("tests", {})
    files_info = sdata.get("files", {})
    is_rate_limit_err = _detect_rate_limit_error(final_summary)

    p_name = sdata.get("project_name", st.session_state.get("project_name", "Python Project"))
    short_id = active_run_id[:8].upper()

    # Formatted duration
    dur_sec = sdata.get("elapsed_seconds")
    if dur_sec is not None:
        mins = int(dur_sec // 60)
        secs = int(dur_sec % 60)
        duration_str = f"{mins:02d}m {secs:02d}s" if mins > 0 else f"{secs:02d}s"
    else:
        duration_str = _duration_str(sdata.get("started_at"), sdata.get("finished_at"))

    # Badge style
    if run_status in ("passed", "already_passing"):
        badge_class = "passed"
        status_label = "PASSED"
    elif run_status in ("failed", "error"):
        badge_class = "failed"
        status_label = "FAILED"
    elif run_status == "stalled":
        badge_class = "failed"
        status_label = "STALLED"
    elif run_status == "cancelled":
        badge_class = "running"
        status_label = "CANCELLED"
    else:
        badge_class = "running"
        status_label = "RUNNING"

    # ── A. RUN HEADER ─────────────────────────────────────────────────────────
    st.html(
        f"""
        <div style="display: flex; justify-content: space-between; align-items: center;
        margin-bottom: 18px; flex-wrap: wrap; gap: 10px; background: var(--bg-panel);
        padding: 16px 20px; border-radius: var(--radius-md);
        border: 1px solid var(--border-subtle);">
          <div>
            <div style="font-size: 0.74rem; color: #94a3b8; text-transform: uppercase;
            letter-spacing: 0.08em; font-weight: 700;">
              🛡️ Autonomous Software Engineering
            </div>
            <h2 style="margin: 3px 0 0 0; font-size: 1.4rem; font-weight: 800; color: #f8fafc;">
              Repair Run <code>RUN-{short_id}</code>
            </h2>
            <div style="font-size: 0.86rem; color: #94a3b8; margin-top: 4px;">
              Project: <strong style="color: #f8fafc;">{p_name}</strong> &nbsp;•&nbsp;
              Elapsed: <strong style="color: #38bdf8;">{duration_str}</strong> &nbsp;•&nbsp;
              Iteration: <strong style="color: #c084fc;">{current_iter}/{max_iter}</strong>
            </div>
          </div>
          <div>
            <span class="aegis-badge {badge_class}" style="font-size: 0.88rem; padding: 6px 16px;">
              ● {status_label}
            </span>
          </div>
        </div>
        """,
    )

    # ── B. REAL-TIME PROGRESS BAR ─────────────────────────────────────────────
    st.html(
        f"""
        <div style="background: var(--bg-panel); padding: 14px 18px;
        border-radius: var(--radius-md); border: 1px solid var(--border-subtle);
        margin-bottom: 18px;">
          <div style="display: flex; justify-content: space-between; align-items: center;
          margin-bottom: 8px;">
            <span style="font-weight: 700; font-size: 0.9rem; color: #f8fafc;">
              Repair Progress &bull; <span style="color: #38bdf8;">{current_phase}</span>
            </span>
            <span style="font-weight: 800; font-size: 0.95rem; color: #38bdf8;">
              {progress_pct}%
            </span>
          </div>
        </div>
        """,
    )
    st.progress(min(progress_pct / 100.0, 1.0))

    # ── C. LANGGRAPH EXECUTION PIPELINE & CURRENT ACTION ──────────────────────
    col_pipe, col_action = st.columns([3, 2])

    with col_pipe:
        st.html(
            """
            <div style="font-weight: 700; font-size: 0.85rem; color: #94a3b8;
            text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 8px;">
              LangGraph State Machine Pipeline
            </div>
            """,
        )

        nodes_to_show = pipeline_nodes or [
            {
                "node": "initial_test",
                "name": "Repository Assessment",
                "agent": "Test Agent",
                "status": "completed" if run_status != "running" else "running",
            },
            {
                "node": "architect",
                "name": "Root Cause Analysis",
                "agent": "Architect Agent",
                "status": "pending",
            },
            {
                "node": "coder",
                "name": "Code Repair & Patch",
                "agent": "Coder Agent",
                "status": "pending",
            },
            {
                "node": "test",
                "name": "Test & Validation",
                "agent": "Test Agent",
                "status": "pending",
            },
            {
                "node": "reviewer",
                "name": "Reviewer Gate",
                "agent": "Reviewer Agent",
                "status": "pending",
            },
        ]

        pipe_html = "<div style='display: flex; flex-direction: column; gap: 8px;'>"
        for idx, pnode in enumerate(nodes_to_show, 1):
            n_status = pnode.get("status", "pending")
            n_name = pnode.get("name", pnode.get("node", "Node"))
            n_agent = pnode.get("agent", "")

            if n_status == "completed":
                status_icon = "✓"
                badge_style = (
                    "background: rgba(16, 185, 129, 0.15); color: #34d399; "
                    "border: 1px solid rgba(16, 185, 129, 0.3);"
                )
                status_text = "Completed"
            elif n_status == "running":
                status_icon = "◉"
                badge_style = (
                    "background: rgba(56, 189, 248, 0.2); color: #38bdf8; "
                    "border: 1px solid rgba(56, 189, 248, 0.4);"
                )
                status_text = "Running"
            elif n_status == "failed":
                status_icon = "✗"
                badge_style = (
                    "background: rgba(239, 68, 68, 0.2); color: #f87171; "
                    "border: 1px solid rgba(239, 68, 68, 0.4);"
                )
                status_text = "Failed"
            else:
                status_icon = "○"
                badge_style = (
                    "background: rgba(148, 163, 184, 0.08); color: #64748b; "
                    "border: 1px solid rgba(148, 163, 184, 0.15);"
                )
                status_text = "Pending"

            pipe_html += f"""
            <div style="display: flex; align-items: center; justify-content: space-between;
            background: var(--bg-panel); padding: 10px 14px; border-radius: var(--radius-sm);
            border: 1px solid var(--border-subtle);">
              <div style="display: flex; align-items: center; gap: 10px;">
                <span style="font-weight: 700; color: #94a3b8; font-size: 0.8rem;">{idx}.</span>
                <div>
                  <div style="font-weight: 700; font-size: 0.88rem; color: #f8fafc;">{n_name}</div>
                  <div style="font-size: 0.75rem; color: #94a3b8;">{n_agent}</div>
                </div>
              </div>
              <span style="{badge_style} font-size: 0.75rem; font-weight: 700;
              padding: 3px 10px; border-radius: 9999px;">
                {status_icon} {status_text}
              </span>
            </div>
            """
        pipe_html += "</div>"
        st.html(pipe_html)

    with col_action:
        st.html(
            """
            <div style="font-weight: 700; font-size: 0.85rem; color: #94a3b8;
            text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 8px;">
              Current Autonomous Action
            </div>
            """,
        )

        agent_name = current_action.get("agent", sdata.get("current_agent", "Autonomous Agent"))
        action_desc = current_action.get("description", "Executing repair workflow...")
        action_file = current_action.get("file")

        file_badge_html = (
            f"<div style='margin-top: 8px; font-size: 0.8rem; color: #94a3b8;'>"
            f"Target: <code style='color: #38bdf8;'>{action_file}</code></div>"
            if action_file else ""
        )

        st.html(
            f"""
            <div class="aegis-agent-card" style="height: calc(100% - 28px); display: flex;
            flex-direction: column; justify-content: space-between;">
              <div>
                <div class="aegis-agent-header">
                  <span class="aegis-agent-title">🤖 {agent_name}</span>
                  <span class="aegis-badge {badge_class}">● {status_label}</span>
                </div>
                <p style="font-size: 0.88rem; color: #f1f5f9; line-height: 1.5;
                margin: 10px 0 0 0;">
                  {action_desc}
                </p>
                {file_badge_html}
              </div>
              <div style="margin-top: 14px; font-size: 0.78rem; color: #94a3b8;
              border-top: 1px solid var(--border-subtle); padding-top: 10px;">
                Cycle: <strong>Iteration {current_iter} of {max_iter}</strong>
              </div>
            </div>
            """,
        )

    # ── D & E. ITERATION TRACKER & LIVE TEST METRICS ──────────────────────────
    st.html("<div style='height: 14px;'></div>")

    t_pass = tests_info.get("passed", 0)
    t_fail = tests_info.get("failed", 0)
    t_total = tests_info.get("total", t_pass + t_fail)
    t_exec = tests_info.get("executed", t_pass + t_fail)
    t_cov = tests_info.get("coverage_percent", 0.0)
    f_changed = files_info.get("changed", 0)

    st.html(
        f"""
        <div class="aegis-metric-grid">
          <div class="aegis-metric-card">
            <div class="aegis-metric-label"><span>🔄</span> Iteration Cycle</div>
            <div class="aegis-metric-val">
              {current_iter} <small style='font-size: 0.85rem; color: #94a3b8;'>/ {max_iter}</small>
            </div>
            <div class="aegis-metric-sub">Phase: {current_phase}</div>
          </div>
          <div class="aegis-metric-card">
            <div class="aegis-metric-label"><span>🧪</span> Pytest Executed</div>
            <div class="aegis-metric-val">
              {t_exec} <small style='font-size: 0.85rem; color: #94a3b8;'>/ {t_total} found</small>
            </div>
            <div class="aegis-metric-sub">
              <span style="color: #34d399; font-weight: 700;">{t_pass} passed</span> &bull;
              <span style="color: #f87171; font-weight: 700;">{t_fail} failed</span>
            </div>
          </div>
          <div class="aegis-metric-card">
            <div class="aegis-metric-label"><span>📊</span> Test Pass Rate</div>
            <div class="aegis-metric-val">{t_cov}%</div>
            <div class="aegis-metric-sub">Authoritative assertion rate</div>
          </div>
          <div class="aegis-metric-card">
            <div class="aegis-metric-label"><span>📝</span> Workspace Changes</div>
            <div class="aegis-metric-val">
              {f_changed} <small style='font-size: 0.85rem; color: #94a3b8;'>files changed</small>
            </div>
            <div class="aegis-metric-sub">Duration: {duration_str}</div>
          </div>
        </div>
        """,
    )

    # ── G. LIVE EXECUTION TIMELINE STREAM ──────────────────────────────────────
    if timeline_events:
        with st.expander("⏱️ Live Event Execution Stream", expanded=(run_status == "running")):
            for ev in reversed(timeline_events[-10:]):
                ts = ev.get("timestamp", "")
                ag = ev.get("agent", "Agent")
                msg = ev.get("message", "")
                it_tag = f"[Iter {ev.get('iteration')}]" if ev.get("iteration") else ""

                st.html(
                    f"""
                    <div style="display: flex; gap: 12px; font-size: 0.84rem; padding: 6px 0;
                    border-bottom: 1px solid rgba(255,255,255,0.04); align-items: baseline;">
                      <span style="color: #64748b; font-family: monospace; font-size: 0.78rem;">
                        {ts}
                      </span>
                      <span style="color: #38bdf8; font-weight: 700;">{ag}</span>
                      <span style="color: #94a3b8; font-size: 0.76rem;">{it_tag}</span>
                      <span style="color: #f8fafc; flex: 1;">{msg}</span>
                    </div>
                    """,
                )

    # ── H. STATUS HERO / COMPLETION & FAILURE BANNERS ─────────────────────────
    if is_rate_limit_err:
        render_rate_limit_alert()
    elif run_status in ("passed", "already_passing"):
        st.html(
            f"""
            <div class="aegis-status-banner passed">
              <div>
                <h3 class="aegis-banner-title">🎉 REPAIR COMPLETED & VERIFIED</h3>
                <p class="aegis-banner-desc">
                  Autonomous self-healing completed in <strong>{duration_str}</strong> across
                  <strong>{current_iter} iteration(s)</strong>.
                  All pytest assertions passed ({t_pass}/{t_total}) and reviewer approved patch.
                </p>
                <div style="margin-top: 10px; font-size: 0.84rem; color: #a7f3d0;
                display: flex; gap: 16px; flex-wrap: wrap;">
                  <span>✓ Root cause identified</span>
                  <span>✓ {f_changed} file(s) modified</span>
                  <span>✓ Tests passed (100%)</span>
                  <span>✓ Reviewer approved</span>
                </div>
              </div>
              <div style="font-size: 2.2rem;">🛡️</div>
            </div>
            """,
        )

        col_act1, col_act2, col_act3, col_act4 = st.columns(4)
        with col_act1:
            if st.button("🔀 View Code Changes", key="btn_view_diffs", use_container_width=True):
                st.session_state["nav_view"] = "🔀 Code Changes"
                st.rerun()
        with col_act2:
            if st.button("🧪 View Test Runs", key="btn_view_tests", use_container_width=True):
                st.session_state["nav_view"] = "🧪 Test Runs"
                st.rerun()
        with col_act3:
            if st.button("📊 Repair History", key="btn_view_hist_done", use_container_width=True):
                st.session_state["nav_view"] = "📊 Repair History"
                st.rerun()
        with col_act4:
            download_url = f"{api_url}/runs/{active_run_id}/download"
            try:
                dl_resp = _safe_get(download_url, timeout=30, stream=True)
                if dl_resp and dl_resp.status_code == 200:
                    filename = _extract_filename_from_content_disposition(dl_resp, active_run_id)
                    st.download_button(
                        label="⬇️ Download (.zip)",
                        data=dl_resp.content,
                        file_name=filename,
                        mime="application/zip",
                        type="primary",
                        key="btn_live_dl_hero",
                        use_container_width=True,
                    )
            except Exception:
                pass

    elif run_status in ("failed", "error", "stalled"):
        fail_desc = (
            final_summary
            or f"Autonomous repair reached iteration {current_iter}/{max_iter} without passing."
        )
        st.html(
            f"""
            <div class="aegis-status-banner failed">
              <div>
                <h3 class="aegis-banner-title">❌ REPAIR TERMINATED WITHOUT PASSING FIX</h3>
                <p class="aegis-banner-desc">{fail_desc}</p>
                <div style="margin-top: 8px; font-size: 0.82rem; color: #fca5a5;">
                  Prior agent telemetry, architecture plans, and diagnostics are preserved below.
                </div>
              </div>
              <div style="font-size: 2.2rem;">🛑</div>
            </div>
            """,
        )

        col_f1, col_f2 = st.columns(2)
        with col_f1:
            if st.button(
                "🚀 Start New Repair",
                key="btn_fail_new_repair",
                type="primary",
                use_container_width=True,
            ):
                st.session_state["nav_view"] = "🚀 New Repair"
                st.rerun()
        with col_f2:
            if st.button("📊 View Repair History", key="btn_fail_hist", use_container_width=True):
                st.session_state["nav_view"] = "📊 Repair History"
                st.rerun()

    elif run_status == "cancelled":
        render_warning_alert(
            "Autonomous Repair Cancelled",
            final_summary or "The repair run was cancelled by user.",
        )

    # ── J. MULTI-TAB EXECUTION WORKSPACE ──────────────────────────────────────
    st.markdown("---")
    console_tabs = st.tabs([
        "📅 Overview & Stepper",
        "🏛️ Architect Agent",
        "💻 Coder Agent",
        "🧪 Pytest Results",
        "🔍 Reviewer Audit",
        "🔀 Code Changes",
    ])

    is_already_passing = (run_status == "already_passing")

    with console_tabs[0]:
        st.markdown("### 📅 Execution Lifecycle Stepper")
        render_timeline(run_status, iterations, final_summary)

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

    with console_tabs[5]:
        render_code_diff_viewer(iterations, is_already_passing)

    # ── K. LIGHTWEIGHT REAL-TIME POLLING ──────────────────────────────────────
    if run_status == "running":
        time.sleep(2)
        st.rerun()
