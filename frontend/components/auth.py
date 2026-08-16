"""
Authentication & Authorization View Component for AegisCode.
Enterprise developer-platform SaaS design system for Sign In and Create Account.
"""

from __future__ import annotations

import re

import streamlit as st

try:
    from frontend.utils.api_client import api_login, api_register
except ImportError:
    from utils.api_client import api_login, api_register


def render_auth(api_url: str) -> None:
    """Render the modern SaaS authentication portal for AegisCode."""
    st.markdown(
        """
        <div class="aegis-auth-wrapper">
          <div class="aegis-auth-header">
            <div class="aegis-auth-shield">🛡️</div>
            <h1 class="aegis-auth-brand-name">AegisCode</h1>
            <div class="aegis-auth-brand-sub">AUTONOMOUS SOFTWARE ENGINEERING</div>
            <div class="aegis-auth-tagline">Build with confidence.</div>
            <p class="aegis-auth-subtagline">AI-powered autonomous software engineering.</p>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    _, col_center, _ = st.columns([1, 1.4, 1])

    with col_center:
        tab_signin, tab_signup = st.tabs(["Sign In", "Create Account"])

        # ── 1. Sign In Tab ───────────────────────────────────────────────────
        with tab_signin:
            with st.form("form_signin", clear_on_submit=False):
                signin_email = st.text_input(
                    "Email",
                    placeholder="engineer@kiranverse.tech",
                    key="signin_email",
                    help="Enter your registered account email.",
                ).strip()

                show_pwd_signin = st.checkbox("Show password", key="chk_show_pwd_signin")
                signin_pwd = st.text_input(
                    "Password",
                    type="default" if show_pwd_signin else "password",
                    placeholder="••••••••",
                    key="signin_pwd",
                )

                submit_signin = st.form_submit_button(
                    "Sign In",
                    use_container_width=True,
                    type="primary",
                )

            if submit_signin:
                if not signin_email or not signin_pwd:
                    st.error("Please provide both email and password.")
                else:
                    with st.spinner("Authenticating with AegisCode..."):
                        success, res = api_login(api_url, signin_email, signin_pwd)
                    if success and isinstance(res, dict):
                        st.session_state["auth_token"] = res["access_token"]
                        st.session_state["current_user"] = res.get("user", {})
                        st.session_state["nav_view"] = "◉ Overview"
                        st.session_state["app_navigation_radio"] = "◉ Overview"
                        st.success("Authenticated successfully! Redirecting...")
                        st.rerun()
                    else:
                        err_msg = str(res) if res else "Invalid email or password."
                        st.error(f"Sign in failed: {err_msg}")

        # ── 2. Create Account Tab ────────────────────────────────────────────
        with tab_signup:
            with st.form("form_signup", clear_on_submit=False):
                signup_name = st.text_input(
                    "Full Name",
                    placeholder="Ada Lovelace",
                    key="signup_name",
                    help="Your full human-readable name.",
                ).strip()

                signup_email = st.text_input(
                    "Email",
                    placeholder="ada@kiranverse.tech",
                    key="signup_email",
                    help="Unique email address for your account.",
                ).strip()

                show_pwd_signup = st.checkbox("Show passwords", key="chk_show_pwd_signup")
                pwd_type = "default" if show_pwd_signup else "password"

                signup_pwd = st.text_input(
                    "Password",
                    type=pwd_type,
                    placeholder="Min. 8 characters with letters & numbers",
                    key="signup_pwd",
                )

                signup_confirm = st.text_input(
                    "Confirm Password",
                    type=pwd_type,
                    placeholder="Re-enter your password",
                    key="signup_confirm",
                )

                submit_signup = st.form_submit_button(
                    "Create Account",
                    use_container_width=True,
                    type="primary",
                )

            if submit_signup:
                if not signup_name or not signup_email or not signup_pwd or not signup_confirm:
                    st.error("All fields are required. Please fill in all fields.")
                elif len(signup_name) < 2:
                    st.error("Full Name must be at least 2 characters long.")
                elif "@" not in signup_email or "." not in signup_email:
                    st.error("Please enter a valid email address.")
                elif signup_pwd != signup_confirm:
                    st.error("Passwords do not match.")
                elif len(signup_pwd) < 8:
                    st.error("Password must be at least 8 characters long.")
                elif not re.search(r"[A-Za-z]", signup_pwd) or not re.search(r"[0-9]", signup_pwd):
                    st.error("Password must contain both letters and numbers.")
                else:
                    with st.spinner("Creating your AegisCode account..."):
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
                        st.success("Account created successfully! Redirecting to Control Center...")
                        st.rerun()
                    else:
                        err_msg = str(res) if res else "Registration failed."
                        st.error(f"Registration failed: {err_msg}")

        st.markdown(
            """
            <div class="aegis-auth-trust-footer">
              🛡️ Protected by AegisCode Cryptographic Auth & RBAC Isolation
            </div>
            """,
            unsafe_allow_html=True,
        )
