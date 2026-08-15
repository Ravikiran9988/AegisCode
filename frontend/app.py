"""
Streamlit Frontend Dashboard for AegisCode — Phase 4.

Provides an interactive user interface to:
1. Upload Python project ZIP files.
2. Trigger autonomous self-healing LangGraph repair runs.
3. View real-time status, iteration timelines, test results, reviewer decisions, and git diffs.
"""

import os
import time

import requests
import streamlit as st

st.set_page_config(
    page_title="AegisCode — Self-Healing Multi-Agent SE System",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded",
)

API_BASE_URL = os.environ.get("BACKEND_URL", "http://localhost:8000")

# ── Custom CSS for modern dark UI ──────────────────────────────────────────────
st.markdown(
    """
    <style>
    .main-title { font-size: 2.2rem; font-weight: 700; color: #4F46E5; margin-bottom: 0.2rem; }
    .subtitle { font-size: 1.0rem; color: #9CA3AF; margin-bottom: 1.5rem; }
    .status-badge { padding: 4px 12px; border-radius: 6px; font-weight: 600; font-size: 0.9rem; }
    .badge-passed { background-color: #059669; color: white; }
    .badge-running { background-color: #2563EB; color: white; }
    .badge-failed { background-color: #DC2626; color: white; }
    .badge-stalled { background-color: #D97706; color: white; }
    </style>
    """,
    unsafe_allow_html=True,
)

# ── Sidebar Configuration ──────────────────────────────────────────────────────
st.sidebar.title("🛡️ AegisCode Settings")
backend_url = st.sidebar.text_input("Backend URL (root)", value=API_BASE_URL)
api_url = backend_url.rstrip("/") + "/api"

# Health Check Indicator
try:
    health_resp = requests.get(f"{backend_url}/health", timeout=3)
    if health_resp.status_code == 200:
        hdata = health_resp.json()
        st.sidebar.success(f"Backend Online (LLM: {hdata.get('llm_provider')})")
    else:
        st.sidebar.error("Backend Degraded")
except Exception:
    st.sidebar.error("Backend Unreachable")

st.sidebar.markdown("---")
st.sidebar.markdown("**Self-Healing Architecture**")
st.sidebar.markdown(
    """
    - **Architect Node**: Analyzes project & test logs
    - **Coder Node**: Generates & applies targeted patch
    - **Test Node**: Authoritative Pytest execution
    - **Reviewer Node**: Independent audit & regression risk
    """
)

# ── Main Header ────────────────────────────────────────────────────────────────
st.markdown('<div class="main-title">AegisCode</div>', unsafe_allow_html=True)
st.markdown(
    '<div class="subtitle">Autonomous Self-Healing Multi-Agent Software Engineering System</div>',
    unsafe_allow_html=True,
)

tabs = st.tabs(["🚀 Launch Repair Run", "📊 Run Timeline & Results", "ℹ️ System Overview"])

# ── Tab 1: Launch Repair Run ───────────────────────────────────────────────────
with tabs[0]:
    st.subheader("1. Upload Python Project (.zip)")
    uploaded_file = st.file_uploader(
        "Choose a project ZIP containing failing pytest tests", type=["zip"]
    )

    col1, col2 = st.columns([1, 2])

    if uploaded_file is not None:
        with col1:
            if st.button("📤 Upload & Initialize Project", type="primary"):
                with st.spinner("Validating and extracting project workspace..."):
                    try:
                        file_tuple = (
                            uploaded_file.name, uploaded_file.getvalue(), "application/zip"
                        )
                        files = {"file": file_tuple}
                        res = requests.post(f"{api_url}/projects/upload", files=files)
                        if res.status_code == 201:
                            data = res.json()
                            st.session_state["project_id"] = data["project_id"]
                            st.success(
                                f"Project Uploaded! ID: `{data['project_id']}` "
                                f"({data['file_count']} files)"
                            )
                        else:
                            st.error(f"Upload failed: {res.text}")
                    except Exception as exc:
                        st.error(f"Connection error: {exc}")

    if "project_id" in st.session_state:
        st.markdown("---")
        st.subheader("2. Configure & Start Self-Healing Repair")
        max_iters = st.slider("Maximum Repair Iterations", min_value=1, max_value=10, value=5)

        if st.button("⚡ Start Autonomous Repair Graph", type="primary"):
            with st.spinner("Initializing repair run..."):
                try:
                    payload = {
                        "project_id": st.session_state["project_id"],
                        "max_iterations": max_iters,
                    }
                    create_res = requests.post(f"{api_url}/runs", json=payload)
                    if create_res.status_code == 201:
                        run_id = create_res.json()["run_id"]
                        st.session_state["active_run_id"] = run_id

                        # Trigger repair loop
                        repair_res = requests.post(f"{api_url}/runs/{run_id}/repair")
                        if repair_res.status_code in (200, 202):
                            st.success(f"Autonomous Repair Graph launched! Run ID: `{run_id}`")
                            st.rerun()
                        else:
                            st.error(f"Failed to launch repair graph: {repair_res.text}")
                    else:
                        st.error(f"Failed to create run: {create_res.text}")
                except Exception as exc:
                    st.error(f"Error launching repair: {exc}")

