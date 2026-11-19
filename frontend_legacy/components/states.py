"""
Standard UI states (Empty, Loading, Error, Warning) for AegisCode.
"""

from __future__ import annotations

import streamlit as st


def render_empty_state(
    title: str,
    description: str,
    icon: str = "🔍",
    cta_label: str | None = None,
    cta_key: str | None = None,
) -> bool:
    """Render a polished, centered empty state container."""
    st.markdown(
        f"""
        <div class="aegis-empty-state">
          <div class="aegis-empty-icon">{icon}</div>
          <h3 class="aegis-empty-title">{title}</h3>
          <p class="aegis-empty-desc">{description}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )
    if cta_label and cta_key:
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            return st.button(
                cta_label,
                key=cta_key,
                type="primary",
                use_container_width=True,
            )
    return False


def render_error_alert(
    title: str,
    message: str,
    technical_details: str | None = None,
) -> None:
    """Render a professional error alert with optional expandable technical details."""
    st.markdown(
        f"""
        <div class="aegis-alert error">
          <strong>❌ {title}</strong><br>
          <span style="font-size: 0.85rem;">{message}</span>
        </div>
        """,
        unsafe_allow_html=True,
    )
    if technical_details:
        with st.expander("Technical details"):
            st.code(technical_details, language="text")


def render_warning_alert(title: str, message: str) -> None:
    """Render a styled warning alert."""
    st.markdown(
        f"""
        <div class="aegis-alert warning">
          <strong>⚠️ {title}</strong><br>
          <span style="font-size: 0.85rem;">{message}</span>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_info_alert(title: str, message: str) -> None:
    """Render a styled info alert."""
    st.markdown(
        f"""
        <div class="aegis-alert info">
          <strong>ℹ️ {title}</strong><br>
          <span style="font-size: 0.85rem;">{message}</span>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_rate_limit_alert() -> None:
    """Render a Groq 429 TPM rate-limit guidance banner."""
    st.markdown(
        """
        <div class="aegis-alert warning">
          <strong>⏳ LLM Rate Limit Reached (Groq 429 Too Many Requests)</strong><br>
          The token rate limit for <code>openai/gpt-oss-120b</code> was reached.<br>
          AegisCode enforces strict single-model fidelity without fallback.<br>
          The system will automatically resume when the token bucket refills in ~30-60s.
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_http_error_state(
    status_code: int,
    message: str | None = None,
    technical_details: str | None = None,
) -> None:
    """Render authoritative HTTP error UI states for 401, 403, 404, 409, 422, 429, 500, 503, etc."""
    if status_code == 401:
        title = "🔒 401 Unauthorized"
        desc = message or "Authentication required. Your session has expired or requires sign-in."
    elif status_code == 403:
        title = "🛡️ 403 Access Restricted / Guest Ownership Error"
        desc = (
            message
            or "Your guest session has expired or this repair belongs to another session. "
            "Start a new repair or restore the original session."
        )
    elif status_code == 404:
        title = "🔍 404 Not Found"
        desc = message or "The requested repair run ID or workspace project could not be found."
    elif status_code == 409:
        title = "⚠️ 409 Resource Conflict"
        desc = message or "The request conflicts with the current server or repair run state."
    elif status_code == 422:
        title = "📋 422 Validation Error"
        desc = (
            message
            or "The request contained invalid parameters. Please check the fields and try again."
        )
    elif status_code == 429:
        title = "⏳ 429 Rate Limit Exceeded"
        desc = (
            message
            or "API or LLM rate limit reached. AegisCode is auto-retrying as token budget refills."
        )
    elif status_code == 503:
        title = "🔌 503 Service Unavailable"
        desc = (
            message
            or "AegisCode backend service is currently initializing or undergoing maintenance."
        )
    elif status_code >= 500:
        title = "💥 500 Backend Internal Server Error"
        desc = (
            message
            or "An internal error occurred on the AegisCode backend. Please retry the operation."
        )
    else:
        title = "🌐 Network Connection Timeout or Error"
        desc = (
            message
            or (
                "Unable to establish connection to AegisCode backend services. "
                "Please check network connectivity."
            )
        )

    render_error_alert(title, desc, technical_details=technical_details)


def render_loading_state(message: str = "Loading repair execution telemetry...") -> None:
    """Render a clean loading indicator for asynchronous operations."""
    st.markdown(
        f"""
        <div style="display: flex; align-items: center; gap: 12px; padding: 18px 24px;
        background: var(--bg-panel); border-radius: var(--radius-md);
        border: 1px solid var(--border-subtle); margin: 12px 0;">
          <div style="font-size: 1.4rem; animation: spin 1s linear infinite;">⏳</div>
          <div>
            <div style="font-weight: 700; font-size: 0.92rem; color: var(--text-primary);">
              {message}
            </div>
            <div style="font-size: 0.78rem; color: var(--text-secondary);">
              Authoritative execution sync in progress...
            </div>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_stalled_state(
    reason: str | None = None,
    last_phase: str | None = None,
    detail: str | None = None,
) -> None:
    """Render explicit STALLED state banner with explanation and recovery options."""
    st_reason = reason or "The graph execution exceeded turn timeout or encountered node freeze."
    st_detail = detail or "The repair graph did not terminate cleanly. Prior agent telemetry is preserved below."
    st.markdown(
        f"""
        <div class="aegis-status-banner failed" style="border: 1px solid rgba(245, 158, 11, 0.5);
        background: linear-gradient(135deg, rgba(245, 158, 11, 0.1), rgba(245, 158, 11, 0.03));">
          <div>
            <h3 class="aegis-banner-title" style="color: #fbbf24;">🟠 REPAIR EXECUTION STALLED</h3>
            <p class="aegis-banner-desc" style="color: #fef3c7;">
              <strong>Status: STALLED</strong><br>
              Reason: {st_reason}<br>
              Last completed phase: <strong>{last_phase or 'Autonomous Execution'}</strong>
            </p>
            <div style="margin-top: 8px; font-size: 0.82rem; color: #fde68a;">
              {st_detail}
            </div>
          </div>
          <div style="font-size: 2.2rem;">⏳</div>

        </div>
        """,
        unsafe_allow_html=True,
    )
