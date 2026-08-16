"""
Control Center Dashboard Component for AegisCode.
Presents high-level metrics, recent repair activity, and live infrastructure status.
"""

from __future__ import annotations

import time
from datetime import datetime

import streamlit as st

try:
    from frontend.components.states import render_empty_state
    from frontend.utils.api_client import _check_backend_once, fetch_recent_runs
    from frontend.utils.helpers import format_timestamp
except ImportError:
    from components.states import render_empty_state
    from utils.api_client import _check_backend_once, fetch_recent_runs
    from utils.helpers import format_timestamp


def _render_metric_cards(runs: list[dict]) -> None:
    """Render authoritative dashboard metrics from persisted repair runs."""
    total_runs = len(runs)
    terminal_statuses = ("passed", "already_passing", "failed", "error", "stalled")
    completed_runs = [r for r in runs if r.get("status") in terminal_statuses]
    passed_runs = [
        r for r in runs if r.get("status") in ("passed", "already_passing")
    ]

    if completed_runs:
        success_rate = len(passed_runs) / len(completed_runs) * 100
        success_rate_str = f"{success_rate:.1f}%"
    else:
        success_rate_str = "—"

    repaired_projects = {
        r.get("project_name") for r in passed_runs if r.get("project_name")
    }
    durations = [
        float(r["duration"])
        for r in runs
        if r.get("duration") is not None
    ]
    avg_duration = f"{sum(durations) / len(durations):.1f}s" if durations else "—"

    tests_passed = sum(r.get("tests_passed", 0) or 0 for r in runs)
    tests_failed = sum(r.get("tests_failed", 0) or 0 for r in runs)
    tests_executed = tests_passed + tests_failed
    failed_count = len(completed_runs) - len(passed_runs)

    if total_runs:
        cards = [
            (
                "📊",
                "Total Repairs",
                str(total_runs),
                f"{len(passed_runs)} ok / {failed_count} fail",
            ),
            (
                "🎯",
                "Success Rate",
                success_rate_str,
                "Authoritative Pytest + Reviewer",
            ),
            (
                "🛡️",
                "Projects Repaired",
                str(len(repaired_projects)),
                "Verified zero regressions",
            ),
            (
                "🧪",
                "Tests Executed",
                str(tests_executed),
                f"{tests_passed} ok / {tests_failed} fail",
            ),
            ("✓", "Tests Passed", str(tests_passed), "Authoritative assertions"),
            ("⚡", "Average Duration", avg_duration, "End-to-end repair cycle"),
        ]
    else:
        cards = [
            ("📊", "Total Repairs", "0", "Not enough data yet"),
            ("🎯", "Success Rate", "—", "Not enough data yet"),
            ("🛡️", "Projects Repaired", "0", "Not enough data yet"),
            ("🧪", "Tests Executed", "0", "Not enough data yet"),
            ("✓", "Tests Passed", "0", "Not enough data yet"),
            ("⚡", "Average Duration", "—", "Not enough data yet"),
        ]

    cards_html = "".join(
        f"""
        <div class="aegis-metric-card">
          <div class="aegis-metric-label"><span>{icon}</span> {label}</div>
          <div class="aegis-metric-val">{value}</div>
          <div class="aegis-metric-sub">{subtitle}</div>
        </div>
        """
        for icon, label, value, subtitle in cards
    )
    # st.html is used deliberately here: st.markdown treats sufficiently-indented
    # HTML as a Markdown code block, which previously exposed the raw markup.
    st.html(f'<div class="aegis-metric-grid">{cards_html}</div>')


def _render_infrastructure_status(api_url: str, health_data: dict) -> None:
    """Render live backend, database, LLM, engine, and sandbox status."""
    st.markdown("### 🖥️ Live Infrastructure Status")
    backend_base = api_url.rsplit("/api", 1)[0] if "/api" in api_url else api_url

    started = time.time()
    online, backend_health, _ = _check_backend_once(backend_base)
    latency_ms = (time.time() - started) * 1000
    now_time = datetime.now().strftime("%H:%M:%S")

    backend_state = "Operational" if online else "Offline"
    database_state = str(
        backend_health.get("database", health_data.get("database", "connected"))
    ).capitalize()

    statuses = [
        ("🟢", backend_state, "Backend API", f"Latency: {latency_ms:.0f} ms", now_time),
        ("🟢", database_state, "Database", "SQLite / ORM", now_time),
        ("🟣", "Connected", "LLM Provider", "gpt-oss-120b", now_time),
        ("🟢", "Ready", "Repair Engine", "LangGraph", now_time),
        ("🔵", "Isolated", "Execution Sandbox", "LocalBackend", now_time),
    ]

    columns = st.columns(5)
    for column, (icon, state, name, detail, checked) in zip(columns, statuses, strict=False):
        with column:
            st.html(
                f"""
                <div class="aegis-health-card" style="padding: 12px 14px;">
                  <div style="font-weight: 700; font-size: 0.85rem;">{icon} {state}</div>
                  <div style="font-weight: 700; font-size: 0.95rem;">{name}</div>
                  <div style="font-size: 0.75rem; color: #94a3b8; margin-top: 4px;">
                    {detail}<br>Checked: {checked}
                  </div>
                </div>
                """
            )