# ── Tab 2: Run Timeline & Results ──────────────────────────────────────────────
with tabs[1]:
    active_run_id = (
        st.session_state.get("active_run_id") or
        st.text_input("Enter Run ID to inspect", value="")
    )

    if active_run_id:
        try:
            status_resp = requests.get(f"{api_url}/runs/{active_run_id}/status")
            results_resp = requests.get(f"{api_url}/runs/{active_run_id}/results")

            if status_resp.status_code == 200 and results_resp.status_code == 200:
                sdata = status_resp.json()
                rdata = results_resp.json()

                # Status Metrics Bar
                mcol1, mcol2, mcol3, mcol4, mcol5 = st.columns(5)
                mcol1.metric("Run Status", sdata.get("status", "unknown").upper())
                mcol2.metric(
                    "Current Iteration",
                    f"{sdata.get('current_iteration')}/{sdata.get('max_iterations')}",
                )
                mcol3.metric(
                    "Pytest Status",
                    "PASSING" if sdata.get("tests_passed") else "FAILING",
                )
                mcol4.metric(
                    "Reviewer Approved",
                    "YES" if sdata.get("review_approved") else "NO",
                )
                mcol5.metric("Total Iterations", len(rdata.get("iterations", [])))

                st.markdown("---")

                # Auto-refresh if running
                if sdata.get("status") == "running":
                    st.info("🔄 Repair Graph running in background... auto-refreshing in 3s")
                    time.sleep(3)
                    st.rerun()

                # Iteration Timeline View
                st.subheader("Step-by-Step Iteration Timeline")
                iterations = rdata.get("iterations", [])

                if not iterations:
                    st.warning("No iterations completed yet.")
                else:
                    it_tabs = st.tabs([f"Iteration {it['iteration_number']}" for it in iterations])
                    for idx, it in enumerate(iterations):
                        with it_tabs[idx]:
                            col_arch, col_code = st.columns(2)

                            with col_arch:
                                st.markdown("##### 🏛️ Architect Agent Plan")
                                plan = it.get("architecture_plan") or {}
                                st.write(f"**Summary:** {plan.get('summary', 'N/A')}")
                                rel_files = ", ".join(plan.get("relevant_files", []))
                                st.write(f"**Relevant Files:** `{rel_files}`")
                                issues = plan.get('suspected_issues', [])
                                st.write(f"**Suspected Issues:** {issues}")
                                st.write(f"**Test Strategy:** {plan.get('test_strategy', 'N/A')}")

                            with col_code:
                                st.markdown("##### 💻 Coder Agent Modification")
                                change = it.get("code_change") or {}
                                st.write(f"**Target File:** `{change.get('file_path', 'N/A')}`")
                                st.write(f"**Change Type:** `{change.get('change_type', 'N/A')}`")
                                st.write(f"**Explanation:** {change.get('explanation', 'N/A')}")

                            st.markdown("---")

                            col_test, col_rev = st.columns(2)

                            with col_test:
                                st.markdown("##### 🧪 Pytest Execution Results")
                                tres = it.get("test_results") or {}
                                st.write(
                                    f"**Exit Code:** `{tres.get('exit_code')}` | "
                                    f"**Passed:** {tres.get('passed')} | "
                                    f"**Failed:** {tres.get('failed')}"
                                )
                                with st.expander("Show Captured Stdout"):
                                    st.code(tres.get("stdout", ""), language="text")

                            with col_rev:
                                st.markdown("##### 🔍 Reviewer Agent Audit")
                                rev = it.get("review_result") or {}
                                st.write(f"**Approved:** `{rev.get('approved')}`")
                                st.write(f"**Root Cause Fixed:** `{rev.get('root_cause_fixed')}`")
                                st.write(f"**Regression Risk:** `{rev.get('regression_risk')}`")
                                st.write(f"**Reasoning:** {rev.get('reasoning', 'N/A')}")

            else:
                st.warning("Run not found or results unavailable.")
        except Exception as exc:
            st.error(f"Error fetching run details: {exc}")

# ── Tab 3: System Overview ─────────────────────────────────────────────────────
with tabs[2]:
    st.markdown("### AegisCode State Machine Architecture")
    st.code(
        """
        START
          │
          ▼
        Initial Test Node (Fast-path exit if already passing)
          │
          ▼
        Architect Node (Analyzes failure & creates ArchitecturePlan)
          │
          ▼
        Coder Node (Generates CodeChange & evaluates security policy)
          │
          ▼
        Test Node (Authoritative Pytest execution)
          │
          ▼
        Reviewer Node (Independent audit & regression assessment)
          │
          ▼
        Decision Router
          ├── All Passed & Approved  --> END (status="passed")
          ├── Max Iterations Reached --> END (status="failed")
          ├── Repeated Failure       --> END (status="stalled")
          └── Retry                  --> ARCHITECT NODE (Iteration N+1)
        """,
        language="text",
    )
