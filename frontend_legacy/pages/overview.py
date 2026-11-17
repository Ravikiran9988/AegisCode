"""
Overview / Control Center Page for AegisCode.
"""

from __future__ import annotations

from frontend.components.dashboard import render_dashboard


def render(api_url: str, health_data: dict | None = None) -> None:
    """Render the main control center overview dashboard."""
    render_dashboard(api_url=api_url, health_data=health_data or {})
