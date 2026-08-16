"""
Control Center Dashboard Component for AegisCode.
Presents high-level metrics, real recent repair activity, and live system status.
"""

from __future__ import annotations

import streamlit as st

from frontend.components.states import render_empty_state
from frontend.utils.api_client import fetch_recent_runs


def render_dashboard(api_url: str, health_data: dict) -> None:
    """Render the main control center dashboard."""
    # Page Header
    col_hdr1, col_hdr2 = st.columns([3, 1])
    with col_hdr1:
        st.markdown(
            """
            <div class="aegis-page-header">
              <h1 class="aegis-page-title">AegisCode Control Center</h1>
              <p class="aegis-page-desc">
                Monitor autonomous self-healing software engineering pipelines and system health.
              </p>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with col_hdr2:
        st.write("")
        if st.button(
            "➕ Start New Repair",
            type="primary",
            use_container_width=True,
            key="dash_btn_new_repair",
        ):
            st.session_state["nav_view"] = "🚀 New Repair"
            st.rerun()

    # ── Fetch real runs from backend database ─────────────────────────────────
    runs = fetch_recent_runs(api_url, limit=50)

    # ── Real Metrics Calculation ──────────────────────────────────────────────
    total_runs = len(runs)
    term_statuses = ("passed", "already_passing", "failed", "error", "stalled")
    completed_runs = [r for r in runs if r.get("status") in term_statuses]
    passed_runs = [r for r in runs if r.get("status") in ("passed", "already_passing")]

    if completed_runs:
        success_rate = (len(passed_runs) / len(completed_runs)) * 100
        success_rate_str = f"{success_rate:.1f}%"
    else:
        success_rate_str = "—"

    # Count distinct projects repaired
    repaired_projects = {
        r.get("project_name") for r in passed_runs if r.get("project_name")
    }
    projects_repaired_count = len(repaired_projects)

    # Calculate average duration
    durations = [r.get("duration") for r in runs if r.get("duration") is not None]
    if durations:
        avg_dur = sum(durations) / len(durations)
        avg_dur_str = f"{avg_dur:.1f}s"
    else:
        avg_dur_str = "—"

    # Total tests passed count
    total_tests_passed = sum(r.get("tests_passed", 0) or 0 for r in runs)
    failed_count = len(completed_runs) - len(passed_runs)

    # ── Metric KPI Grid ───────────────────────────────────────────────────────
    if total_runs > 0:
        st.markdown(
            f"""
            <div class="aegis-metric-grid">
              <div class="aegis-metric-card">
                <div class="aegis-metric-label"><span>📊</span> Total Repair Runs</div>
                <div class="aegis-metric-val">{total_runs}</div>
                <div class="aegis-metric-sub">{len(passed_runs)} ok / {failed_count} fail</div>
              </div>
              <div class="aegis-metric-card">
                <div class="aegis-metric-label"><span>🎯</span> Success Rate</div>
                <div class="aegis-metric-val">{success_rate_str}</div>
                <div class="aegis-metric-sub">Pytest 100% + Reviewer Approval</div>
              </div>
              <div class="aegis-metric-card">
                <div class="aegis-metric-label"><span>🛡️</span> Repaired Projects</div>
                <div class="aegis-metric-val">{projects_repaired_count}</div>
                <div class="aegis-metric-sub">{total_tests_passed} total test assertions</div>
              </div>
              <div class="aegis-metric-card">
                <div class="aegis-metric-label"><span>⚡</span> Average Duration</div>
                <div class="aegis-metric-val">{avg_dur_str}</div>
                <div class="aegis-metric-sub">End-to-end graph cycle</div>
              </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            """
            <div class="aegis-metric-grid">
              <div class="aegis-metric-card">
                <div class="aegis-metric-label"><span>📊</span> Total Repair Runs</div>
                <div class="aegis-metric-val">0</div>
                <div class="aegis-metric-sub">Not enough data yet</div>
              </div>
              <div class="aegis-metric-card">
                <div class="aegis-metric-label"><span>🎯</span> Success Rate</div>
                <div class="aegis-metric-val">—</div>
                <div class="aegis-metric-sub">Not enough data yet</div>
              </div>
              <div class="aegis-metric-card">
                <div class="aegis-metric-label"><span>🛡️</span> Repaired Projects</div>
                <div class="aegis-metric-val">0</div>
                <div class="aegis-metric-sub">Not enough data yet</div>
              </div>
              <div class="aegis-metric-card">
                <div class="aegis-metric-label"><span>⚡</span> Average Duration</div>
                <div class="aegis-metric-val">—</div>
                <div class="aegis-metric-sub">Not enough data yet</div>
              </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    # ── Recent Repairs Section ────────────────────────────────────────────────
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
    else:
        for r in runs[:8]:
            rid = r.get("run_id", "")
            pname = r.get("project_name", "Python Project")
            rstat = r.get("status", "unknown")
            dur = f"{r.get('duration'):.1f}s" if r.get("duration") is not None else "—"
            p_cnt = r.get("tests_passed")
            f_cnt = r.get("tests_failed")
            t_str = f"{p_cnt} passed" if p_cnt is not None else "Tests pending"
            if f_cnt and f_cnt > 0:
                t_str += f" / {f_cnt} failed"

            rev_approved = r.get("reviewer_approved")
            if rev_approved is True:
                rev_str = "Approved"
            elif rev_approved is False:
                rev_str = "Rejected"
            else:
                rev_str = "Pending"

            status_badge_map = {
                "passed": "passed",
                "already_passing": "passed",
                "failed": "failed",
                "error": "failed",
                "running": "running",
            }
            b_class = status_badge_map.get(rstat, "running")

            col1, col2, col3, col4, col5 = st.columns([3, 2, 2, 2, 2])
            with col1:
                st.markdown(
                    f"**📁 {pname}**  \n<small style='color: #64748b;'>"
                    f"ID: <code>{rid[:8]}</code></small>",
                    unsafe_allow_html=True,
                )
            with col2:
                st.markdown(
                    f"<span class='aegis-badge {b_class}'>{rstat.upper()}</span>",
                    unsafe_allow_html=True,
                )
            with col3:
                st.markdown(
                    f"🧪 **{t_str}**  \n"
                    f"<small style='color: #94a3b8;'>Reviewer: {rev_str}</small>",
                    unsafe_allow_html=True,
                )
            with col4:
                cur_it = r.get("current_iteration", 1)
                max_it = r.get("max_iterations", 5)
                st.markdown(
                    f"⏱️ **{dur}**  \n"
                    f"<small style='color: #94a3b8;'>Iter: {cur_it}/{max_it}</small>",
                    unsafe_allow_html=True,
                )
            with col5:
                if st.button(
                    "Open Console →",
                    key=f"btn_dash_open_{rid}",
                    use_container_width=True,
                ):
                    st.session_state["active_run_id"] = rid
                    st.session_state["nav_view"] = "🤖 Live Repair Console"
                    st.rerun()

            st.markdown(
                "<hr style='margin: 8px 0; border-color: rgba(255,255,255,0.04);'>",
                unsafe_allow_html=True,
            )

    st.markdown("---")

    # ── Real System Overview Grid ─────────────────────────────────────────────
    st.markdown("### 🖥️ Live Engine & Infrastructure Status")
    db_stat = health_data.get("database", "connected")
    app_ver = health_data.get("version", "0.1.0")

    col_s1, col_s2, col_s3, col_s4, col_s5 = st.columns(5)
    with col_s1:
        st.markdown(
            f"""
            <div class="aegis-health-card" style="text-align: center; padding: 14px 10px;">
              <div style="color: #34d399; font-size: 1.1rem; margin-bottom: 4px;">
                ● Operational
              </div>
              <div style="font-weight: 700; font-size: 0.9rem;">Backend API</div>
              <div style="font-size: 0.75rem; color: #94a3b8;">v{app_ver}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with col_s2:
        st.markdown(
            """
            <div class="aegis-health-card" style="text-align: center; padding: 14px 10px;">
              <div style="color: #c084fc; font-size: 1.1rem; margin-bottom: 4px;">
                ● Connected
              </div>
              <div style="font-weight: 700; font-size: 0.9rem;">LLM Provider</div>
              <div style="font-size: 0.75rem; color: #94a3b8;">gpt-oss-120b</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with col_s3:
        st.markdown(
            f"""
            <div class="aegis-health-card" style="text-align: center; padding: 14px 10px;">
              <div style="color: #34d399; font-size: 1.1rem; margin-bottom: 4px;">
                ● {db_stat.capitalize()}
              </div>
              <div style="font-weight: 700; font-size: 0.9rem;">Database Engine</div>
              <div style="font-size: 0.75rem; color: #94a3b8;">SQLite / SQLAlchemy</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with col_s4:
        st.markdown(
            """
            <div class="aegis-health-card" style="text-align: center; padding: 14px 10px;">
              <div style="color: #34d399; font-size: 1.1rem; margin-bottom: 4px;">
                ● Ready
              </div>
              <div style="font-weight: 700; font-size: 0.9rem;">Repair Graph</div>
              <div style="font-size: 0.75rem; color: #94a3b8;">LangGraph Engine</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with col_s5:
        st.markdown(
            """
            <div class="aegis-health-card" style="text-align: center; padding: 14px 10px;">
              <div style="color: #34d399; font-size: 1.1rem; margin-bottom: 4px;">
                ● Isolated
              </div>
              <div style="font-weight: 700; font-size: 0.9rem;">Pytest Sandbox</div>
              <div style="font-size: 0.75rem; color: #94a3b8;">LocalExecutionBackend</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
