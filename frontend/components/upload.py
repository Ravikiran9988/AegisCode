"""
New Repair & Project Upload Component for AegisCode.
Automated workspace initialization and autonomous repair lifecycle management.
"""

from __future__ import annotations

import time

import streamlit as st

try:
    from frontend.components.states import (
        render_error_alert,
        render_warning_alert,
    )
    from frontend.utils.api_client import _safe_post, fetch_run_status
    from frontend.utils.helpers import _parse_api_error, format_file_size
except ImportError:
    from components.states import (
        render_error_alert,
        render_warning_alert,
    )
    from utils.api_client import _safe_post, fetch_run_status
    from utils.helpers import _parse_api_error, format_file_size


def render_upload(api_url: str) -> None:
    """Render the project upload, configuration, and autonomous repair lifecycle."""
    st.markdown(
        """
        <div class="aegis-page-header"
        style="text-align: center; max-width: 680px; margin: 0 auto 28px auto;">
          <h1 class="aegis-page-title">Start Autonomous Repair</h1>
          <p class="aegis-page-desc">
            Upload a Python project archive and let AegisCode diagnose defects,
            synthesize verified patches, and independently audit regressions.
          </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # Centered Workspace Card
    col_u1, col_u2, col_u3 = st.columns([1, 6, 1])
    with col_u2:
        uploaded_file = st.file_uploader(
            "Upload Project ZIP Archive",
            type=["zip"],
            help="Upload a .zip file containing your Python source files and pytest test files.",
            key="project_zip_uploader",
        )

        # Automatic Workspace Extraction upon Drop / Selection
        if uploaded_file is not None:
            file_bytes = uploaded_file.getvalue()
            file_size_str = format_file_size(len(file_bytes))
            file_sig = f"{uploaded_file.name}_{len(file_bytes)}"

            # If new file or signature changed, automatically initialize workspace
            if st.session_state.get("uploaded_file_sig") != file_sig:
                with st.spinner("Extracting workspace and initializing git baseline..."):
                    try:
                        file_tuple = (
                            uploaded_file.name,
                            file_bytes,
                            "application/zip",
                        )
                        files = {"file": file_tuple}
                        res = _safe_post(f"{api_url}/projects/upload", files=files, timeout=30)
                        if res is None:
                            st.session_state["upload_error"] = (
                                "Could not connect to backend to initialize workspace."
                            )
                            st.session_state.pop("project_id", None)
                        elif res.status_code == 201:
                            data = res.json()
                            st.session_state["project_id"] = data["project_id"]
                            st.session_state["project_name"] = data.get("name", uploaded_file.name)
                            f_count = data.get("file_count", 0)
                            st.session_state["file_count"] = f_count
                            st.session_state["uploaded_filename"] = uploaded_file.name
                            st.session_state["uploaded_file_sig"] = file_sig
                            st.session_state.pop("upload_error", None)
                            st.session_state.pop("repair_run_id", None)
                            st.session_state.pop("repair_status", None)
                            st.session_state.pop("repair_error", None)
                        elif res.status_code == 413:
                            st.session_state["upload_error"] = (
                                "Archive exceeds maximum upload size limit (50 MB)."
                            )
                            st.session_state.pop("project_id", None)
                        elif res.status_code == 415:
                            st.session_state["upload_error"] = (
                                "Only .zip archive format is accepted."
                            )
                            st.session_state.pop("project_id", None)
                        elif res.status_code == 422:
                            st.session_state["upload_error"] = _parse_api_error(res)
                            st.session_state.pop("project_id", None)
                        else:
                            st.session_state["upload_error"] = _parse_api_error(res)
                            st.session_state.pop("project_id", None)
                    except Exception as exc:
                        st.session_state["upload_error"] = str(exc)
                        st.session_state.pop("project_id", None)
                    st.rerun()

            # Check if upload error occurred
            if "upload_error" in st.session_state and st.session_state["upload_error"]:
                render_error_alert(
                    "Workspace Initialization Failed",
                    st.session_state["upload_error"],
                )

            # Workspace Ready & Inspected Metadata Card
            if "project_id" in st.session_state:
                pid = st.session_state["project_id"]
                pname = st.session_state.get("project_name", uploaded_file.name)
                fcnt = st.session_state.get("file_count", 0)

                st.markdown(
                    f"""
                    <div class="aegis-agent-card" style="margin-top: 20px;">
                      <div class="aegis-agent-header">
                        <span class="aegis-agent-title">📦 Project Workspace Ready</span>
                        <span class="aegis-badge passed">Workspace Initialized</span>
                      </div>
                      <div style="display: grid;
                      grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
                      gap: 12px; font-size: 0.88rem;">
                        <div>
                          <span style="color: #94a3b8;">Archive Name:</span><br>
                          <strong style="color: #f8fafc;">{uploaded_file.name}</strong>
                        </div>
                        <div>
                          <span style="color: #94a3b8;">Archive Size:</span><br>
                          <strong style="color: #f8fafc;">{file_size_str}</strong>
                        </div>
                        <div>
                          <span style="color: #94a3b8;">Source Files:</span><br>
                          <strong style="color: #38bdf8;">{fcnt} file(s) extracted</strong>
                        </div>
                        <div>
                          <span style="color: #94a3b8;">Test Framework:</span><br>
                          <strong style="color: #34d399;">Pytest (Auto-detected)</strong>
                        </div>
                      </div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

                # Repair Lifecycle State Handling
                repair_status = st.session_state.get("repair_status")
                repair_run_id = st.session_state.get("repair_run_id")

                # If no repair is currently running or failed, show Configuration & Launch
                if not repair_status:
                    st.markdown("---")
                    st.markdown("### Configure Repair Execution")

                    max_iters = st.slider(
                        "Maximum Repair Iterations",
                        min_value=1,
                        max_value=10,
                        value=5,
                        help="Max cycles of Architect → Coder → Test → Reviewer before halting.",
                        key="upload_max_iters_slider",
                    )
                    st.caption(f"Target Workspace: `{pid}` ({pname} • {fcnt} source files)")

                    if st.button(
                        "🛡️ Start Autonomous Repair",
                        type="primary",
                        use_container_width=True,
                        key="btn_start_repair",
                    ):
                        with st.spinner("Spawning autonomous LangGraph repair engine..."):
                            try:
                                payload = {
                                    "project_id": pid,
                                    "max_iterations": max_iters,
                                }
                                create_res = _safe_post(
                                    f"{api_url}/runs", json=payload, timeout=30
                                )
                                if create_res is None:
                                    st.session_state["repair_status"] = "error"
                                    st.session_state["repair_error"] = (
                                        "Could not reach backend to spawn repair run."
                                    )
                                elif create_res.status_code == 201:
                                    run_id = create_res.json()["run_id"]
                                    st.session_state["repair_run_id"] = run_id
                                    st.session_state["active_run_id"] = run_id
                                    st.session_state["repair_status"] = "running"
                                    st.session_state.pop("repair_error", None)

                                    # Trigger background repair graph
                                    repair_res = _safe_post(
                                        f"{api_url}/runs/{run_id}/repair", timeout=15
                                    )
                                    if (
                                        repair_res is None
                                        or repair_res.status_code not in (200, 202)
                                    ):
                                        st.session_state["repair_status"] = "error"
                                        st.session_state["repair_error"] = (
                                            _parse_api_error(repair_res)
                                            if repair_res
                                            else "Failed to launch repair graph in background."
                                        )
                                    else:
                                        # Navigate to Active Repairs
                                        st.session_state["nav_view"] = (
                                            "🤖 Active Repairs"
                                        )
                                        st.session_state["app_navigation_radio"] = (
                                            "🤖 Active Repairs"
                                        )
                                else:
                                    st.session_state["repair_status"] = "error"
                                    st.session_state["repair_error"] = _parse_api_error(create_res)
                            except Exception as exc:
                                st.session_state["repair_status"] = "error"
                                st.session_state["repair_error"] = str(exc)
                        st.rerun()

                # Execution State: Running (Live Execution & Progress Monitoring)
                elif repair_status == "running" and repair_run_id:
                    st.markdown("---")
                    st.markdown(
                        f"""
                        <div class="aegis-agent-card"
                        style="border: 1px solid rgba(56, 189, 248, 0.4);">
                          <div class="aegis-agent-header">
                            <span class="aegis-agent-title">⚙️ Autonomous Repair Execution</span>
                            <span class="aegis-badge running">● Executing Graph</span>
                          </div>
                          <p style="color: #94a3b8; font-size: 0.9rem; margin-bottom: 12px;">
                            The multi-agent repair loop is actively running
                            (Architect → Coder → Pytest → Reviewer).<br>
                            Run ID: <code>{repair_run_id}</code>
                          </p>
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )

                    status_data = fetch_run_status(api_url, repair_run_id)
                    if status_data:
                        cur_status = status_data.get("status", "running")
                        cur_iter = status_data.get("current_iteration", 1)
                        max_iter = status_data.get("max_iterations", 5)
                        final_summary = status_data.get("final_summary", "")

                        st.progress(
                            min(cur_iter / max(max_iter, 1), 1.0),
                            text=f"Iteration {cur_iter} of {max_iter} in progress...",
                        )

                        # Terminal Success: Automatically navigate to Active Repairs
                        if cur_status in ("passed", "already_passing"):
                            st.session_state["active_run_id"] = repair_run_id
                            st.session_state["nav_view"] = "🤖 Active Repairs"
                            st.session_state["app_navigation_radio"] = "🤖 Active Repairs"
                            st.session_state.pop("repair_run_id", None)
                            st.session_state.pop("repair_status", None)
                            st.session_state.pop("repair_error", None)
                            st.rerun()

                        # Terminal Failure / Stalled / Error: Keep on page and show failure details
                        elif cur_status in ("failed", "stalled", "error"):
                            st.session_state["repair_status"] = cur_status
                            st.session_state["repair_error"] = (
                                final_summary
                                or f"Repair concluded with status: {cur_status.upper()}."
                            )
                            st.rerun()

                        # Terminal Cancelled / Stopped
                        elif cur_status in ("cancelled", "stopped"):
                            st.session_state["repair_status"] = "cancelled"
                            st.session_state["repair_error"] = (
                                final_summary or "Repair was cancelled or stopped."
                            )
                            st.rerun()

                        # Still running: Poll backend
                        else:
                            st.caption("Auto-refreshing execution telemetry...")
                            col_c1, col_c2 = st.columns([4, 1])
                            with col_c2:
                                if st.button(
                                    "🛑 Cancel Tracking",
                                    key="btn_stop_waiting",
                                    use_container_width=True,
                                ):
                                    st.session_state["repair_status"] = "cancelled"
                                    st.session_state["repair_error"] = (
                                        "Repair tracking was stopped by user."
                                    )
                                    st.rerun()
                            time.sleep(1.5)
                            st.rerun()
                    else:
                        st.caption("Connecting to repair runtime...")
                        time.sleep(1.5)
                        st.rerun()

                # Terminal Failure / Error State Display
                elif repair_status in ("failed", "stalled", "error"):
                    st.markdown("---")
                    err_msg = st.session_state.get(
                        "repair_error", "Autonomous repair was unsuccessful."
                    )
                    render_error_alert(
                        f"Autonomous Repair {repair_status.upper()}",
                        f"Run ID <code>{repair_run_id}</code> failed to produce a passing patch: "
                        f"{err_msg}",
                    )

                    col_f1, col_f2 = st.columns(2)
                    with col_f1:
                        if st.button(
                            "🔄 Try Again",
                            key="btn_try_again",
                            type="primary",
                            use_container_width=True,
                        ):
                            st.session_state.pop("repair_status", None)
                            st.session_state.pop("repair_run_id", None)
                            st.session_state.pop("repair_error", None)
                            st.rerun()
                    with col_f2:
                        if st.button(
                            "📊 View Repair History",
                            key="btn_view_hist",
                            use_container_width=True,
                        ):
                            st.session_state["nav_view"] = "📊 Repair History"
                            st.session_state["app_navigation_radio"] = "📊 Repair History"
                            st.rerun()

                # Terminal Cancelled State Display
                elif repair_status == "cancelled":
                    st.markdown("---")
                    render_warning_alert(
                        "Autonomous Repair Cancelled",
                        st.session_state.get("repair_error", "The repair run was cancelled."),
                    )
                    if st.button(
                        "🔄 Start New Repair Run",
                        key="btn_restart_after_cancel",
                        type="primary",
                        use_container_width=True,
                    ):
                        st.session_state.pop("repair_status", None)
                        st.session_state.pop("repair_run_id", None)
                        st.session_state.pop("repair_error", None)
                        st.rerun()
        else:
            # File removed / cleared: reset session state
            st.session_state.pop("uploaded_file_sig", None)
            st.session_state.pop("project_id", None)
            st.session_state.pop("upload_error", None)
            st.session_state.pop("repair_status", None)
            st.session_state.pop("repair_run_id", None)
            st.session_state.pop("repair_error", None)

