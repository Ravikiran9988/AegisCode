"""
Streamlit Frontend Dashboard for AegisCode — Phase 6.

Improvements over Phase 4:
- Status card: SUCCESS / FAILED / STALLED / RUNNING with coloured icons.
- Visual repair timeline (no fabricated events).
- Repair summary table (only fields available from backend).
- Improved code-changes diff view with per-file expanders.
- Prominent download button (only when status == passed/already_passing).
- All 10 UX states handled cleanly.
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

# ── Custom CSS ─────────────────────────────────────────────────────────────────
st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

    html, body, [class*="css"] { font-family: 'Inter', sans-serif; }

    .main-title {
        font-size: 2.4rem; font-weight: 700;
        background: linear-gradient(135deg, #4F46E5, #7C3AED);
        -webkit-background-clip: text; -webkit-text-fill-color: transparent;
        margin-bottom: 0.2rem;
    }
    .subtitle { font-size: 1.0rem; color: #9CA3AF; margin-bottom: 1.5rem; }

    /* Status cards */
    .status-card {
        border-radius: 12px; padding: 20px 24px;
        margin: 12px 0; border-left: 5px solid;
    }
    .status-card.passed {
        background: linear-gradient(135deg, #064e3b22, #065f4622);
        border-color: #10b981;
    }
    .status-card.failed {
        background: linear-gradient(135deg, #7f1d1d22, #991b1b22);
        border-color: #ef4444;
    }
    .status-card.stalled {
        background: linear-gradient(135deg, #78350f22, #92400e22);
        border-color: #f59e0b;
    }
    .status-card.running {
        background: linear-gradient(135deg, #1e3a8a22, #1d4ed822);
        border-color: #3b82f6;
    }
    .status-card h2 { margin: 0 0 8px 0; font-size: 1.4rem; font-weight: 700; }
    .status-card p  { margin: 4px 0; color: #d1d5db; font-size: 0.95rem; }

    /* Download section */
    .download-section {
        background: linear-gradient(135deg, #0f172a, #1e293b);
        border: 1px solid #10b981;
        border-radius: 14px;
        padding: 24px 28px;
        margin: 16px 0;
        text-align: center;
    }
    .download-section h3 { color: #10b981; margin: 0 0 8px 0; font-size: 1.2rem; }
    .download-section p  { color: #94a3b8; margin: 0 0 16px 0; font-size: 0.9rem; }

    /* Timeline */
    .timeline-step {
        display: flex; align-items: flex-start;
        padding: 10px 0; gap: 14px;
    }
    .timeline-icon { font-size: 1.4rem; min-width: 30px; text-align: center; }
    .timeline-label { font-weight: 600; font-size: 0.95rem; }
    .timeline-detail { color: #94a3b8; font-size: 0.85rem; margin-top: 2px; }
    .timeline-connector {
        width: 2px; height: 20px; background: #374151;
        margin-left: 14px; margin-top: 0;
    }

    /* Summary table */
    .summary-grid {
        display: grid; grid-template-columns: 1fr 1fr;
        gap: 10px; margin: 12px 0;
    }
    .summary-item {
        background: #1e293b; border-radius: 8px;
        padding: 10px 14px;
    }
    .summary-item .label { color: #94a3b8; font-size: 0.8rem; text-transform: uppercase;
                           letter-spacing: 0.05em; }
    .summary-item .value { color: #f1f5f9; font-size: 1.0rem; font-weight: 600; }

    /* Diff badge */
    .diff-badge {
        display: inline-block; padding: 2px 8px; border-radius: 4px;
        font-size: 0.75rem; font-weight: 600; margin-right: 6px;
    }
    .diff-badge.modified { background: #1d4ed8; color: #bfdbfe; }
    .diff-badge.added    { background: #065f46; color: #a7f3d0; }
    .diff-badge.deleted  { background: #991b1b; color: #fecaca; }

    /* Alerts */
    .alert-offline {
        background: #1c1917; border: 1px solid #78350f;
        border-radius: 8px; padding: 14px 18px; color: #fcd34d;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


# ── Helpers ────────────────────────────────────────────────────────────────────

def _safe_get(url: str, timeout: int = 5) -> requests.Response | None:
    """GET request; returns None on any connection/timeout error."""
    try:
        return requests.get(url, timeout=timeout)
    except Exception:
        return None


def _normalize_backend_url(url: str) -> str:
    """
    Normalize backend URL by stripping whitespace, trailing slashes,
    and path suffixes like /health or /api.
    """
    u = url.strip().rstrip("/")
    if u.endswith("/health"):
        u = u[:-7].rstrip("/")
    elif u.endswith("/api"):
        u = u[:-4].rstrip("/")
    return u


def _backend_online(backend_url: str) -> tuple[bool, dict]:
    """
    Check backend connectivity via GET /health endpoint.

    Returns (is_online, health_data) when /health returns HTTP 200 and status is "ok" or "healthy".
    """
    base_url = _normalize_backend_url(backend_url)
    health_url = f"{base_url}/health"
    resp = _safe_get(health_url, timeout=5)
    if resp is not None and resp.status_code == 200:
        try:
            data = resp.json()
            if isinstance(data, dict) and data.get("status") in ("ok", "healthy"):
                return True, data
        except Exception:
            pass
    return False, {}


def _duration_str(started_at: str | None, finished_at: str | None) -> str:
    """Compute human-readable duration from ISO timestamps."""
    if not started_at or not finished_at:
        return "—"
    try:
        from datetime import datetime
        def _parse(s: str):
            for f in ("%Y-%m-%dT%H:%M:%S.%f%z", "%Y-%m-%dT%H:%M:%S%z",
                      "%Y-%m-%dT%H:%M:%S.%f", "%Y-%m-%dT%H:%M:%S"):
                try:
                    return datetime.strptime(s, f)
                except ValueError:
                    continue
            return None
        t0 = _parse(started_at)
        t1 = _parse(finished_at)
        if t0 and t1:
            diff = abs((t1 - t0).total_seconds())
            return f"{diff:.1f}s"
    except Exception:
        pass
    return "—"


# ── Sidebar ────────────────────────────────────────────────────────────────────
st.sidebar.title("🛡️ AegisCode Settings")
raw_backend_url = st.sidebar.text_input("Backend URL (root or /health)", value=API_BASE_URL)
base_backend_url = _normalize_backend_url(raw_backend_url)
api_url = f"{base_backend_url}/api"

online, health_data = _backend_online(base_backend_url)
if online:
    llm_prov = health_data.get("llm_provider", "unknown")
    st.sidebar.success(f"✅ Backend Online — LLM: `{llm_prov}`")
else:
    st.sidebar.error("❌ Backend Unreachable")

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

# ── Header ─────────────────────────────────────────────────────────────────────
st.markdown('<div class="main-title">🛡️ AegisCode</div>', unsafe_allow_html=True)
st.markdown(
    '<div class="subtitle">Autonomous Self-Healing Multi-Agent Software Engineering System</div>',
    unsafe_allow_html=True,
)

# Backend offline — show prominent warning and disable action tabs
if not online:
    st.markdown(
        """
        <div class="alert-offline">
        ⚠️ <strong>Backend Unavailable</strong> — The AegisCode backend service is not reachable
        at the URL above. Please check the backend service and try again.
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.stop()

