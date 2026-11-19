"""
New Repair Page for AegisCode.
"""

from __future__ import annotations

from frontend.components.upload import render_upload_section


def render(api_url: str) -> None:
    """Render the new repair section."""
    render_upload_section(api_url)
