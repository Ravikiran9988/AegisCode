"""
Repair History & Run Browser Component for AegisCode.
Presents filterable, searchable historical runs with status, test pass rates, and drill-down.
"""

from __future__ import annotations

import streamlit as st

try:
    from frontend.components.states import render_empty_state
    from frontend.utils.api_client import fetch_recent_runs
    from frontend.utils.helpers import format_timestamp
except ImportError:
    from components.states import render_empty_state
    from utils.api_client import fetch_recent_runs
    from utils.helpers import format_timestamp


def render_history(api_url: str) -> None:
    """Render the searchable repair run history browser."""
    st.markdown(
        """
        <div class="aegis-page-header">
          <h1 class="aegis-page-title">Repair Run History</h1>
          <p class="aegis-page-desc">
            Search, inspect, and analyze past autonomous self-healing execution runs.
          </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # Fetch runs
    runs = fetch_recent_runs(api_url, limit=100)

    if not runs:
        render_empty_state(
            title="No Historical Runs",
            description=(
                "No repair runs recorded in the database yet. "
                "Launch a repair to see results here."
            ),
            icon="📜",
            cta_label="🚀 Launch New Repair",
            cta_key="hist_empty_cta",
        )
        return

    # Filters and Search
    col_f1, col_f2 = st.columns([2, 1])
    with col_f1:
        search_query = st.text_input(
            "Search by Project or Run ID",
            placeholder="e.g. calculator, 3fa85f64...",
            key="hist_search_input",
        ).strip().lower()

    with col_f2:
        status_filter = st.selectbox(
            "Filter by Status",
            ["All Statuses", "Passed / Healthy", "Failed / Error", "Running"],
            key="hist_status_select",
        )

    # Filter runs
    filtered_runs = []
    for r in runs:
        rid = r.get("run_id", "").lower()
        pname = r.get("project_name", "").lower()
        rstat = r.get("status", "").lower()

        # Search match
        if search_query and (search_query not in rid and search_query not in pname):
            continue

        # Status filter match
        if status_filter == "Passed / Healthy" and rstat not in ("passed", "already_passing"):
            continue
        elif status_filter == "Failed / Error" and rstat not in ("failed", "error", "stalled"):
            continue
        elif status_filter == "Running" and rstat != "running":
            continue

        filtered_runs.append(r)

    st.markdown(
        f"<small style='color: #94a3b8;'>Displaying {len(filtered_runs)} of {len(runs)} "
        "total runs</small>",
        unsafe_allow_html=True,
    )
    st.markdown("<div style='height: 8px;'></div>", unsafe_allow_html=True)

    if not filtered_runs:
        st.info("🔍 No runs match the current search filters.")
        return

    # Table Header
    col_h1, col_h2, col_h3, col_h4, col_h5, col_h6 = st.columns([3, 2, 2, 2, 2, 2])
    with col_h1:
        st.markdown("**PROJECT**")
    with col_h2:
        st.markdown("**STATUS**")
    with col_h3:
        st.markdown("**TESTS**")
    with col_h4:
        st.markdown("**REVIEWER**")
    with col_h5:
        st.markdown("**DURATION / DATE**")
    with col_h6:
        st.markdown("**ACTION**")

    st.markdown(
        "<hr style='margin: 4px 0 10px 0; border-color: rgba(255,255,255,0.08);'>",
        unsafe_allow_html=True,
    )

    for r in filtered_runs:
        rid = r.get("run_id", "")
        pname = r.get("project_name", "Python Project")
        rstat = r.get("status", "unknown")
        dur_val = r.get("duration")
        dur_str = f"{dur_val:.1f}s" if dur_val is not None else "—"
        date_str = format_timestamp(r.get("created_at"))

        p_cnt = r.get("tests_passed")
        f_cnt = r.get("tests_failed")
        if p_cnt is not None:
            t_str = f"{p_cnt} passed"
            if f_cnt and f_cnt > 0:
                t_str += f", {f_cnt} fail"
        else:
            t_str = "Pending"

        rev_approved = r.get("reviewer_approved")
        if rev_approved is True:
            rev_str = "Approved"
        elif rev_approved is False:
            rev_str = "Rejected"
        else:
            rev_str = "—"

        if rstat in ("passed", "already_passing"):
            badge_class = "passed"
        elif rstat in ("failed", "error"):
            badge_class = "failed"
        else:
            badge_class = "running"

        c1, c2, c3, c4, c5, c6 = st.columns([3, 2, 2, 2, 2, 2])
        with c1:
            st.markdown(
                f"**{pname}**  \n<small style='color: #64748b;'><code>{rid[:8]}</code></small>",
                unsafe_allow_html=True,
            )
        with c2:
            st.markdown(
                f"<span class='aegis-badge {badge_class}'>{rstat.upper()}</span>",
                unsafe_allow_html=True,
            )
        with c3:
            st.markdown(f"**{t_str}**")
        with c4:
            st.markdown(f"**{rev_str}**")
        with c5:
            st.markdown(
                f"**{dur_str}**  \n<small style='color: #94a3b8;'>{date_str}</small>",
                unsafe_allow_html=True,
            )
        with c6:
            if st.button("Inspect →", key=f"hist_open_{rid}", use_container_width=True):
                st.session_state["active_run_id"] = rid
                st.session_state["nav_view"] = "🤖 Active Repairs"
                st.rerun()

        st.markdown(
            "<hr style='margin: 6px 0; border-color: rgba(255,255,255,0.03);'>",
            unsafe_allow_html=True,
        )
