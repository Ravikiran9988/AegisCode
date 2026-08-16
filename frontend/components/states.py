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