tabs = st.tabs(["🚀 Launch Repair Run", "📊 Repair Results & Timeline", "ℹ️ System Overview"])


# ── Tab 1: Launch Repair Run ───────────────────────────────────────────────────
with tabs[0]:
    st.subheader("1. Upload Python Project (.zip)")
    uploaded_file = st.file_uploader(
        "Choose a project ZIP containing failing pytest tests", type=["zip"],
        help="Upload a .zip archive of your Python project with pytest tests.",
    )

    col1, col2 = st.columns([1, 2])

    if uploaded_file is not None:
        with col1:
            if st.button("📤 Upload & Initialize Project", type="primary",
                         key="btn_upload"):
                with st.spinner("Validating and extracting project workspace..."):
                    try:
                        file_tuple = (
                            uploaded_file.name, uploaded_file.getvalue(), "application/zip"
                        )
                        files = {"file": file_tuple}
                        res = requests.post(f"{api_url}/projects/upload", files=files,
                                            timeout=30)
                        if res.status_code == 201:
                            data = res.json()
                            st.session_state["project_id"] = data["project_id"]
                            st.session_state.pop("active_run_id", None)
                            st.success(
                                f"✅ Project Uploaded!  \n"
                                f"**ID:** `{data['project_id']}`  \n"
                                f"**Files:** {data['file_count']} Python source files"
                            )
                        else:
                            st.error(f"Upload failed: {res.text}")
                    except Exception as exc:
                        st.error(f"Connection error during upload: {exc}")
    else:
        st.info("📁 No project selected. Please upload a .zip file above to continue.")

    if "project_id" in st.session_state:
        st.markdown("---")
        st.subheader("2. Configure & Start Self-Healing Repair")

        col_cfg1, col_cfg2 = st.columns([1, 2])
        with col_cfg1:
            max_iters = st.slider(
                "Maximum Repair Iterations", min_value=1, max_value=10, value=5,
                help="How many Architect→Coder→Test→Reviewer cycles to allow.",
            )

        pid_display = st.session_state["project_id"]
        st.caption(f"Project ID: `{pid_display}`")

        if st.button("⚡ Start Autonomous Repair Graph", type="primary",
                     key="btn_start_repair"):
            with st.spinner("Initializing repair run..."):
                try:
                    payload = {
                        "project_id": st.session_state["project_id"],
                        "max_iterations": max_iters,
                    }
                    create_res = requests.post(f"{api_url}/runs", json=payload, timeout=30)
                    if create_res.status_code == 201:
                        run_id = create_res.json()["run_id"]
                        st.session_state["active_run_id"] = run_id

                        # Trigger repair loop
                        repair_res = requests.post(
                            f"{api_url}/runs/{run_id}/repair", timeout=10
                        )
                        if repair_res.status_code in (200, 202):
                            st.success(
                                f"🚀 Autonomous Repair Graph launched!  \n"
                                f"**Run ID:** `{run_id}`  \n"
                                "Switch to **📊 Repair Results & Timeline** to monitor progress."
                            )
                        else:
                            st.error(f"Failed to launch repair graph: {repair_res.text}")
                    else:
                        st.error(f"Failed to create run: {create_res.text}")
                except Exception as exc:
                    st.error(f"Error launching repair: {exc}")


