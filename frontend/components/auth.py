"""
Authentication & Authorization View Component for AegisCode.
Provides Sign In and Sign Up tabs with real-time validation and automatic session persistence.
"""

from __future__ import annotations

import streamlit as st

try:
    from frontend.utils.api_client import api_login, api_register
except ImportError:
    from utils.api_client import api_login, api_register


def render_auth(api_url: str) -> None:
    """Render the central SaaS authentication portal."""
    st.markdown(
        """
        <div style="text-align: center; max-width: 480px; margin: 40px auto 20px auto;">
          <div style="font-size: 2.5rem; margin-bottom: 8px;">🛡️</div>
          <h1 style="font-size: 1.85rem; font-weight: 800; color: var(--text-primary);
          letter-spacing: -0.03em; margin: 0;">
            AegisCode
          </h1>
          <div style="font-size: 0.76rem; font-weight: 700; color: #6366f1;
          letter-spacing: 0.08em; text-transform: uppercase; margin-top: 4px;">
            AUTONOMOUS SOFTWARE ENGINEERING
          </div>
          <p style="font-size: 0.88rem; color: var(--text-secondary); margin-top: 10px;">
            Sign in to access your autonomous repair consoles and telemetry.
          </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    col_center1, col_center2, col_center3 = st.columns([1, 2, 1])
    with col_center2:
        tab_signin, tab_signup = st.tabs(["Sign In", "Create Account"])

        # ── 1. Sign In Tab ───────────────────────────────────────────────────
        with tab_signin:
            with st.form("form_signin"):
                signin_email = st.text_input(
                    "Email Address",
                    placeholder="engineer@kiranverse.tech",
                    key="signin_email",
                ).strip()
                signin_pwd = st.text_input(
                    "Password",
                    type="password",
                    placeholder="••••••••",
                    key="signin_pwd",
                )
                submit_signin = st.form_submit_button(
                    "Sign In to AegisCode",
                    use_container_width=True,
                    type="primary",
                )

            if submit_signin:
                if not signin_email or not signin_pwd:
                    st.error("Please provide both email and password.")
                else:
                    success, res = api_login(api_url, signin_email, signin_pwd)
                    if success and isinstance(res, dict):
                        st.session_state["auth_token"] = res["access_token"]
                        st.session_state["current_user"] = res.get("user", {})
                        st.session_state["nav_view"] = "◉ Overview"
                        st.session_state["app_navigation_radio"] = "◉ Overview"
                        st.rerun()
                    else:
                        err_msg = str(res) if res else "Invalid email or password."
                        st.error(f"Sign in failed: {err_msg}")

        # ── 2. Sign Up Tab ───────────────────────────────────────────────────
        with tab_signup:
            with st.form("form_signup"):
                signup_name = st.text_input(
                    "Full Name",
                    placeholder="Ada Lovelace",
                    key="signup_name",
                ).strip()
                signup_email = st.text_input(
                    "Work Email",
                    placeholder="ada@kiranverse.tech",
                    key="signup_email",
                ).strip()
                signup_pwd = st.text_input(
                    "Password",
                    type="password",
                    placeholder="Min. 8 characters with letters & numbers",
                    key="signup_pwd",
                )
                signup_confirm = st.text_input(
                    "Confirm Password",
                    type="password",
                    placeholder="Re-enter password",
                    key="signup_confirm",
                )
                submit_signup = st.form_submit_button(
                    "Create Account & Start",
                    use_container_width=True,
                    type="primary",
                )

            if submit_signup:
                if not signup_name or not signup_email or not signup_pwd or not signup_confirm:
                    st.error("All fields are required.")
                elif signup_pwd != signup_confirm:
                    st.error("Passwords do not match.")
                elif len(signup_pwd) < 8:
                    st.error("Password must be at least 8 characters long.")
                else:
                    success, res = api_register(
                        api_url,
                        signup_name,
                        signup_email,
                        signup_pwd,
                        signup_confirm,
                    )
                    if success and isinstance(res, dict):
                        st.session_state["auth_token"] = res["access_token"]
                        st.session_state["current_user"] = res.get("user", {})
                        st.session_state["nav_view"] = "◉ Overview"
                        st.session_state["app_navigation_radio"] = "◉ Overview"
                        st.rerun()
                    else:
                        err_msg = str(res) if res else "Registration failed."
                        st.error(f"Registration failed: {err_msg}")
