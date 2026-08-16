"""
Global Footer Component for AegisCode.
Enterprise SaaS footer displaying platform identity, support channel, and copyright.
"""

from __future__ import annotations

import streamlit as st


def render_footer() -> None:
    """Render the global enterprise SaaS footer."""
    st.markdown("<div style='height: 48px;'></div>", unsafe_allow_html=True)
    st.markdown(
        """
        <footer class="aegis-global-footer">
          <div class="aegis-footer-inner">
            <div class="aegis-footer-brand">
              <span class="aegis-footer-logo">🛡️ AegisCode</span>
              <span class="aegis-footer-tagline">Autonomous Software Engineering</span>
            </div>
            <div class="aegis-footer-meta">
              <span class="aegis-footer-support">
                Support: <a href="mailto:admin@kiranverse.tech"
                class="aegis-footer-link">admin@kiranverse.tech</a>
              </span>
              <span class="aegis-footer-divider">•</span>
              <span class="aegis-footer-copy">© 2026 Kiranverse. All rights reserved.</span>
            </div>
          </div>
        </footer>
        """,
        unsafe_allow_html=True,
    )
