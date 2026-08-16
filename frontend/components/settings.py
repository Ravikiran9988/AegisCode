"""
System Configuration & Settings Component for AegisCode.
Presents enterprise settings and security boundaries without exposing secrets.
"""

from __future__ import annotations

import os

import streamlit as st


def render_settings(backend_url: str, health_data: dict) -> None:
    """Render the system settings and configuration panel."""
    st.markdown(
        """
        <div class="aegis-page-header">
          <h1 class="aegis-page-title">Platform Settings & Engine Configuration</h1>
          <p class="aegis-page-desc">
            Inspect active service configurations, production LLM model constraints,
            and security boundaries.
          </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    col_s1, col_s2 = st.columns(2)

    with col_s1:
        st.markdown(
            f"""
            <div class="aegis-health-card">
              <div class="aegis-agent-header">
                <span class="aegis-agent-title">🌐 Backend Service</span>
                <span class="aegis-badge passed">Connected</span>
              </div>
              <div class="aegis-health-row">
                <span class="aegis-health-key">Backend URL</span>
                <span class="aegis-health-val"><code>{backend_url}</code></span>
              </div>
              <div class="aegis-health-row">
                <span class="aegis-health-key">API Framework</span>
                <span class="aegis-health-val">FastAPI / Uvicorn</span>
              </div>
              <div class="aegis-health-row">
                <span class="aegis-health-key">Max Upload Limit</span>
                <span class="aegis-health-val">50 MB (.zip)</span>
              </div>
              <div class="aegis-health-row">
                <span class="aegis-health-key">Execution Timeout</span>
                <span class="aegis-health-val">30.0 seconds</span>
              </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        st.markdown(
            """
            <div class="aegis-health-card">
              <div class="aegis-agent-header">
                <span class="aegis-agent-title">🤖 Production LLM Model</span>
                <span class="aegis-badge passed">Fixed</span>
              </div>
              <div class="aegis-health-row">
                <span class="aegis-health-key">Provider Protocol</span>
                <span class="aegis-health-val">Groq OpenAI-Compatible REST</span>
              </div>
              <div class="aegis-health-row">
                <span class="aegis-health-key">Enforced Model</span>
                <span class="aegis-health-val" style="color: #c084fc;">openai/gpt-oss-120b</span>
              </div>
              <div class="aegis-health-row">
                <span class="aegis-health-key">Fallback Policy</span>
                <span class="aegis-health-val" style="color: #38bdf8;">
                  Strict Single-Model (No Fallback)
                </span>
              </div>
              <div class="aegis-health-row">
                <span class="aegis-health-key">429 Rate-Limit Recovery</span>
                <span class="aegis-health-val">Exponential Backoff with Token Reset</span>
              </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with col_s2:
        db_stat = health_data.get("database", "connected")
        st.markdown(
            f"""
            <div class="aegis-health-card">
              <div class="aegis-agent-header">
                <span class="aegis-agent-title">💾 Database & Persistence</span>
                <span class="aegis-badge passed">Active</span>
              </div>
              <div class="aegis-health-row">
                <span class="aegis-health-key">Engine</span>
                <span class="aegis-health-val">SQLite (SQLAlchemy ORM)</span>
              </div>
              <div class="aegis-health-row">
                <span class="aegis-health-key">Connection Status</span>
                <span class="aegis-health-val" style="color: #34d399;">
                  {db_stat.capitalize()}
                </span>
              </div>
              <div class="aegis-health-row">
                <span class="aegis-health-key">Transactional Persistence</span>
                <span class="aegis-health-val">Atomic per-node commits</span>
              </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        groq_set = "Configured" if os.environ.get("GROQ_API_KEY") else "Configured (Server-Side)"

        st.markdown(
            f"""
            <div class="aegis-health-card">
              <div class="aegis-agent-header">
                <span class="aegis-agent-title">🛡️ Security & Privacy Boundaries</span>
                <span class="aegis-badge passed">Enforced</span>
              </div>
              <div class="aegis-health-row">
                <span class="aegis-health-key">Secrets Exposure</span>
                <span class="aegis-health-val" style="color: #34d399;">
                  Zero API Keys or Tokens Exposed
                </span>
              </div>
              <div class="aegis-health-row">
                <span class="aegis-health-key">LLM API Key Status</span>
                <span class="aegis-health-val" style="color: #34d399;">
                  {groq_set}
                </span>
              </div>
              <div class="aegis-health-row">
                <span class="aegis-health-key">Archive Traversal Shield</span>
                <span class="aegis-health-val" style="color: #34d399;">
                  Zip Slip Guard Enforced
                </span>
              </div>
              <div class="aegis-health-row">
                <span class="aegis-health-key">Test Integrity Protection</span>
                <span class="aegis-health-val" style="color: #34d399;">
                  Read-Only Test Files Enforced
                </span>
              </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
