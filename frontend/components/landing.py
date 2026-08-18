"""
Public Landing Page & Unauthenticated Auth Flow Components for AegisCode.

Provides:
- Public AegisCode landing page explaining features and multi-agent workflow
- Clean auth choice modal ("Start with AegisCode": Sign In / Create Account / Continue as Guest)
- Guest name prompt ("What should we call you?")
"""

from __future__ import annotations

import streamlit as st

try:
    from frontend.components.auth import render_auth_tabs
except ImportError:
    from components.auth import render_auth_tabs


def render_public_landing() -> None:
    """Render the high-converting, professional SaaS public landing page for AegisCode."""
    st.markdown(
        """
        <style>
        .aegis-hero {
          text-align: center;
          padding: 38px 20px 28px 20px;
          max-width: 900px;
          margin: 0 auto;
        }

        .aegis-hero-badge {
          display: inline-flex;
          align-items: center;
          gap: 8px;
          background: rgba(99, 102, 241, 0.12);
          border: 1px solid rgba(99, 102, 241, 0.3);
          padding: 6px 16px;
          border-radius: 9999px;
          font-size: 0.82rem;
          font-weight: 650;
          color: var(--brand-primary);
          margin-bottom: 20px;
        }

        .aegis-hero-title {
          font-size: 2.85rem;
          font-weight: 850;
          letter-spacing: -0.04em;
          line-height: 1.15;
          margin-bottom: 16px;
          color: var(--text-primary) !important;
        }

        .aegis-hero-subtitle {
          font-size: 1.12rem;
          line-height: 1.6;
          color: var(--text-secondary);
          max-width: 720px;
          margin: 0 auto 28px auto;
        }

        .aegis-features-grid {
          display: grid;
          grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
          gap: 18px;
          margin: 36px 0;
        }

        .aegis-feature-card {
          background: linear-gradient(145deg, var(--bg-panel), var(--bg-panel-elevated));
          border: 1px solid var(--border-subtle);
          border-radius: var(--radius-lg);
          padding: 22px;
          transition: transform 0.15s ease, border-color 0.15s ease;
        }

        .aegis-feature-card:hover {
          transform: translateY(-3px);
          border-color: var(--border-hover);
        }

        .aegis-feature-icon {
          font-size: 1.8rem;
          margin-bottom: 12px;
          display: inline-block;
        }

        .aegis-feature-title {
          font-size: 1.05rem;
          font-weight: 750;
          color: var(--text-primary);
          margin-bottom: 6px;
        }

        .aegis-feature-desc {
          font-size: 0.86rem;
          color: var(--text-secondary);
          line-height: 1.5;
        }

        .aegis-workflow-section {
          background: var(--bg-panel);
          border: 1px solid var(--border-subtle);
          border-radius: var(--radius-lg);
          padding: 30px 24px;
          margin: 36px 0;
        }

        .aegis-workflow-header {
          text-align: center;
          margin-bottom: 26px;
        }

        .aegis-workflow-header h2 {
          font-size: 1.6rem;
          font-weight: 800;
          color: var(--text-primary);
          margin-bottom: 6px;
        }

        .aegis-workflow-header p {
          font-size: 0.9rem;
          color: var(--text-secondary);
        }

        .aegis-workflow-steps {
          display: grid;
          grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
          gap: 16px;
        }

        .aegis-workflow-step {
          background: var(--bg-panel-elevated);
          border: 1px solid var(--border-subtle);
          border-radius: var(--radius-md);
          padding: 18px 16px;
          text-align: center;
          position: relative;
        }

        .aegis-step-num {
          display: inline-flex;
          align-items: center;
          justify-content: center;
          width: 28px;
          height: 28px;
          border-radius: 50%;
          background: var(--brand-primary);
          color: #fff;
          font-size: 0.78rem;
          font-weight: 700;
          margin-bottom: 10px;
        }

        .aegis-step-title {
          font-weight: 700;
          font-size: 0.95rem;
          color: var(--text-primary);
          margin-bottom: 4px;
        }

        .aegis-step-desc {
          font-size: 0.8rem;
          color: var(--text-secondary);
          line-height: 1.4;
        }

        .aegis-download-hero-text h3 {
          color: #ffffff !important;
        }

        .aegis-download-hero-text p {
          color: #c7d2fe !important;
        }

        @media (max-width: 768px) {
          .aegis-hero {
            padding: 28px 12px 22px 12px;
          }

          .aegis-hero-badge {
            font-size: 0.74rem;
            padding: 5px 12px;
          }

          .aegis-hero-title {
            font-size: 2rem;
            line-height: 1.18;
          }

          .aegis-hero-subtitle {
            font-size: 0.95rem;
            line-height: 1.5;
            margin-bottom: 22px;
          }

          .aegis-workflow-section {
            padding: 22px 14px;
            margin: 28px 0;
          }

          .aegis-workflow-steps,
          .aegis-features-grid {
            grid-template-columns: 1fr;
            gap: 12px;
          }

          .aegis-workflow-step,
          .aegis-feature-card {
            padding: 18px;
          }

          .aegis-download-hero {
            padding: 20px 16px;
          }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    # Hero Header
    st.markdown(
        """
        <div class="aegis-hero">
          <div class="aegis-hero-badge">
            <span>🛡️</span> AegisCode &bull; Autonomous Multi-Agent Engineering
          </div>
          <h1 class="aegis-hero-title">
            Autonomous Self-Healing Software Platform
          </h1>
          <p class="aegis-hero-subtitle">
            Upload buggy Python codebases, let specialized AI agents diagnose failing test suites,
            synthesize clean code patches, verify via Pytest, and deliver production-ready diffs automatically.
          </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # Hero CTA Buttons
    col_c1, col_c2, col_c3 = st.columns([1, 1.2, 1])
    with col_c2:
        btn_start = st.button(
            "🚀 Start Repair Now",
            key="hero_start_repair_btn",
            use_container_width=True,
            type="primary",
        )
        if btn_start:
            st.session_state["auth_flow_step"] = "auth_choice"
            st.rerun()

        st.markdown(
            "<div style='text-align: center; margin-top: 8px; font-size: 0.8rem; color: var(--text-muted);'>"
            "Instant guest access &bull; No signup required"
            "</div>",
            unsafe_allow_html=True,
        )

    st.markdown("<div style='height: 24px;'></div>", unsafe_allow_html=True)

    # Multi-Agent Workflow Pipeline Section
    st.markdown(
        """
        <div class="aegis-workflow-section">
          <div class="aegis-workflow-header">
            <h2>Autonomous Repair Pipeline</h2>
            <p>Our four-stage agentic workflow powered by LangGraph & Groq open-source LLMs</p>
          </div>
          <div class="aegis-workflow-steps">
            <div class="aegis-workflow-step">
              <div class="aegis-step-num">1</div>
              <div class="aegis-step-title">🏛️ Architect Agent</div>
              <div class="aegis-step-desc">
                Analyzes repository context & Pytest failure tracebacks to pinpoint bug root cause.
              </div>
            </div>
            <div class="aegis-workflow-step">
              <div class="aegis-step-num">2</div>
              <div class="aegis-step-title">💻 Coder Agent</div>
              <div class="aegis-step-desc">
                Synthesizes minimal, safe code patches adhering to repository coding patterns.
              </div>
            </div>
            <div class="aegis-workflow-step">
              <div class="aegis-step-num">3</div>
              <div class="aegis-step-title">🧪 Pytest Execution</div>
              <div class="aegis-step-desc">
                Executes automated test suites in isolated sandboxed execution workspaces.
              </div>
            </div>
            <div class="aegis-workflow-step">
              <div class="aegis-step-num">4</div>
              <div class="aegis-step-title">⚖️ Reviewer Agent</div>
              <div class="aegis-step-desc">
                Evaluates patch quality, verifies zero regressions, and approves patch commit.
              </div>
            </div>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # Key Features Grid
    st.markdown(
        """
        <div style="text-align: center; margin: 32px 0 16px 0;">
          <h2 style="font-size: 1.5rem; font-weight: 800; color: var(--text-primary);">
            Built for Modern Engineering Teams
          </h2>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown(
        """
        <div class="aegis-features-grid">
          <div class="aegis-feature-card">
            <div class="aegis-feature-icon">🤖</div>
            <div class="aegis-feature-title">Autonomous Repair</div>
            <div class="aegis-feature-desc">
              End-to-end bug detection and resolution without requiring manual intervention.
            </div>
          </div>
          <div class="aegis-feature-card">
            <div class="aegis-feature-icon">🏛️</div>
            <div class="aegis-feature-title">Multi-Agent Workflow</div>
            <div class="aegis-feature-desc">
              Specialized Architect, Coder, and Reviewer agents collaborating via LangGraph stateful graph.
            </div>
          </div>
          <div class="aegis-feature-card">
            <div class="aegis-feature-icon">🧪</div>
            <div class="aegis-feature-title">Pytest Verification</div>
            <div class="aegis-feature-desc">
              Authoritative test run validation ensuring generated patches pass 100% of test cases.
            </div>
          </div>
          <div class="aegis-feature-card">
            <div class="aegis-feature-icon">🔀</div>
            <div class="aegis-feature-title">Synthesized Code Diffs</div>
            <div class="aegis-feature-desc">
              Interactive GitHub-style diff viewer highlighting unified file modifications and line changes.
            </div>
          </div>
          <div class="aegis-feature-card">
            <div class="aegis-feature-icon">📊</div>
            <div class="aegis-feature-title">Agent Observability</div>
            <div class="aegis-feature-desc">
              Real-time telemetry, agent reasoning logs, step execution trees, and iteration tracking.
            </div>
          </div>
          <div class="aegis-feature-card">
            <div class="aegis-feature-icon">🛡️</div>
            <div class="aegis-feature-title">Security Controls</div>
            <div class="aegis-feature-desc">
              Zip Slip path traversal prevention, sandboxed execution, and read-only test suite integrity guards.
            </div>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # Bottom Call To Action Banner
    st.markdown(
        """
        <div class="aegis-download-hero" style="margin-top: 32px; text-align: center;">
          <div class="aegis-download-hero-text" style="width: 100%;">
            <h3>Ready to auto-heal your codebase?</h3>
            <p>Upload a Python project ZIP and watch AegisCode diagnose and repair bugs in real time.</p>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    col_b1, col_b2, col_b3 = st.columns([1, 1.2, 1])
    with col_b2:
        if st.button("🚀 Start Repair", key="landing_bottom_cta", use_container_width=True, type="primary"):
            st.session_state["auth_flow_step"] = "auth_choice"
            st.rerun()


def render_auth_choice(api_url: str) -> None:
    """Render clean authentication choice card ('Start with AegisCode')."""
    st.markdown(
        """
        <div style="max-width: 480px; margin: 30px auto 0 auto; text-align: center;">
          <div style="font-size: 2.2rem; margin-bottom: 8px;">🛡️</div>
          <h2 style="font-size: 1.65rem; font-weight: 800; color: var(--text-primary); margin-bottom: 6px;">
            Start with AegisCode
          </h2>
          <p style="font-size: 0.88rem; color: var(--text-secondary); margin-bottom: 20px;">
            Sign in, create an account, or continue as a guest to begin your repair.
          </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    _, col_center, _ = st.columns([1, 1.3, 1])

    with col_center:
        tab_signin, tab_signup, tab_guest = st.tabs(
            ["Sign In", "Create Account", "Continue as Guest"]
        )

        with tab_signin:
            render_auth_tabs(api_url=api_url, active_tab="signin", target_nav="🚀 New Repair")

        with tab_signup:
            render_auth_tabs(api_url=api_url, active_tab="signup", target_nav="🚀 New Repair")

        with tab_guest:
            st.markdown(
                """
                <div style="padding: 16px 8px 12px 8px; text-align: center;">
                  <div style="font-size: 1.1rem; font-weight: 700; color: var(--text-primary); margin-bottom: 6px;">
                    ⚡ Instant Guest Access
                  </div>
                  <div style="font-size: 0.84rem; color: var(--text-secondary); margin-bottom: 18px; line-height: 1.45;">
                    No email or password needed. Try out full repair features immediately during your session.
                  </div>
                </div>
                """,
                unsafe_allow_html=True,
            )
            if st.button(
                "Continue as Guest →",
                key="btn_auth_choice_guest",
                use_container_width=True,
                type="primary",
            ):
                st.session_state["auth_flow_step"] = "guest_name_input"
                st.rerun()

        st.markdown("<div style='height: 16px;'></div>", unsafe_allow_html=True)
        if st.button("← Back to Public Dashboard", key="btn_back_to_dashboard", use_container_width=True):
            st.session_state["auth_flow_step"] = "public_dashboard"
            st.rerun()


def render_guest_name_input() -> None:
    """Render single prompt asking: 'What should we call you?'."""
    st.markdown(
        """
        <div style="max-width: 440px; margin: 40px auto 0 auto; text-align: center;">
          <div style="font-size: 2.2rem; margin-bottom: 8px;">👋</div>
          <h2 style="font-size: 1.65rem; font-weight: 800; color: var(--text-primary); margin-bottom: 6px;">
            What should we call you?
          </h2>
          <p style="font-size: 0.88rem; color: var(--text-secondary); margin-bottom: 22px;">
            Enter your preferred name to personalize your guest repair session.
          </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    _, col_center, _ = st.columns([1, 1.25, 1])

    with col_center:
        with st.form("guest_name_form", clear_on_submit=False):
            g_name = st.text_input(
                "Name",
                placeholder="e.g. Ravi",
                key="guest_name_field",
                help="Stored only in your current browser session.",
            ).strip()

            submit_guest = st.form_submit_button(
                "Continue as Guest",
                use_container_width=True,
                type="primary",
            )

        if submit_guest:
            if not g_name:
                st.error("Please enter your name to continue.")
            else:
                st.session_state["guest_mode"] = True
                st.session_state["guest_name"] = g_name
                st.session_state["nav_view"] = "🚀 New Repair"
                st.session_state["auth_flow_step"] = "public_dashboard"
                st.rerun()

        st.markdown("<div style='height: 12px;'></div>", unsafe_allow_html=True)
        if st.button("← Back", key="btn_back_to_auth_choice", use_container_width=True):
            st.session_state["auth_flow_step"] = "auth_choice"
            st.rerun()