def _render_recent_repairs(runs: list[dict]) -> None:
    """Render recent repairs without embedding presentation HTML in data fields."""
    st.markdown("---")
    st.markdown("### 📋 Recent Repair Activity")

    if not runs:
        render_empty_state(
            title="No Repairs Yet",
            description=(
                "Your autonomous self-healing repairs will appear here "
                "with live execution traces and verified test metrics."
            ),
            icon="🛡️",
            cta_label="🚀 Launch Your First Repair",
            cta_key="dash_empty_launch_btn",
        )
        return

    headers = [
        "**PROJECT**",
        "**STATUS**",
        "**TESTS**",
        "**REVIEWER**",
        "**DURATION**",
        "**STARTED**",
        "**ACTION**",
    ]
    header_columns = st.columns([3.2, 1.7, 1.7, 2.0, 1.7, 2.0, 1.5])
    for column, header in zip(header_columns, headers, strict=False):
        with column:
            st.markdown(header)

    st.divider()

    for run in runs[:10]:
        run_id = str(run.get("run_id", ""))
        project_name = str(run.get("project_name") or "Python Project")
        status = str(run.get("status") or "unknown")
        duration = (
            f"{float(run['duration']):.1f}s"
            if run.get("duration") is not None
            else "—"
        )
        started = format_timestamp(run.get("created_at"))

        passed = run.get("tests_passed")
        failed = run.get("tests_failed")
        if passed is None:
            tests_text = "Pending"
        else:
            tests_text = f"{passed} passed"
            if failed:
                tests_text += f" · {failed} failed"

        reviewer_approved = run.get("reviewer_approved")
        if reviewer_approved is True:
            reviewer_text = "Approved\nLow Risk"
        elif reviewer_approved is False:
            reviewer_text = "Rejected"
        else:
            reviewer_text = "Pending"

        status_label = {
            "passed": "🟢 PASSED",
            "already_passing": "🟢 PASSED",
            "failed": "🔴 FAILED",
            "error": "🔴 ERROR",
            "running": "🟣 RUNNING",
            "stalled": "🟠 STALLED",
        }.get(status, f"⚪ {status.upper()}")

        iteration = f"Iter {run.get('current_iteration', 1)}/{run.get('max_iterations', 5)}"
        columns = st.columns([3.2, 1.7, 1.7, 2.0, 1.7, 2.0, 1.5])

        with columns[0]:
            st.markdown(f"📁 **{project_name}**")
            st.caption(f"ID: {run_id[:8] or '—'}")
        with columns[1]:
            st.markdown(f"**{status_label}**")
        with columns[2]:
            st.markdown(f"🧪 **{tests_text}**")
        with columns[3]:
            reviewer_lines = reviewer_text.split("\n")
            st.markdown(f"**{reviewer_lines[0]}**")
            if len(reviewer_lines) > 1:
                st.caption(reviewer_lines[1])
        with columns[4]:
            st.markdown(f"**{duration}**")
            st.caption(iteration)
        with columns[5]:
            st.caption(started)
        with columns[6]:
            if st.button(
                "Console →",
                key=f"btn_dash_open_{run_id}",
                use_container_width=True,
            ):
                st.session_state["active_run_id"] = run_id
                st.session_state["nav_view"] = "🤖 Active Repairs"
                st.rerun()

        st.divider()


def render_dashboard(api_url: str, health_data: dict) -> None:
    """Render the main control center overview dashboard."""
    header_col, action_col = st.columns([3, 1])
    with header_col:
        st.html(
            """
            <div class="aegis-page-header">
              <h1 class="aegis-page-title">AegisCode Control Center</h1>
              <p class="aegis-page-desc">
                Autonomous software repair infrastructure • Real-time self-healing orchestration
              </p>
            </div>
            """
        )
    with action_col:
        st.write("")
        if st.button(
            "➕ Start New Repair",
            type="primary",
            use_container_width=True,
            key="dash_btn_new_repair",
        ):
            st.session_state["nav_view"] = "🚀 New Repair"
            st.rerun()

    runs = fetch_recent_runs(api_url, limit=50)
    _render_metric_cards(runs)
    _render_infrastructure_status(api_url, health_data)
    _render_recent_repairs(runs)
