"""
Documentation & Architecture Reference Component for AegisCode.
"""

from __future__ import annotations

import streamlit as st


def render_docs() -> None:
    """Render the technical architecture, agent role guide, and API reference."""
    st.markdown(
        """
        <div class="aegis-page-header">
          <h1 class="aegis-page-title">AegisCode Platform Architecture & Reference</h1>
          <p class="aegis-page-desc">
            Autonomous multi-agent self-healing state machine, security boundaries,
            and API specifications.
          </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown("### 🛡️ LangGraph Self-Healing State Machine")
    st.code(
        """
        START
          │
          ▼
        Initial Test Node ──(All Passed)──► [already_passing] ──► END (Success)
          │
          ▼ (Tests Failed)
        Architect Node (Analyzes logs, hypothesizes root cause, designs plan)
          │
          ▼
        Coder Node (Synthesizes AST / patch modification to source files)
          │
          ▼
        Test Node (Executes authoritative Pytest subprocess in isolated workspace)
          │
          ▼
        Reviewer Node (Independent audit: checks regressions & approves/rejects)
          │
          ▼
        Decision Router
          ├── All Passed & Approved  ──► [passed]  ──► END (Success + ZIP Download)
          ├── Max Iterations Reached ──► [failed]  ──► END (Max Iterations)
          ├── Repeated Failure       ──► [stalled] ──► END (Loop Stalled)
          └── Retry Needed           ──► ARCHITECT NODE (Iteration N+1)
        """,
        language="text",
    )

    st.markdown("---")
    st.markdown("### 🤖 Agent Roles & Responsibilities")

    col_a1, col_a2 = st.columns(2)
    with col_a1:
        st.markdown(
            """
            <div class="aegis-agent-card">
              <div class="aegis-agent-header">
                <span class="aegis-agent-title">🏛️ Architect Agent</span>
                <span class="aegis-badge passed">Diagnosis</span>
              </div>
              <p style="font-size: 0.85rem; color: #cbd5e1; margin: 0;">
                Analyzes failure tracebacks and syntax errors. Identifies defect root causes,
                selects relevant files, and creates targeted repair strategies.
              </p>
            </div>
            """,
            unsafe_allow_html=True,
        )

        st.markdown(
            """
            <div class="aegis-agent-card">
              <div class="aegis-agent-header">
                <span class="aegis-agent-title">🧪 Test Execution Node</span>
                <span class="aegis-badge passed">Authoritative</span>
              </div>
              <p style="font-size: 0.85rem; color: #cbd5e1; margin: 0;">
                Executes the actual pytest suite in a subshell inside the isolated sandbox.
                Test exit code 0 is an invariant requirement for resolution.
              </p>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with col_a2:
        st.markdown(
            """
            <div class="aegis-agent-card">
              <div class="aegis-agent-header">
                <span class="aegis-agent-title">💻 Coder Agent</span>
                <span class="aegis-badge running">Synthesis</span>
              </div>
              <p style="font-size: 0.85rem; color: #cbd5e1; margin: 0;">
                Translates Architect plans into unified patches or AST file replacements.
                Strictly barred from modifying test files or system paths.
              </p>
            </div>
            """,
            unsafe_allow_html=True,
        )

        st.markdown(
            """
            <div class="aegis-agent-card">
              <div class="aegis-agent-header">
                <span class="aegis-agent-title">🔍 Reviewer Agent</span>
                <span class="aegis-badge risk-low">Verification</span>
              </div>
              <p style="font-size: 0.85rem; color: #cbd5e1; margin: 0;">
                Performs independent verification of all modifications against the baseline.
                Rates regression risk (LOW, MEDIUM, HIGH) and approves/rejects the repair.
              </p>
            </div>
            """,
            unsafe_allow_html=True,
        )

    st.markdown("---")
    st.markdown("### 🔌 REST API Specification")
    st.markdown(
        """
        | Method | Endpoint | Description |
        | :--- | :--- | :--- |
        | `GET` | `/health` | Live service health & LLM model verification |
        | `POST` | `/api/projects/upload` | Upload & extract project ZIP into sandbox |
        | `POST` | `/api/runs` | Initialize a repair run and execute baseline test |
        | `POST` | `/api/runs/{run_id}/repair` | Launch background LangGraph autonomous repair |
        | `GET` | `/api/runs` | Query historical repair runs with status and metrics |
        | `GET` | `/api/runs/{run_id}/status` | Query live status, iteration progress, metrics |
        | `GET` | `/api/runs/{run_id}/results` | Query complete iteration telemetry & logs |
        | `GET` | `/api/runs/{run_id}/download` | Stream verified repaired project as ZIP archive |
        """
    )
