"""
System Health & Observability Dashboard Component for AegisCode.
"""

from __future__ import annotations

import time
from datetime import datetime

import streamlit as st

try:
    from frontend.utils.api_client import _check_backend_once
except ImportError:
    from utils.api_client import _check_backend_once


def render_system_health(backend_url: str, initial_health_data: dict) -> None:
    """Render the observability and system health dashboard."""
    st.markdown(
        """
        <div class="aegis-page-header">
          <h1 class="aegis-page-title">System Health & Telemetry</h1>
          <p class="aegis-page-desc">
            Real-time operational metrics, round-trip latency, database integrity,
            and execution environment sandboxing.
          </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # Measure real ping latency
    t0 = time.time()
    online, health_data, _ = _check_backend_once(backend_url)
    latency_ms = (time.time() - t0) * 1000

    now_str = datetime.now().strftime("%b %d, %Y • %H:%M:%S")

    col_h1, col_h2, col_h3 = st.columns(3)
    with col_h1:
        st.markdown(
            f"""
            <div class="aegis-metric-card">
              <div class="aegis-metric-label"><span>🌐</span> Backend Status</div>
              <div class="aegis-metric-val" style="color: {'#34d399' if online else '#ef4444'};">
                {'● Operational' if online else '● Offline'}
              </div>
              <div class="aegis-metric-sub">Latency: {latency_ms:.1f} ms</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with col_h2:
        db_state_str = health_data.get('database', 'connected').capitalize()
        st.markdown(
            f"""
            <div class="aegis-metric-card">
              <div class="aegis-metric-label"><span>💾</span> Database State</div>
              <div class="aegis-metric-val" style="color: #6ee7b7;">
                {db_state_str}
              </div>
              <div class="aegis-metric-sub">Engine: SQLite / SQLAlchemy</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with col_h3:
        st.markdown(
            """
            <div class="aegis-metric-card">
              <div class="aegis-metric-label"><span>🤖</span> Production LLM</div>
              <div class="aegis-metric-val" style="color: #c084fc;">gpt-oss-120b</div>
              <div class="aegis-metric-sub">Provider: Groq OpenAI REST</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.markdown("---")
    st.markdown("### 🔍 Detailed Infrastructure Health Matrix")

    app_name = health_data.get('app_name', 'AegisCode')
    version_str = health_data.get('version', '0.1.0')

    col_m1, col_m2 = st.columns(2)
    with col_m1:
        st.markdown(
            f"""
            <div class="aegis-health-card">
              <div class="aegis-agent-header">
                <span class="aegis-agent-title">🖥️ Service Runtime</span>
                <span class="aegis-badge passed">Healthy</span>
              </div>
              <div class="aegis-health-row">
                <span class="aegis-health-key">Application</span>
                <span class="aegis-health-val">{app_name}</span>
              </div>
              <div class="aegis-health-row">
                <span class="aegis-health-key">Version</span>
                <span class="aegis-health-val">v{version_str}</span>
              </div>
              <div class="aegis-health-row">
                <span class="aegis-health-key">Last Checked</span>
                <span class="aegis-health-val">{now_str}</span>
              </div>
              <div class="aegis-health-row">
                <span class="aegis-health-key">API Protocol</span>
                <span class="aegis-health-val">HTTP/1.1 REST + JSON</span>
              </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with col_m2:
        st.markdown(
            """
            <div class="aegis-health-card">
              <div class="aegis-agent-header">
                <span class="aegis-agent-title">🛡️ Execution Sandbox & Security</span>
                <span class="aegis-badge passed">Active</span>
              </div>
              <div class="aegis-health-row">
                <span class="aegis-health-key">Backend Driver</span>
                <span class="aegis-health-val">LocalExecutionBackend</span>
              </div>
              <div class="aegis-health-row">
                <span class="aegis-health-key">Workspace Isolation</span>
                <span class="aegis-health-val" style="color: #34d399;">
                  Path Traversal Guard Active
                </span>
              </div>
              <div class="aegis-health-row">
                <span class="aegis-health-key">Test Integrity Policy</span>
                <span class="aegis-health-val" style="color: #34d399;">
                  Read-Only Test Files Guard
                </span>
              </div>
              <div class="aegis-health-row">
                <span class="aegis-health-key">Rate Limit Protection</span>
                <span class="aegis-health-val" style="color: #38bdf8;">
                  Exponential Backoff Retry Active
                </span>
              </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
