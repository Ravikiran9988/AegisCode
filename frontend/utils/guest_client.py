"""Client helpers for persistent guest identities."""

from __future__ import annotations

import uuid

import requests
import streamlit as st


def persist_guest_identity(api_url: str, name: str) -> dict | None:
    """Create or refresh the current browser guest identity in the backend DB."""
    clean_name = name.strip()
    if not clean_name:
        return None

    session_id = st.session_state.get("guest_session_id")
    if not session_id:
        session_id = str(uuid.uuid4())
        st.session_state["guest_session_id"] = session_id

    try:
        response = requests.post(
            f"{api_url}/guests",
            json={"name": clean_name, "session_id": session_id},
            timeout=10,
        )
        if response.status_code == 200:
            return response.json()
    except requests.RequestException:
        pass
    return None
