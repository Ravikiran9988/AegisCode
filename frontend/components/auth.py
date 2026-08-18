"""
Authentication & Authorization View Component for AegisCode.
Compact, modern SaaS authentication interface for Sign In and Create Account.
"""

from __future__ import annotations

import json
import re

import streamlit as st
from streamlit_cookies_controller import CookieController

try:
    from frontend.utils.api_client import api_login, api_register
except ImportError:
    from utils.api_client import api_login, api_register


def _persist_session(response: dict) -> None:
    """Persist the authenticated session for seven days."""
    st.session_state["auth_token"] = response["access_token"]
    st.session_state["current_user"] = response.get("user", {})
    # Clear guest session mode when authenticating real user account
    st.session_state["guest_mode"] = False
    st.session_state["guest_name"] = ""
    st.session_state["auth_flow_step"] = "public_dashboard"

    try:
        cookies = CookieController()
        cookies.set(
            "aegis_auth_token",
            response["access_token"],
            max_age=60 * 60 * 24 * 7,
        )
        cookies.set(
            "aegis_user",
            json.dumps(response.get("user", {})),
            max_age=60 * 60 * 24 * 7,
        )
    except Exception:
        pass


def render_auth_tabs(
    api_url: str,
    active_tab: str = "signin",
    target_nav: str = "🚀 New Repair",
) -> None:
    """Render individual signin or signup form tab with custom target navigation."""
    if active_tab == "signin":
        with st.form("form_signin", clear_on_submit=False):
            signin_email = st.text_input(
                "Email",
                placeholder="lily@gmail.com",
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
                    _persist_session(res)
                    st.session_state["nav_view"] = target_nav
                    st.success("Authenticated successfully! Redirecting...")
                    st.rerun()
                else:
                    err_msg = str(res) if res else "Invalid email or password."
                    st.error(f"Sign in failed: {err_msg}")

    elif active_tab == "signup":
        with st.form("form_signup", clear_on_submit=False):
            signup_name = st.text_input(
                "Full Name",
                placeholder="e.g. Ada Lovelace",
                key="signup_name",
                help="Your name displayed across the AegisCode workspace.",
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
            if not all((signup_name, signup_email, signup_pwd, signup_confirm)):
                st.error("All fields are required. Please complete the form.")
            elif len(signup_name) < 2:
                st.error("Full name must be at least 2 characters long.")
            elif "@" not in signup_email or "." not in signup_email:
                st.error("Please enter a valid email address.")
            elif signup_pwd != signup_confirm:
                st.error("Passwords do not match.")
            elif len(signup_pwd) < 8:
                st.error("Password must be at least 8 characters long.")
            elif not re.search(r"[A-Za-z]", signup_pwd) or not re.search(
                r"[0-9]", signup_pwd
            ):
                st.error("Password must contain both letters and numbers.")
            else:
                with st.spinner("Creating your account..."):
                    success, res = api_register(
                        api_url,
                        signup_name,
                        signup_email,
                        signup_pwd,
                        signup_confirm,
                    )
                if success and isinstance(res, dict):
                    _persist_session(res)
                    st.session_state["nav_view"] = target_nav
                    st.success("Account created successfully! Redirecting...")
                    st.rerun()
                else:
                    err_msg = str(res) if res else "Registration failed."
                    st.error(f"Registration failed: {err_msg}")


def render_auth(api_url: str, target_nav: str = "◉ Overview") -> None:
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

        with tab_signin:
            render_auth_tabs(api_url=api_url, active_tab="signin", target_nav=target_nav)

        with tab_signup:
            render_auth_tabs(api_url=api_url, active_tab="signup", target_nav=target_nav)

        st.markdown(
            """
            <div class="aegis-auth-footer">
              <div>Support: <a href="mailto:admin@kiranverse.tech">admin@kiranverse.tech</a></div>
              <div>© 2026 Kiranverse. All rights reserved.</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
