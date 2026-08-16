"""
Streamlit Frontend Dashboard for AegisCode — Phase 6.

Improvements over Phase 4:
- Status card: SUCCESS / FAILED / STALLED / RUNNING with coloured icons.
- Visual repair timeline with fixed stage states (Waiting / Running / Completed / Failed).
- Repair summary table (only fields available from backend).
- Improved code-changes diff view with per-file expanders.
- Prominent download button (only when status == passed/already_passing).
- All 10 UX states handled cleanly.
- Backend connectivity with retry/backoff for Render cold starts.
- Robust error handling for all API calls.
- LLM rate-limit (429) detection and user-friendly messaging.
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

# ── Configuration ───────────────────────────────────────────────────────────────

DEFAULT_BACKEND = os.environ.get(
    "BACKEND_URL", "https://aegiscode-vrob.onrender.com"
)
# Retry schedule for cold-start tolerance (seconds between attempts)
_COLD_START_RETRY_DELAYS = [0, 2, 4, 8, 15, 30]
_HEALTH_TIMEOUT = 10  # seconds per health check call
_API_TIMEOUT = 30  # seconds per API call


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
    .alert-error {
        background: rgba(239, 68, 68, 0.12); border-left: 4px solid #ef4444;
        border-radius: 8px; padding: 14px 18px; margin: 12px 0; color: #fca5a5;
    }
    .alert-warning {
        background: rgba(245, 152, 26, 0.15); border-left: 4px solid #f59e0b;
        border-radius: 8px; padding: 14px 18px; margin: 12px 0; color: #fcd34d;
    }
    .alert-info {
        background: rgba(59, 130, 246, 0.12); border-left: 4px solid #3b82f6;
        border-radius: 8px; padding: 14px 18px; margin: 12px 0; color: #93c5fd;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


# ── Helpers ────────────────────────────────────────────────────────────────────

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


def _parse_api_error(resp: requests.Response) -> str:
    """Extract a user-friendly error message from an HTTP response."""
    try:
        data = resp.json()
        detail = data.get("detail", "")
        if detail:
            return f"HTTP {resp.status_code}: {detail}"
    except Exception:
        pass
    text = resp.text[:200] if resp.text else "Unknown error"
    return f"HTTP {resp.status_code}: {text}"


def _check_backend_once(
    backend_url: str, timeout: int = _HEALTH_TIMEOUT
) -> tuple[bool, dict, str]:
    """
    Single health check attempt against GET /health.

    Returns (is_online, health_data, error_message).
    """
    base_url = _normalize_backend_url(backend_url)
    health_url = f"{base_url}/health"
    try:
        resp = requests.get(health_url, timeout=timeout)
        if resp.status_code == 200:
            data = resp.json()
            if isinstance(data, dict) and data.get("status") in ("ok", "healthy"):
                return True, data, ""
            status = data.get("status", "unknown") if isinstance(data, dict) else "unknown"
            return False, data, f"Unexpected health status: {status}"
        return False, {}, f"Health endpoint returned HTTP {resp.status_code}"
    except requests.exceptions.Timeout:
        return False, {}, "Connection timed out — the backend may be slow to respond."
    except requests.exceptions.ConnectionError:
        return (
            False, {},
            "Connection refused — the backend may be starting up or unavailable.",
        )
    except Exception as exc:
        return False, {}, f"Health check error: {exc}"


def check_backend_with_retry(
    backend_url: str,
    retry_delays: list[int] = _COLD_START_RETRY_DELAYS,
) -> tuple[bool, dict, str]:
    """
    Check backend connectivity via GET /health with automatic retry
    and backoff.

    Uses the provided schedule of delays (in seconds) between attempts.
    This gracefully handles Render free-tier cold starts which can take
    up to 60 seconds.

    Returns (is_online, health_data, error_message).
    """
    last_error = ""
    last_data: dict = {}

    for delay in retry_delays:
        if delay > 0:
            time.sleep(delay)

        online, data, err = _check_backend_once(backend_url)

        if online:
            return True, data, ""

        last_error = err
        last_data = data

    return False, last_data, last_error


def _safe_get(
    url: str,
    timeout: int = _API_TIMEOUT,
    retries: int = 3,
    backoff: float = 1.5,
) -> requests.Response | None:
    """
    GET request with retry for transient network errors.

    Retries on connection errors and timeouts.
    Returns the response object on success, None on permanent failure.
    """
    for attempt in range(retries):
        try:
            return requests.get(url, timeout=timeout)
        except (requests.exceptions.Timeout,
                requests.exceptions.ConnectionError):
            if attempt < retries - 1:
                time.sleep(backoff ** attempt)
        except Exception:
            return None
    return None


def _safe_post(url: str, **kwargs) -> requests.Response | None:
    """
    POST request with retry for transient network errors.

    Retries on connection errors and timeouts.
    Returns the response object on success, None on permanent failure.
    """
    timeout = kwargs.pop("timeout", _API_TIMEOUT)
    retries = kwargs.pop("retries", 3)
    backoff = kwargs.pop("backoff", 1.5)

    for attempt in range(retries):
        try:
            return requests.post(url, timeout=timeout, **kwargs)
        except (requests.exceptions.Timeout,
                requests.exceptions.ConnectionError):
            if attempt < retries - 1:
                time.sleep(backoff ** attempt)
        except Exception:
            return None
    return None


def _duration_str(started_at: str | None, finished_at: str | None) -> str:
    """Compute human-readable duration from ISO timestamps."""
    if not started_at or not finished_at:
        return "—"
    try:
        from datetime import datetime

        def _parse(s: str):
            for f in (
                "%Y-%m-%dT%H:%M:%S.%f%z", "%Y-%m-%dT%H:%M:%S%z",
                "%Y-%m-%dT%H:%M:%S.%f", "%Y-%m-%dT%H:%M:%S",
            ):
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


def _detect_rate_limit_error(final_summary: str | None) -> bool:
    """
    Detect whether the run's final_summary indicates an LLM
    rate-limit issue (429) for openai/gpt-oss-120b.

    Does NOT trigger a model fallback — the production provider
    is always Groq openai/gpt-oss-120b.
    """
    if not final_summary:
        return False
    s = final_summary.lower()
    keywords = (
        "rate_limit", "rate limit", "429",
        "ratelimit", "too many requests", "quota",
    )
    return any(k in s for k in keywords)


# ── Stage definitions for repair timeline ──────────────────────────────────────

REPAIR_STAGES = [
    ("upload", "📦", "Project Uploaded",
     "ZIP extracted and workspace initialized."),
    ("initial_test", "🧪", "Initial Test Run",
     "Running pytest to identify failing tests."),
    ("architect", "🏛️", "Architect Analysis",
     "Agent analyzes failures and creates a repair plan."),
    ("coder", "💻", "Code Repair",
     "Coder agent generates and applies targeted patch."),
    ("test", "🧪", "Tests Executed",
     "Pytest re-run after patch to verify fixes."),
    ("reviewer", "🔍", "Reviewer Audit",
     "Independent audit of changes & regression risk."),
]

_PATCH_ERROR_KEYWORDS = (
    "patch application failed", "failed to patch", "no hunks found",
)


# ── Sidebar ────────────────────────────────────────────────────────────────────

st.sidebar.title("🛡️ AegisCode Settings")

raw_backend_url = st.sidebar.text_input(
    "Backend URL (root or /health)",
    value=DEFAULT_BACKEND,
    key="backend_url_input",
)
base_backend_url = _normalize_backend_url(raw_backend_url)
api_url = f"{base_backend_url}/api"

# ── Backend connectivity with retry ────────────────────────────────────────────

if "backend_online" not in st.session_state:
    st.session_state["backend_online"] = False
if "health_data" not in st.session_state:
    st.session_state["health_data"] = {}
if "backend_error" not in st.session_state:
    st.session_state["backend_error"] = ""

# Connection status display while attempting
if not st.session_state["backend_online"]:
    with st.sidebar:
        st.markdown("🔄 **Connecting to AegisCode backend...**")
        st.caption("The backend may take up to 60 seconds to wake up.")

    online, health_data, error = check_backend_with_retry(base_backend_url)
    st.session_state["backend_online"] = online
    st.session_state["health_data"] = health_data
    st.session_state["backend_error"] = error
    st.rerun()

if st.session_state["backend_online"]:
    llm_prov = st.session_state["health_data"].get("llm_provider", "unknown")
    st.sidebar.success(f"✅ Backend Online — LLM: `{llm_prov}`")
else:
    # Show retry button when all attempts have been exhausted
    st.sidebar.error("❌ Backend Unreachable")
    st.sidebar.caption(f"Error: {st.session_state['backend_error']}")
    st.sidebar.markdown("The backend did not respond after several attempts.")

    if st.sidebar.button("🔄 Retry Connection", key="btn_retry_conn"):
        st.session_state["backend_online"] = False
        st.rerun()

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
    st.stop()

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

st.markdown(
    '<div class="main-title">🛡️ AegisCode</div>',
    unsafe_allow_html=True,
)
st.markdown(
    '<div class="subtitle">'
    "Autonomous Self-Healing Multi-Agent Software Engineering System"
    "</div>",
    unsafe_allow_html=True,
)

tabs = st.tabs([
    "🚀 Launch Repair Run",
    "📊 Repair Results & Timeline",
    "ℹ️ System Overview",
])


# ── Tab 1: Launch Repair Run ───────────────────────────────────────────────────
with tabs[0]:
    st.subheader("1. Upload Python Project (.zip)")
    uploaded_file = st.file_uploader(
        "Choose a project ZIP containing failing pytest tests",
        type=["zip"],
        help="Upload a .zip archive of your Python project with pytest tests.",
    )

    col1, col2 = st.columns([1, 2])

    if uploaded_file is not None:
        with col1:
            if st.button(
                "📤 Upload & Initialize Project",
                type="primary",
                key="btn_upload",
            ):
                with st.spinner("Validating and extracting project workspace..."):
                    try:
                        file_tuple = (
                            uploaded_file.name,
                            uploaded_file.getvalue(),
                            "application/zip",
                        )
                        files = {"file": file_tuple}
                        res = _safe_post(
                            f"{api_url}/projects/upload",
                            files=files, timeout=30,
                        )
                        if res is None:
                            st.error(
                                "❌ Connection error during upload — "
                                "the backend may have restarted. Please try again."
                            )
                            st.stop()

                        if res.status_code == 201:
                            data = res.json()
                            st.session_state["project_id"] = data["project_id"]
                            st.session_state.pop("active_run_id", None)
                            st.success(
                                f"✅ Project Uploaded!  \n"
                                f"**ID:** `{data['project_id']}`  \n"
                                f"**Files:** {data['file_count']} Python source files"
                            )
                        elif res.status_code == 413:
                            st.error(
                                "❌ File too large — the uploaded project "
                                "exceeds the size limit."
                            )
                        elif res.status_code == 415:
                            st.error(
                                "❌ Unsupported file type — only .zip archives "
                                "are accepted."
                            )
                        elif res.status_code == 422:
                            st.error(
                                f"❌ ZIP validation failed — "
                                f"{_parse_api_error(res)}"
                            )
                        elif res.status_code == 429:
                            st.warning(
                                "⚠️ LLM rate limit reached. Please wait "
                                "and try again."
                            )
                        elif res.status_code >= 500:
                            st.error(
                                f"❌ Server error (HTTP {res.status_code}). "
                                "The backend encountered an internal error. "
                                "Please try again."
                            )
                        else:
                            st.error(f"❌ Upload failed — {_parse_api_error(res)}")
                    except Exception as exc:
                        st.error(f"❌ Connection error during upload: {exc}")
    else:
        st.info(
            "📁 No project selected. Please upload a .zip file above to continue."
        )

    if "project_id" in st.session_state:
        st.markdown("---")
        st.subheader("2. Configure & Start Self-Healing Repair")

        col_cfg1, col_cfg2 = st.columns([1, 2])
        with col_cfg1:
            max_iters = st.slider(
                "Maximum Repair Iterations",
                min_value=1, max_value=10, value=5,
                help="How many Architect→Coder→Test→Reviewer cycles to allow.",
            )

        pid_display = st.session_state["project_id"]
        st.caption(f"Project ID: `{pid_display}`")

        if st.button(
            "⚡ Start Autonomous Repair Graph",
            type="primary",
            key="btn_start_repair",
        ):
            with st.spinner("Initializing repair run..."):
                try:
                    payload = {
                        "project_id": st.session_state["project_id"],
                        "max_iterations": max_iters,
                    }
                    create_res = _safe_post(
                        f"{api_url}/runs", json=payload, timeout=30,
                    )
                    if create_res is None:
                        st.error(
                            "❌ Connection error — could not reach backend. "
                            "The backend may be starting up. Please retry."
                        )
                        st.stop()

                    if create_res.status_code == 201:
                        run_id = create_res.json()["run_id"]
                        st.session_state["active_run_id"] = run_id

                        # Trigger repair loop
                        repair_res = _safe_post(
                            f"{api_url}/runs/{run_id}/repair", timeout=10,
                        )
                        if repair_res is None:
                            st.error(
                                "❌ Connection error while launching repair. "
                                "Please check the run in Repair Results."
                            )
                            st.stop()

                        if repair_res.status_code in (200, 202):
                            st.success(
                                f"🚀 Autonomous Repair Graph launched!  \n"
                                f"**Run ID:** `{run_id}`  \n"
                                "Switch to **📊 Repair Results & Timeline** "
                                "to monitor progress."
                            )
                        elif repair_res.status_code == 429:
                            st.warning(
                                "⚠️ LLM rate limit reached during repair "
                                "launch. Please wait and try again."
                            )
                        elif repair_res.status_code == 404:
                            st.error(
                                "❌ Run not found — the project may have been "
                                "cleaned up. Please re-upload and try again."
                            )
                        elif repair_res.status_code >= 500:
                            st.error(
                                f"❌ Server error (HTTP {repair_res.status_code}). "
                                "Please try again."
                            )
                        else:
                            st.error(
                                f"❌ Failed to launch repair — "
                                f"{_parse_api_error(repair_res)}"
                            )
                    elif create_res.status_code == 429:
                        st.warning(
                            "⚠️ LLM rate limit reached. Please wait "
                            "and try again."
                        )
                    elif create_res.status_code == 404:
                        st.error(
                            "❌ Project not found. It may have expired. "
                            "Please re-upload the project."
                        )
                    elif create_res.status_code >= 500:
                        st.error(
                            f"❌ Server error (HTTP {create_res.status_code}). "
                            "Please try again."
                        )
                    else:
                        st.error(
                            f"❌ Failed to create run — "
                            f"{_parse_api_error(create_res)}"
                        )
                except Exception as exc:
                    st.error(f"❌ Error launching repair: {exc}")


# ── Tab 2: Repair Results & Timeline ──────────────────────────────────────────
with tabs[1]:
    # Resolve the run ID to inspect
    active_run_id = st.session_state.get("active_run_id", "")
    if not active_run_id:
        manual_id = st.text_input(
            "Enter Run ID to inspect",
            value="",
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
    with st.spinner("Fetching run details..."):
        status_resp = _safe_get(
            f"{api_url}/runs/{active_run_id}/status", timeout=15,
        )
        results_resp = _safe_get(
            f"{api_url}/runs/{active_run_id}/results", timeout=15,
        )

    if status_resp is None or results_resp is None:
        st.markdown(
            '<div class="alert-error">⚠️ <strong>Backend Unavailable</strong><br>'
            'Could not reach the backend to fetch run details. '
            "The backend may be starting up (Render free-tier cold start). "
            "Please try again in a minute, or use the sidebar to retry the connection."
            "</div>",
            unsafe_allow_html=True,
        )
        st.stop()

    if status_resp.status_code == 404 or results_resp.status_code == 404:
        st.warning(f"Run `{active_run_id}` not found. Please verify the run ID.")
        st.stop()

    if status_resp.status_code == 429 or results_resp.status_code == 429:
        st.markdown(
            '<div class="alert-warning">⚠️ <strong>LLM Rate Limit Reached</strong><br>'
            "The backend returned 429 Too Many Requests for "
            "`openai/gpt-oss-120b`.<br><br>"
            "Please wait 1–2 minutes for your token bucket to refill, "
            "then try again.</div>",
            unsafe_allow_html=True,
        )
        st.stop()

    if status_resp.status_code != 200 or results_resp.status_code != 200:
        st.error(
            f"Failed to fetch run details "
            f"(HTTP {status_resp.status_code}/{results_resp.status_code}). "
            "Please try again."
        )
        st.stop()

    try:
        sdata = status_resp.json()
        rdata = results_resp.json()
    except Exception as exc:
        st.error(f"❌ Malformed API response — could not parse JSON: {exc}")
        st.stop()

    run_status: str = sdata.get("status", "unknown")
    iterations: list = rdata.get("iterations", [])
    final_summary: str | None = sdata.get("final_summary", "")

    current_iter = sdata.get("current_iteration", 0)
    max_iter = sdata.get("max_iterations", 5)

    is_rate_limit_err = _detect_rate_limit_error(final_summary)

    # ── Status Card ───────────────────────────────────────────────────────────────
    _STATUS_CONFIG = {
        "passed":        ("🟢", "Repair Successful", "passed"),
        "already_passing": ("🟢", "Already Passing", "passed"),
        "failed":        ("🔴", "Repair Failed", "failed"),
        "error":         ("🔴", "Repair Error", "failed"),
        "stalled":       ("🟠", "Repair Stalled", "stalled"),
        "running":       ("🔵", "Repair In Progress", "running"),
        "pending":       ("⚪", "Pending", "running"),
    }

    icon, label, css_cls = _STATUS_CONFIG.get(
        run_status, ("⚪", run_status.upper(), "running"),
    )

    if is_rate_limit_err and run_status in ("failed", "error"):
        icon, label, css_cls = (
            "⏳", "LLM Rate Limit Reached", "stalled",
        )

    duration_str = _duration_str(
        sdata.get("started_at"), sdata.get("finished_at"),
    )

    # ── Build status card content ─────────────────────────────────────────────────
    extra_html_lines: list[str] = []

    if run_status in ("passed", "already_passing") and not is_rate_limit_err:
        extra_html_lines = [
            "<p>✅ Tests Passed &nbsp;|&nbsp; "
            "✅ Reviewer Approved &nbsp;|&nbsp; "
            f"Iterations: {current_iter}/{max_iter} &nbsp;|&nbsp; "
            f"Duration: {duration_str}</p>",
        ]
    elif run_status == "running" and not is_rate_limit_err:
        extra_html_lines = [
            f"<p>🔄 Current Iteration: {current_iter}/{max_iter} "
            "— auto-refreshing…</p>",
            "<p><small>ℹ️ The backend is working on the repair. "
            "If Groq returns rate-limit errors for "
            "`openai/gpt-oss-120b`, AegisCode will report them "
            "here — no automatic fallback to another model.</small></p>",
        ]
    elif is_rate_limit_err:
        extra_html_lines = [
            "<p>⚠️ <strong>Groq rate limit reached for "
            "openai/gpt-oss-120b</strong></p>",
            "<p>The LLM returned a 429 Too Many Requests response.</p>",
            "<p>💡 <em>Please wait 1–2 minutes for your token bucket "
            "to refill, then start a new repair run.</em></p>",
            f"<p>Iterations completed: {current_iter}/{max_iter}</p>",
        ]
    elif run_status in ("failed", "error"):
        extra_html_lines = [
            f"<p>❌ Termination: "
            f"{final_summary or 'See iteration details below'}</p>",
            f"<p>Iterations completed: {current_iter}/{max_iter}</p>",
        ]
    elif run_status == "stalled":
        extra_html_lines = [
            "<p>⚠️ The repair loop detected repeated identical failures "
            "and stopped.</p>",
            f"<p>{final_summary or ''}</p>",
            f"<p>Iterations completed: {current_iter}/{max_iter}</p>",
        ]
    else:
        extra_html_lines = [
            f"<p>Status: {run_status}</p>",
            f"<p>Iterations: {current_iter}/{max_iter}</p>",
        ]

    extra_lines_html = "\n".join(extra_html_lines)

    st.markdown(
        f"""
        <div class="status-card {css_cls}">
          <h2>{icon} {label}</h2>
          {extra_lines_html}
        </div>
        """,
        unsafe_allow_html=True,
    )

    # ── Patch failure alert ─────────────────────────────────────────────────────
    patch_error_found = False
    for it in iterations:
        changes = it.get("code_changes") or []
        if isinstance(changes, dict):
            changes = [changes]
        for ch in changes:
            expl = ch.get("explanation", "") or ""
            rc = ch.get("root_cause", "") or ""
            combined = f"{expl} {rc}".lower()
            if any(k in combined for k in _PATCH_ERROR_KEYWORDS):
                if not patch_error_found:
                    patch_error_found = True
                    target_file = ch.get("file_path", "unknown")
                    st.markdown(
                        f"""
                        <div class="alert-error">
                        ❌ <strong>Repair Failed — Patch Application Error</strong><br><br>
                        <strong>File Being Patched:</strong>
                        <code>{target_file}</code><br>
                        <strong>Reason:</strong> {expl or rc}<br><br>
                        <strong>Iterations completed:</strong>
                        {current_iter} / {max_iter}
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )
                    break
        if patch_error_found:
            break

    # Auto-refresh while running
    if run_status == "running":
        st.info(
            "🔄 Repair Graph running in background — "
            "auto-refreshing in 3 seconds…"
        )
        time.sleep(3)
        st.rerun()

    st.markdown("---")

    # ── Visual Repair Timeline ────────────────────────────────────────────────────
    st.subheader("📅 Repair History")

    def _stage_step(
        icon_str: str,
        label_str: str,
        detail_str: str = "",
        state: str = "info",
    ) -> None:
        """Render a single timeline stage with a state indicator."""
        state_icons = {
            "completed": "✅",
            "running": "🔄",
            "failed": "❌",
            "waiting": "⏳",
            "info": icon_str,
        }
        display_icon = state_icons.get(state, icon_str)
        detail_html = (
            f"<div class='timeline-detail'>{detail_str}</div>"
            if detail_str else ""
        )
        st.markdown(
            f"""
            <div class="timeline-step">
              <div class="timeline-icon">{display_icon}</div>
              <div>
                <div class="timeline-label">{label_str}</div>
                {detail_html}
              </div>
            </div>
            <div class="timeline-connector"></div>
            """,
            unsafe_allow_html=True,
        )

    # Stage 1: Upload (always completed since we have a run)
    _stage_step(
        "📦", "1. Project Uploaded",
        "ZIP extracted and workspace initialized.",
        state="completed",
    )

    # Stage 2: Initial Test
    initial_test_ok = False
    if iterations:
        first_it = iterations[0]
        tres = first_it.get("test_results") or {}
        if tres:
            initial_test_ok = bool(tres.get("success", False))
            passed_c = tres.get("passed", 0)
            failed_c = tres.get("failed", 0)
            test_state = (
                "completed" if initial_test_ok
                else "running" if run_status == "running"
                else "failed"
            )
            _stage_step(
                "🧪", "2. Initial Test Run",
                f"{passed_c} passed, {failed_c} failed",
                state=test_state,
            )
        else:
            _stage_step(
                "🧪", "2. Initial Test Run",
                "Awaiting results...", state="waiting",
            )
    else:
        _stage_step(
            "🧪", "2. Initial Test Run",
            "Awaiting results...", state="waiting",
        )

    # Stages 3-6: Based on iteration data
    if not iterations:
        for stage_idx in range(2, len(REPAIR_STAGES)):
            _, stage_icon, stage_label, _ = REPAIR_STAGES[stage_idx]
            _stage_step(
                stage_icon,
                f"{stage_idx + 1}. {stage_label}",
                "Not started",
                state="waiting",
            )
    else:
        for it in iterations:
            it_num = it.get("iteration_number", "?")

            # Architect
            has_arch = bool(it.get("architecture_plan"))
            arch_detail = (
                it.get("architecture_plan", {}).get("summary", "")
                if has_arch else "Waiting…"
            )
            _stage_step(
                "🏛️", f"Iteration {it_num} — Architect Analysis",
                arch_detail,
                state="completed" if has_arch else "waiting",
            )

            # Coder
            has_code = bool(it.get("code_changes") or it.get("test_results"))
            changes_list = it.get("code_changes") or []
            if isinstance(changes_list, dict):
                changes_list = [changes_list]

            patch_err = None
            for ch in changes_list:
                expl = (ch.get("explanation", "") or "").lower()
                rc = (ch.get("root_cause", "") or "").lower()
                if any(k in f"{expl} {rc}" for k in _PATCH_ERROR_KEYWORDS):
                    patch_err = ch.get("explanation") or ch.get("root_cause")
                    break

            if patch_err:
                coder_state = "failed"
                coder_detail = patch_err
            elif has_code:
                coder_state = "completed"
                coder_detail = "Patch applied"
            else:
                coder_state = "waiting"
                coder_detail = "Waiting…"
            _stage_step(
                "💻", f"Iteration {it_num} — Code Repair",
                coder_detail, state=coder_state,
            )

            # Tests
            tres = it.get("test_results") or {}
            if tres:
                passed_c = tres.get("passed", 0)
                failed_c = tres.get("failed", 0)
                test_ok = tres.get("success", False)
                _stage_step(
                    "🧪", f"Iteration {it_num} — Tests Executed",
                    f"{passed_c} passed, {failed_c} failed",
                    state="completed" if test_ok else "failed",
                )
            else:
                _stage_step(
                    "🧪", f"Iteration {it_num} — Tests Executed",
                    "Awaiting results…", state="waiting",
                )

            # Reviewer
            rev = it.get("review_result") or {}
            if rev:
                rev_approved = rev.get("approved", False)
                _stage_step(
                    "🔍", f"Iteration {it_num} — Reviewer Audit",
                    f"Approved: {rev_approved} | "
                    f"Risk: {rev.get('regression_risk', '?')}",
                    state="completed" if rev_approved else "failed",
                )
            else:
                _stage_step(
                    "🔍", f"Iteration {it_num} — Reviewer Audit",
                    "Awaiting review…", state="waiting",
                )

    # Final stage
    if run_status in ("passed", "already_passing") and not is_rate_limit_err:
        _stage_step(
            "✅",
            "Repair Complete — All Tests Passed & Reviewer Approved",
            "Done", state="completed",
        )
    elif run_status in ("failed", "error"):
        _stage_step("❌", "Repair Failed", final_summary or "", state="failed")
    elif run_status == "stalled":
        _stage_step("🟠", "Repair Stalled", final_summary or "", state="failed")
    elif run_status == "running":
        _stage_step("🔄", "Repair In Progress", "Working...", state="running")

    st.markdown("---")

    # ── Repair Summary ────────────────────────────────────────────────────────────
    st.subheader("📋 Repair Summary")

    summary_fields: list[tuple[str, str]] = []
    status_label = run_status.upper()
    if is_rate_limit_err:
        status_label = f"{status_label} (Rate Limited)"
    summary_fields.append(("Status", f"{icon} {status_label}"))

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
            decision = "✅ APPROVED" if rev_last.get("approved") else "❌ NOT APPROVED"
            summary_fields.append(("Reviewer Decision", decision))

    if final_summary:
        summary_fields.append(("Termination Reason", final_summary))

    if duration_str != "—":
        summary_fields.append(("Duration", duration_str))

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

    # ── Download Section ────────────────────────────────────────────────────────
    st.subheader("⬇ Download Repaired Project")

    if run_status in ("passed", "already_passing"):
        st.markdown(
            """
            <div class="download-section">
              <h3>✅ REPAIR SUCCESSFUL</h3>
              <p>
                Your project has been repaired successfully.<br>
                All authoritative tests passed and the Reviewer approved
                the changes.
              </p>
            </div>
            """,
            unsafe_allow_html=True,
        )

        # Fetch the ZIP from the backend download endpoint
        download_url = f"{api_url}/runs/{active_run_id}/download"
        try:
            dl_resp = _safe_post(download_url, timeout=60, stream=True)
            if dl_resp is None:
                st.error(
                    "❌ Connection error — could not reach backend for "
                    "download. The backend may be starting up. "
                    "Please try again."
                )
            elif dl_resp.status_code == 200:
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
                st.warning(
                    "⚠️ Repaired project is not currently available "
                    "for download. The workspace may still be processing."
                )
            elif dl_resp.status_code == 404:
                st.warning(
                    "⚠️ Repaired project workspace not found. "
                    "It may have been cleaned up."
                )
            elif dl_resp.status_code == 429:
                st.warning(
                    "⚠️ LLM rate limit reached. Please wait "
                    "and try again."
                )
            elif dl_resp.status_code >= 500:
                st.error(
                    f"❌ Server error (HTTP {dl_resp.status_code}) "
                    "during download. Please try again."
                )
            else:
                st.error(
                    f"❌ Download failed (HTTP {dl_resp.status_code}). "
                    "Please try again or contact support."
                )
        except Exception as exc:
            st.error(f"❌ Download unavailable — could not reach backend: {exc}")

    elif run_status == "running":
        st.info(
            "⏳ Download will be available once the repair completes "
            "successfully."
        )
    else:
        st.warning(
            "⬇️ **Download is available only after a successful repair.** "
            f"Current status: **{run_status.upper()}** — "
            "the run did not complete successfully, so no repaired "
            "project is available for download."
        )

    st.markdown("---")

    # ── Iteration Detail Tabs ─────────────────────────────────────────────────
    if iterations:
        st.subheader("🔬 Iteration-by-Iteration Details")
        it_tabs = st.tabs(
            [f"Iteration {it['iteration_number']}" for it in iterations]
        )
        for idx, it in enumerate(iterations):
            with it_tabs[idx]:
                it_num = it.get("iteration_number", idx + 1)
                changes = it.get("code_changes") or []
                if isinstance(changes, dict):
                    changes = [changes]

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
                    if changes:
                        # Check for patch application failure
                        patch_error = None
                        target_file = None
                        for ch in changes:
                            expl = ch.get("explanation", "") or ""
                            rc = ch.get("root_cause", "") or ""
                            combined = f"{expl} {rc}".lower()
                            if any(
                                k in combined for k in _PATCH_ERROR_KEYWORDS
                            ):
                                patch_error = expl or rc
                                target_file = ch.get(
                                    "file_path", "unknown",
                                )
                                break

                        if patch_error:
                            will_retry = (it_num < max_iter)
                            if will_retry:
                                retry_str = (
                                    f"Yes — the system will retry in "
                                    f"Iteration {it_num + 1} of {max_iter}"
                                )
                            else:
                                retry_str = (
                                    f"No — the maximum iteration limit "
                                    f"({max_iter}) has been reached"
                                )
                            if run_status in ("passed", "already_passing"):
                                dl_status = "Available"
                            else:
                                dl_status = (
                                    "Unavailable until the repair completes "
                                    "successfully"
                                )

                            st.markdown(
                                f"""
                                <div style="background-color: rgba(239, 68, 68, 0.12);
                                border-left: 4px solid #ef4444;
                                padding: 14px 18px;
                                border-radius: 8px; margin-bottom: 16px;">
                                  <h4 style="color: #ef4444; margin: 0 0 8px 0;">
                                  ❌ Patch Application Failed in
                                  Iteration {it_num}</h4>
                                  <p style="margin: 4px 0;">
                                  <strong>File Being Patched:</strong>
                                  <code>{target_file}</code></p>
                                  <p style="margin: 4px 0;">
                                  <strong>Reason:</strong>
                                  {patch_error}</p>
                                  <p style="margin: 4px 0;">
                                  <strong>Tests Passed / Failed:</strong>
                                  {it.get('test_results', {}).get('passed', 0)} passed,
                                  {it.get('test_results', {}).get('failed', 0)} failed</p>
                                  <p style="margin: 4px 0;">
                                  <strong>Will System Retry?</strong>
                                  {retry_str}</p>
                                  <p style="margin: 4px 0;">
                                  <strong>Final Download Availability:</strong>
                                  {dl_status}</p>
                                </div>
                                """,
                                unsafe_allow_html=True,
                            )

                        # Show each change
                        for ch in changes:
                            fpath = ch.get("file_path", "N/A")
                            ctype = ch.get("change_type", "N/A")
                            expl = ch.get("explanation", "N/A")
                            st.write(
                                f"**File:** `{fpath}` "
                                f"— **Type:** `{ctype}`"
                            )
                            st.write(f"**Explanation:** {expl}")
                            if ch.get("root_cause"):
                                st.write(
                                    f"**Root Cause:** {ch.get('root_cause')}"
                                )
                            if ch.get("patch"):
                                with st.expander("Show Patch"):
                                    st.code(
                                        ch["patch"], language="python",
                                    )
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
                            st.write(
                                f"**Root Cause Fixed:** `{rev.get('root_cause_fixed')}`"
                            )
                        if rev.get("regression_risk"):
                            st.write(
                                f"**Regression Risk:** "
                                f"`{rev.get('regression_risk')}`"
                            )
                        if rev.get("reasoning"):
                            st.write(f"**Reasoning:** {rev.get('reasoning')}")
                    else:
                        st.caption("No reviewer result recorded.")

    st.markdown("---")

    # ── Code Changes / Git Diff ─────────────────────────────────────────────────
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
            modified = {
                fp: ch for fp, ch in seen.items()
                if ch.get("change_type") not in ("add",)
            }
            added = {
                fp: ch for fp, ch in seen.items()
                if ch.get("change_type") == "add"
            }
            deleted = {
                fp: ch for fp, ch in seen.items()
                if ch.get("change_type") == "delete"
            }

            if modified:
                st.markdown(
                    f"<span class='diff-badge modified'>MODIFIED</span> "
                    f"{len(modified)} file(s)",
                    unsafe_allow_html=True,
                )
                for fp, ch in modified.items():
                    display_name = (
                        fp.split("/")[-1] if "/" in fp else fp
                    )
                    with st.expander(f"📝 {display_name}"):
                        st.write(f"**Explanation:** {ch.get('explanation', 'N/A')}")
                        if ch.get("root_cause"):
                            st.write(
                                f"**Root Cause:** {ch.get('root_cause')}"
                            )
                        if ch.get("patch"):
                            st.code(ch["patch"], language="python")

            if added:
                st.markdown(
                    f"<span class='diff-badge added'>ADDED</span> "
                    f"{len(added)} file(s)",
                    unsafe_allow_html=True,
                )
                for fp, ch in added.items():
                    display_name = (
                        fp.split("/")[-1] if "/" in fp else fp
                    )
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
                    display_name = (
                        fp.split("/")[-1] if "/" in fp else fp
                    )
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
