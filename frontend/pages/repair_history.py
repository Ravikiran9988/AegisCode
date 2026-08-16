"""
Repair History Page for AegisCode.
"""

from __future__ import annotations

from frontend.components.history import render_history


def render(api_url: str) -> None:
    """Render the repair history browser."""
    render_history(api_url=api_url)
