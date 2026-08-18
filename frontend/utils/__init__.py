"""
AegisCode Frontend Utilities Package.

Also persists a newly-created guest identity at the first Streamlit rerun after
Guest mode is enabled. This keeps guest persistence centralized without changing
the existing guest-entry UI flow.
"""

from __future__ import annotations

import os
import uuid

import requests
import streamlit as st


_original_rerun = st.rerun


def _persist_guest_before_rerun() -> None:
    """Persist a newly-entered guest name before Streamlit reruns the app."""
    if not st.session_state.get("guest_mode"):
        return
    if st.session_state.get("guest_db_id"):
        return

    name = str(st.session_state.get("guest_name", "")).strip()
    if not name:
        return

    session_id = st.session_state.get("guest_session_id")
    if not session_id:
        session_id = str(uuid.uuid4())
        st.session_state["guest_session_id"] = session_id

    backend_url = os.environ.get(
        "BACKEND_URL", "https://aegiscode-vrob.onrender.com"
    ).rstrip("/")
    try:
        response = requests.post(
            f"{backend_url}/api/guests",
            json={"name": name, "session_id": session_id},
            timeout=10,
        )
        if response.status_code == 200:
            data = response.json()
            st.session_state["guest_db_id"] = data.get("guest_id", "")
            st.session_state["guest_name"] = data.get("name", name)
    except requests.RequestException:
        # Guest functionality must remain available if the persistence service
        # is temporarily unavailable; the existing session-state identity remains usable.
        pass


def _guest_aware_rerun(*args, **kwargs):
    _persist_guest_before_rerun()
    return _original_rerun(*args, **kwargs)


st.rerun = _guest_aware_rerun
