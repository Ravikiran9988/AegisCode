"""
Authentication & Authorization View Component for AegisCode.
Compact, modern SaaS authentication interface for Sign In and Create Account.
"""

from __future__ import annotations

import re

import streamlit as st

try:
    from frontend.utils.api_client import api_login, api_register
except ImportError:
    from utils.api_client import api_login, api_register


def render_auth(api_url: str) -> None:
    """Render the compact SaaS authentication portal for AegisCode."""
    st.markdown(
        """
        <div class="aegis-auth-wrapper">
          <div class="aegis-auth-header">
            <div class="aegis-auth-shield">🛡️</div>
            <h1 class="aegis-auth-brand-name">AegisCode</h1>
            <div class="aegis-auth-brand-sub">AI-powered autonomous software engineering.</div>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    _, col_center, _ = st.columns([1, 1.25, 1])

    with col_center:
        tab_signin, tab_signup = st.tabs(["Sign In", "Create Account"])

        # ── 1. Sign In Tab ───────────────────────────────────────────────────
        with tab_signin:
            with st.form("form_signin", clear_on_submit=False):
                signin_email = st.text_input(
                    "Email",
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
                        try:
                            from streamlit_cookies_controller import CookieController
                            import json
                            cookies = CookieController()
                            cookies.set("aegis_auth_token", res["access_token"], max_age=60*60*24*7)
                            cookies.set("aegis_user", json.dumps(res.get("user", {})), max_age=60*60*24*7)
                        except ImportError:
                            pass
                        st.session_state["nav_view"] = "◉ Overview"
                        st.success("Authenticated successfully! Redirecting...")
                        st.rerun()
                    else:
                        err_msg = str(res) if res else "Invalid email or password."
                        st.error(f"Sign in failed: {err_msg}")

        # ── 2. Create Account Tab ────────────────────────────────────────────
        with tab_signup:
            with st.form("form_signup", clear_on_submit=False):
                signup_nick = st.text_input(
                    "Nickname",
                    placeholder="e.g. ada",
                    key="signup_nick",
                    help="Your preferred display nickname (at least 2 characters).",
                ).strip()

                signup_email = st.text_input(
                    "Email",
                    placeholder="ada@kiranverse.tech",
                    key="signup_email",
                    help="Unique email address for your account.",
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
                    placeholder="Re-enter your password",
                    key="signup_confirm",
                )

                submit_signup = st.form_submit_button(
                    "Create Account",
                    use_container_width=True,
                    type="primary",
                )

            if submit_signup:
                if not signup_nick or not signup_email or not signup_pwd or not signup_confirm:
                    st.error("All fields are required. Please complete the form.")
                elif len(signup_nick) < 2:
                    st.error("Nickname must be at least 2 characters long.")
                elif "@" not in signup_email or "." not in signup_email:
                    st.error("Please enter a valid email address.")
                elif signup_pwd != signup_confirm:
                    st.error("Passwords do not match.")
                elif len(signup_pwd) < 8:
                    st.error("Password must be at least 8 characters long.")
                elif not re.search(r"[A-Za-z]", signup_pwd) or not re.search(r"[0-9]", signup_pwd):
                    st.error("Password must contain both letters and numbers.")
                else:
                    with st.spinner("Creating your account..."):
                        success, res = api_register(
                            api_url,
                            signup_nick,
                            signup_email,
                            signup_pwd,
                            signup_confirm,
                        )
                    if success and isinstance(res, dict):
                        st.session_state["auth_token"] = res["access_token"]
                        st.session_state["current_user"] = res.get("user", {})
                        try:
                            from streamlit_cookies_controller import CookieController
                            import json
                            cookies = CookieController()
                            cookies.set("aegis_auth_token", res["access_token"], max_age=60*60*24*7)
                            cookies.set("aegis_user", json.dumps(res.get("user", {})), max_age=60*60*24*7)
                        except ImportError:
                            pass
                        st.session_state["nav_view"] = "◉ Overview"
                        st.success("Account created successfully! Redirecting to Control Center...")
                        st.rerun()
                    else:
                        err_msg = str(res) if res else "Registration failed."
                        st.error(f"Registration failed: {err_msg}")

        # Compact Brand & Support Footer
        st.markdown(
            """
            <div class="aegis-auth-footer">
              <div>Support: <a href="mailto:admin@kiranverse.tech">admin@kiranverse.tech</a></div>
              <div>© 2026 Kiranverse. All rights reserved.</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