# ── Tab 2: Repair Results & Timeline ──────────────────────────────────────────
with tabs[1]:
    # Resolve the run ID to inspect
    active_run_id = st.session_state.get("active_run_id", "")
    if not active_run_id:
        manual_id = st.text_input(
            "Enter Run ID to inspect", value="",
            placeholder="e.g. 3fa85f64-5717-4562-b3fc-2c963f66afa6",
            key="manual_run_id",
        )
        active_run_id = manual_id.strip()

    if not active_run_id:
        st.info(
            "🔍 No active run. Start a repair in **🚀 Launch Repair Run** "
            "or enter a run ID above."
        )
        st.stop()

    # ── Fetch data ────────────────────────────────────────────────────────────
    status_resp = _safe_get(f"{api_url}/runs/{active_run_id}/status")
    results_resp = _safe_get(f"{api_url}/runs/{active_run_id}/results")

    if status_resp is None or results_resp is None:
        st.error("❌ Backend unavailable. Please check the backend service.")
        st.stop()

    if status_resp.status_code == 404:
        st.warning(f"Run `{active_run_id}` not found. Please verify the run ID.")
        st.stop()

    if status_resp.status_code != 200 or results_resp.status_code != 200:
        st.error(
            f"Failed to fetch run details (status HTTP {status_resp.status_code}). "
            "Please try again."
        )
        st.stop()

    sdata = status_resp.json()
    rdata = results_resp.json()

    run_status = sdata.get("status", "unknown")
    iterations = rdata.get("iterations", [])

    # ── 3. Status Card ────────────────────────────────────────────────────────
    _STATUS_ICONS = {
        "passed": ("🟢", "Repair Successful", "passed"),
        "already_passing": ("🟢", "Already Passing", "passed"),
        "failed": ("🔴", "Repair Failed", "failed"),
        "error": ("🔴", "Repair Error", "failed"),
        "stalled": ("🟠", "Repair Stalled", "stalled"),
        "running": ("🔵", "Repair In Progress", "running"),
        "pending": ("⚪", "Pending", "running"),
    }
    icon, label, css_cls = _STATUS_ICONS.get(run_status, ("⚪", run_status.upper(), "running"))

    duration_str = _duration_str(sdata.get("started_at"), sdata.get("finished_at"))
    current_iter = sdata.get("current_iteration", 0)
    max_iter = sdata.get("max_iterations", 5)
    tests_ok = sdata.get("tests_passed", False)
    rev_ok = sdata.get("review_approved", False)
    final_summary = sdata.get("final_summary", "")

    is_rate_limit_err = any(
        k in final_summary.lower()
        for k in ("rate_limit", "rate limit", "429", "ratelimiterror")
    )

    if is_rate_limit_err and run_status in ("failed", "error"):
        icon, label, css_cls = ("⏳", "Groq Rate Limit Reached", "stalled")

    extra_lines = ""
    if run_status in ("passed", "already_passing"):
        extra_lines = (
            "<p>✅ Tests Passed &nbsp;|&nbsp; "
            f"✅ Reviewer Approved &nbsp;|&nbsp; "
            f"Iterations: {current_iter}/{max_iter} &nbsp;|&nbsp; "
            f"Duration: {duration_str}</p>"
        )
    elif run_status == "running":
        extra_lines = (
            f"<p>🔄 Current Node Iteration: {current_iter}/{max_iter} — auto-refreshing…</p>"
            "<p><small>ℹ️ Note: If Groq 429 rate limits are hit, AegisCode automatically "
            "pauses and retries in the background.</small></p>"
        )
    elif is_rate_limit_err:
        extra_lines = (
            "<p>⚠️ <strong>Groq Free-Tier Rate Limit Reached (8,000 TPM)</strong></p>"
            "<p>All 4 automatic retries were exhausted while waiting for quota reset.</p>"
            "<p>💡 <em>Please wait 1–2 minutes for your TPM token bucket to refill, "
            "then switch to <strong>🚀 Launch Repair Run</strong> to try again.</em></p>"
            f"<p>Iterations completed: {current_iter}/{max_iter}</p>"
        )
    elif run_status in ("failed", "error"):
        extra_lines = (
            f"<p>❌ Termination: {final_summary or 'See logs below'}</p>"
            f"<p>Iterations completed: {current_iter}/{max_iter}</p>"
        )
    elif run_status == "stalled":
        extra_lines = (
            "<p>⚠️ The repair loop detected repeated identical failures and stopped.</p>"
            f"<p>{final_summary or ''}</p>"
            f"<p>Iterations completed: {current_iter}/{max_iter}</p>"
        )

    st.markdown(
        f"""
        <div class="status-card {css_cls}">
          <h2>{icon} {label}</h2>
          {extra_lines}
        </div>
        """,
        unsafe_allow_html=True,
    )

    # Auto-refresh while running
    if run_status == "running":
        st.info("🔄 Repair Graph running in background — auto-refreshing in 3 seconds…")
        time.sleep(3)
        st.rerun()

    st.markdown("---")

    # ── 4. Visual Repair Timeline ─────────────────────────────────────────────
    st.subheader("📅 Repair Timeline")

    def _timeline_step(icon_str: str, label_str: str, detail_str: str = "") -> None:
        st.markdown(
            f"""
            <div class="timeline-step">
              <div class="timeline-icon">{icon_str}</div>
              <div>
                <div class="timeline-label">{label_str}</div>
                {"<div class='timeline-detail'>" + detail_str + "</div>" if detail_str else ""}
              </div>
            </div>
            <div class="timeline-connector"></div>
            """,
            unsafe_allow_html=True,
        )

    # Step 1: Upload (always happened since we have a run)
    _timeline_step("📦", "Project Uploaded", "ZIP extracted and workspace created.")

    # Step 2–6: Iteration-based steps — only show what actually happened
    if not iterations:
        _timeline_step("⏳", "No iterations recorded yet.", "")
    else:
        for it in iterations:
            it_num = it.get("iteration_number", "?")

            # Architect
            has_arch = bool(it.get("architecture_plan"))
            _timeline_step(
                "✅" if has_arch else "⏳",
                f"Iteration {it_num} — Architect Analysis",
                it.get("architecture_plan", {}).get("summary", "") if has_arch else "Waiting…",
            )

            # Coder
            has_code = bool(it.get("code_changes") or it.get("test_results"))
            _timeline_step(
                "✅" if has_code else "⏳",
                f"Iteration {it_num} — Code Repair",
                "",
            )

            # Tests
            tres = it.get("test_results") or {}
            if tres:
                passed_c = tres.get("passed", 0)
                failed_c = tres.get("failed", 0)
                test_ok = tres.get("success", False)
                _timeline_step(
                    "✅" if test_ok else "❌",
                    f"Iteration {it_num} — Tests Executed",
                    f"{passed_c} passed, {failed_c} failed",
                )
            else:
                _timeline_step("⏳", f"Iteration {it_num} — Tests Executed", "Awaiting results…")

            # Reviewer
            rev = it.get("review_result") or {}
            if rev:
                rev_approved = rev.get("approved", False)
                _timeline_step(
                    "✅" if rev_approved else "❌",
                    f"Iteration {it_num} — Reviewer Audit",
                    f"Approved: {rev_approved} | Risk: {rev.get('regression_risk', '?')}",
                )
            else:
                _timeline_step("⏳", f"Iteration {it_num} — Reviewer Audit", "Awaiting review…")

    # Final approval step
    if run_status in ("passed", "already_passing"):
        _timeline_step(
            "✅", "Final Approval — Repair Complete",
            "All tests passed. Reviewer approved.",
        )
    elif run_status in ("failed", "error", "stalled"):
        _timeline_step("❌", "Repair Ended Without Full Recovery", final_summary or "")

    st.markdown("---")

    # ── 5. Repair Summary ─────────────────────────────────────────────────────
    st.subheader("📋 Repair Summary")

    # Compute summary data from available fields
    summary_fields: list[tuple[str, str]] = []

    summary_fields.append(("Status", f"{icon} {run_status.upper()}"))

    if current_iter:
        summary_fields.append(("Iterations", f"{current_iter} / {max_iter}"))

    if iterations:
        last = iterations[-1]
        tp = last.get("tests_passed")
        tf = last.get("tests_failed")
        if tp is not None:
            summary_fields.append(("Tests Passed", str(tp)))
        if tf is not None:
            summary_fields.append(("Tests Failed", str(tf)))

        rev_last = last.get("review_result") or {}
        if rev_last:
            summary_fields.append((
                "Reviewer Decision",
                "✅ APPROVED" if rev_last.get("approved") else "❌ NOT APPROVED",
            ))

    if final_summary:
        summary_fields.append(("Termination Reason", final_summary))

    if duration_str != "—":
        summary_fields.append(("Duration", duration_str))

    # Render as a 2-column grid
    cols = st.columns(2)
    for idx, (lbl, val) in enumerate(summary_fields):
        with cols[idx % 2]:
            st.markdown(
                f"""
                <div class="summary-item">
                  <div class="label">{lbl}</div>
                  <div class="value">{val}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )

    st.markdown("---")

    # ── 7. Download Section ───────────────────────────────────────────────────
    if run_status in ("passed", "already_passing"):
        st.markdown(
            """
            <div class="download-section">
              <h3>✅ REPAIR SUCCESSFUL</h3>
              <p>
                Your project has been repaired successfully.<br>
                All authoritative tests passed and the Reviewer approved the changes.
              </p>
            </div>
            """,
            unsafe_allow_html=True,
        )

        # Fetch the ZIP from the backend
        try:
            dl_resp = requests.get(
                f"{api_url}/runs/{active_run_id}/download",
                timeout=60,
                stream=True,
            )
            if dl_resp.status_code == 200:
                zip_bytes = dl_resp.content
                st.download_button(
                    label="⬇️ Download Repaired Project",
                    data=zip_bytes,
                    file_name=f"aegiscode-repaired-{active_run_id}.zip",
                    mime="application/zip",
                    type="primary",
                    key="btn_download_zip",
                    help="Downloads the repaired project source files as a ZIP archive.",
                )
            elif dl_resp.status_code == 409:
                st.warning("⚠️ Repaired project is not currently available for download.")
            elif dl_resp.status_code == 404:
                st.warning("⚠️ Repaired project workspace not found. It may have been cleaned up.")
            else:
                st.error(
                    f"Download failed (HTTP {dl_resp.status_code}). "
                    "Please try again or contact support."
                )
        except Exception as exc:
            st.error(f"Download unavailable — could not reach backend: {exc}")

    elif run_status == "running":
        st.info("⏳ Download will be available once the repair completes successfully.")
    else:
        st.warning(
            "⬇️ Download is only available for successfully completed repairs. "
            f"Current status: **{run_status.upper()}**"
        )

    st.markdown("---")

    # ── Iteration Detail Tabs ─────────────────────────────────────────────────
    if iterations:
        st.subheader("🔬 Iteration-by-Iteration Details")
        it_tabs = st.tabs([f"Iteration {it['iteration_number']}" for it in iterations])
        for idx, it in enumerate(iterations):
            with it_tabs[idx]:
                col_arch, col_code = st.columns(2)

                with col_arch:
                    st.markdown("##### 🏛️ Architect Agent Plan")
                    plan = it.get("architecture_plan") or {}
                    if plan:
                        st.write(f"**Summary:** {plan.get('summary', 'N/A')}")
                        rel_files = ", ".join(plan.get("relevant_files", []))
                        if rel_files:
                            st.write(f"**Relevant Files:** `{rel_files}`")
                        issues = plan.get("suspected_issues", [])
                        if issues:
                            st.write(f"**Suspected Issues:** {issues}")
                        if plan.get("test_strategy"):
                            st.write(f"**Test Strategy:** {plan.get('test_strategy')}")
                    else:
                        st.caption("No architect plan recorded for this iteration.")

                with col_code:
                    st.markdown("##### 💻 Coder Agent Modification")
                    # code_changes is a list; support both old dict and new list
                    changes = it.get("code_changes") or []
                    if isinstance(changes, dict):
                        changes = [changes]
                    if changes:
                        for ch in changes:
                            fpath = ch.get("file_path", "N/A")
                            ctype = ch.get("change_type", "N/A")
                            expl = ch.get("explanation", "N/A")
                            st.write(f"**File:** `{fpath}` — **Type:** `{ctype}`")
                            st.write(f"**Explanation:** {expl}")
                    else:
                        st.caption("No code changes recorded for this iteration.")

                st.markdown("---")
                col_test, col_rev = st.columns(2)

                with col_test:
                    st.markdown("##### 🧪 Pytest Execution Results")
                    tres = it.get("test_results") or {}
                    if tres:
                        st.write(
                            f"**Exit Code:** `{tres.get('exit_code')}` | "
                            f"**Passed:** {tres.get('passed')} | "
                            f"**Failed:** {tres.get('failed')} | "
                            f"**Duration:** {tres.get('duration', 0):.2f}s"
                        )
                        with st.expander("Show Captured Stdout"):
                            st.code(tres.get("stdout", ""), language="text")
                        if tres.get("stderr"):
                            with st.expander("Show Captured Stderr"):
                                st.code(tres.get("stderr", ""), language="text")
                    else:
                        st.caption("No test results recorded.")

                with col_rev:
                    st.markdown("##### 🔍 Reviewer Agent Audit")
                    rev = it.get("review_result") or {}
                    if rev:
                        st.write(f"**Approved:** `{rev.get('approved')}`")
                        if rev.get("root_cause_fixed") is not None:
                            st.write(f"**Root Cause Fixed:** `{rev.get('root_cause_fixed')}`")
                        if rev.get("regression_risk"):
                            st.write(f"**Regression Risk:** `{rev.get('regression_risk')}`")
                        if rev.get("reasoning"):
                            st.write(f"**Reasoning:** {rev.get('reasoning')}")
                    else:
                        st.caption("No reviewer result recorded.")

    st.markdown("---")

    # ── 6. Code Changes / Git Diff ────────────────────────────────────────────
    st.subheader("🔀 Code Changes")

    diff_resp = _safe_get(f"{api_url}/runs/{active_run_id}/results")
    if diff_resp and diff_resp.status_code == 200:
        diff_data = diff_resp.json()
        all_changes: list[dict] = []
        for it in diff_data.get("iterations", []):
            changes = it.get("code_changes") or []
            if isinstance(changes, dict):
                changes = [changes]
            all_changes.extend(changes)

        if not all_changes:
            st.caption("No code changes were recorded for this run.")
        else:
            # Deduplicate by file path (keep last change per file)
            seen: dict[str, dict] = {}
            for ch in all_changes:
                fp = ch.get("file_path", "")
                if fp:
                    seen[fp] = ch

            # Categorise
            modified = {fp: ch for fp, ch in seen.items() if ch.get("change_type") not in ("add",)}
            added    = {fp: ch for fp, ch in seen.items() if ch.get("change_type") == "add"}
            deleted  = {fp: ch for fp, ch in seen.items() if ch.get("change_type") == "delete"}

            if modified:
                st.markdown(
                    f"<span class='diff-badge modified'>MODIFIED</span> "
                    f"{len(modified)} file(s)",
                    unsafe_allow_html=True,
                )
                for fp, ch in modified.items():
                    # Show only the filename, not internal workspace paths
                    display_name = fp.split("/")[-1] if "/" in fp else fp
                    with st.expander(f"📝 {display_name}"):
                        st.write(f"**Explanation:** {ch.get('explanation', 'N/A')}")
                        if ch.get("patch"):
                            st.code(ch["patch"], language="python")

            if added:
                st.markdown(
                    f"<span class='diff-badge added'>ADDED</span> "
                    f"{len(added)} file(s)",
                    unsafe_allow_html=True,
                )
                for fp, ch in added.items():
                    display_name = fp.split("/")[-1] if "/" in fp else fp
                    with st.expander(f"➕ {display_name}"):
                        st.write(f"**Explanation:** {ch.get('explanation', 'N/A')}")
                        if ch.get("patch"):
                            st.code(ch["patch"], language="python")

            if deleted:
                st.markdown(
                    f"<span class='diff-badge deleted'>DELETED</span> "
                    f"{len(deleted)} file(s)",
                    unsafe_allow_html=True,
                )
                for fp in deleted:
                    display_name = fp.split("/")[-1] if "/" in fp else fp
                    st.markdown(f"🗑️ `{display_name}`")
    else:
        st.caption("Could not load code change details.")


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

    st.markdown("### Production Configuration")
    st.markdown(
        """
        | Setting | Value |
        |---|---|
        | LLM Provider | `openai_compatible` |
        | API Endpoint | Groq (OpenAI-compatible) |
        | Model | `openai/gpt-oss-120b` |
        | Execution Backend | `local` |
        """
    )

    st.markdown("### Security Features")
    st.markdown(
        """
        - **Upload Validation**: ZIP Slip (path traversal) prevention, bomb detection, size limits.
        - **Workspace Isolation**: Each run gets a unique UUID-named workspace; all paths are
          resolved and verified before access.
        - **Download Safety**: Repaired ZIPs exclude `.env`, `*.db`, `__pycache__`, `.git`,
          secrets and credentials files.
        - **Status Guards**: Download only available for `passed` / `already_passing` runs.
        - **No Secret Leakage**: API keys are never returned in health checks or logs.
        """
    )
