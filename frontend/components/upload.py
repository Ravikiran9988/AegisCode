"""
New Repair & Project Upload Component for AegisCode.
Handles project ZIP upload, workspace initialization, and graph execution launch.
"""

from __future__ import annotations

import time

import streamlit as st

from frontend.components.states import render_error_alert
from frontend.utils.api_client import _safe_post
from frontend.utils.helpers import _parse_api_error, format_file_size


def render_upload(api_url: str) -> None:
    """Render the project upload and repair initialization experience."""
    st.markdown(
        """
        <div class="aegis-page-header">
          <h1 class="aegis-page-title">Start a New Autonomous Repair</h1>
          <p class="aegis-page-desc">
            Upload a Python repository and let AegisCode diagnose failures,
            synthesize verified patches, and audit regressions.
          </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # Drag and Drop Upload Card
    uploaded_file = st.file_uploader(
        "Upload Python Project ZIP",
        type=["zip"],
        help="Upload a .zip file containing your Python source files and pytest test files.",
        key="project_zip_uploader",
    )

    if uploaded_file is not None:
        file_bytes = uploaded_file.getvalue()
        file_size_str = format_file_size(len(file_bytes))

        st.markdown(
            f"""
            <div class="aegis-agent-card" style="margin-top: 16px;">
              <div class="aegis-agent-header">
                <span class="aegis-agent-title">📦 Project Archive Details</span>
                <span class="aegis-badge running">Ready for Inspection</span>
              </div>
              <div style="display: grid;
              grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
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
                  <span style="color: #94a3b8;">Target Runtime:</span><br>
                  <strong style="color: #38bdf8;">Python 3.10+</strong>
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

        col_act1, col_act2 = st.columns([1, 1])

        # Step 1: Initialize Workspace
        with col_act1:
            uploaded_name = uploaded_file.name
            has_project = "project_id" in st.session_state
            is_same_file = st.session_state.get("uploaded_filename") == uploaded_name
            if not has_project or not is_same_file:
                if st.button(
                    "🚀 Initialize Project Workspace",
                    type="primary",
                    use_container_width=True,
                    key="btn_init_ws",
                ):
                    with st.spinner("Extracting workspace and initializing git snapshot..."):
                        try:
                            file_tuple = (
                                uploaded_file.name,
                                file_bytes,
                                "application/zip",
                            )
                            files = {"file": file_tuple}
                            res = _safe_post(f"{api_url}/projects/upload", files=files, timeout=30)
                            if res is None:
                                render_error_alert(
                                    "Connection Error",
                                    "Could not connect to backend to upload file.",
                                )
                            elif res.status_code == 201:
                                data = res.json()
                                st.session_state["project_id"] = data["project_id"]
                                st.session_state["project_name"] = data.get("name", uploaded_name)
                                f_count = data.get("file_count", 0)
                                st.session_state["file_count"] = f_count
                                st.session_state["uploaded_filename"] = uploaded_name
                                st.session_state.pop("active_run_id", None)
                                st.success(
                                    f"✅ Workspace Initialized! Extracted {f_count} source file(s)."
                                )
                                st.rerun()
                            elif res.status_code == 413:
                                render_error_alert(
                                    "File Too Large",
                                    "Archive exceeds maximum upload size limit (50 MB).",
                                )
                            elif res.status_code == 415:
                                render_error_alert(
                                    "Unsupported Format",
                                    "Only .zip archive format is accepted.",
                                )
                            elif res.status_code == 422:
                                render_error_alert(
                                    "ZIP Validation Failed",
                                    _parse_api_error(res),
                                )
                            else:
                                render_error_alert("Upload Failed", _parse_api_error(res))
                        except Exception as exc:
                            render_error_alert("Upload Exception", str(exc))

    # Step 2: Configure and Launch Graph
    if "project_id" in st.session_state:
        pid = st.session_state["project_id"]
        pname = st.session_state.get("project_name", "project")
        fcnt = st.session_state.get("file_count", 0)

        st.markdown("---")
        st.markdown("### 2. Configure Autonomous Repair Parameters")

        col_cfg1, col_cfg2 = st.columns([1, 1])
        with col_cfg1:
            max_iters = st.slider(
                "Maximum Repair Iterations",
                min_value=1,
                max_value=10,
                value=5,
                help="Max cycles of Architect → Coder → Test → Reviewer before halting.",
                key="upload_max_iters_slider",
            )
            st.caption(f"Active Workspace: `{pid}` ({pname} • {fcnt} files)")

        with col_cfg2:
            st.markdown(
                """
                <div class="aegis-health-card">
                  <strong style="color: #e2e8f0; font-size: 0.88rem;">
                    🛡️ Engine Safety & Isolation Guarantees:
                  </strong>
                  <ul style="margin: 6px 0 0 0; padding-left: 18px; color: #94a3b8;
                  font-size: 0.82rem; line-height: 1.5;">
                    <li>Isolated sandbox prevents modification outside project root.</li>
                    <li>Test files are strictly read-only — agents cannot tamper with tests.</li>
                    <li>Double-gated resolution: 100% Pytest pass + Reviewer LLM audit.</li>
                  </ul>
                </div>
                """,
                unsafe_allow_html=True,
            )

        if st.button(
            "🛡️ Start Autonomous Self-Healing Graph",
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
                    create_res = _safe_post(f"{api_url}/runs", json=payload, timeout=30)
                    if create_res is None:
                        render_error_alert(
                            "Connection Error",
                            "Could not reach backend to spawn repair run.",
                        )
                    elif create_res.status_code == 201:
                        run_id = create_res.json()["run_id"]
                        st.session_state["active_run_id"] = run_id

                        # Trigger background repair graph
                        _safe_post(f"{api_url}/runs/{run_id}/repair", timeout=10)

                        st.success(f"🚀 Repair Graph Launched! Run ID: `{run_id}`")
                        time.sleep(0.5)
                        st.session_state["nav_view"] = "🤖 Live Repair Console"
                        st.rerun()
                    else:
                        render_error_alert("Run Creation Failed", _parse_api_error(create_res))
                except Exception as exc:
                    render_error_alert("Execution Error", str(exc))
