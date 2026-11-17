"""
Active Repairs Page for AegisCode.
"""

from __future__ import annotations

from frontend.components.live_repair import render_live_repair


def render(api_url: str) -> None:
    """Render the active repairs console."""
    render_live_repair(api_url)
