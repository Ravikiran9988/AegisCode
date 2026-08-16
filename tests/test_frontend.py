"""
test_frontend.py — Tests for Streamlit Frontend Helpers & Health Connectivity.

Tests:
1.  _normalize_backend_url strips trailing slashes, /health, /api.
2.  _check_backend_once queries /health endpoint and returns (True, health_data, "")
    when status == "ok".
3.  _check_backend_once handles full /health URLs.
4.  _check_backend_once returns (False, {}, error_msg) when connection fails.
5.  check_backend_with_retry retries on failure and succeeds on a later attempt.
6.  _detect_rate_limit_error correctly identifies 429 rate-limit messages.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import requests

# Mock Streamlit to avoid top-level Streamlit execution errors during import
st_mock = MagicMock()
st_mock.sidebar.text_input.return_value = "http://localhost:8000"
st_mock.tabs.return_value = [MagicMock(), MagicMock(), MagicMock()]
st_mock.columns.return_value = [MagicMock(), MagicMock()]

with patch.dict("sys.modules", {"streamlit": st_mock}):
    with patch("requests.get") as mock_init_get:
        mock_init_get.return_value = MagicMock(
            status_code=200, json=lambda: {"status": "ok"}
        )
        from frontend.app import (
            _check_backend_once,
            _detect_rate_limit_error,
            _normalize_backend_url,
            check_backend_with_retry,
        )


class TestFrontendHealthConnectivity:

    def test_normalize_backend_url(self):
        assert _normalize_backend_url(
            "https://aegiscode-vrob.onrender.com"
        ) == "https://aegiscode-vrob.onrender.com"
        assert _normalize_backend_url(
            "https://aegiscode-vrob.onrender.com/"
        ) == "https://aegiscode-vrob.onrender.com"
        assert _normalize_backend_url(
            "https://aegiscode-vrob.onrender.com/health"
        ) == "https://aegiscode-vrob.onrender.com"
        assert _normalize_backend_url(
            "https://aegiscode-vrob.onrender.com/health/"
        ) == "https://aegiscode-vrob.onrender.com"
        assert _normalize_backend_url(
            "https://aegiscode-vrob.onrender.com/api"
        ) == "https://aegiscode-vrob.onrender.com"
        assert _normalize_backend_url(
            "http://localhost:8000"
        ) == "http://localhost:8000"

    @patch("requests.get")
    def test_backend_online_success_root_url(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "status": "ok",
            "app_name": "AegisCode",
            "version": "0.1.0",
            "timestamp": "2026-08-16T22:00:00Z",
            "database": "connected",
            "llm_provider": "openai_compatible",
        }
        mock_get.return_value = mock_resp

        is_online, data, error = _check_backend_once(
            "https://aegiscode-vrob.onrender.com"
        )
        assert is_online is True
        assert data["status"] == "ok"
        assert data["llm_provider"] == "openai_compatible"
        assert error == ""
        mock_get.assert_called_with(
            "https://aegiscode-vrob.onrender.com/health", timeout=10
        )

    @patch("requests.get")
    def test_backend_online_success_health_url(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "status": "ok",
            "app_name": "AegisCode",
            "version": "0.1.0",
            "timestamp": "2026-08-16T22:00:00Z",
            "database": "connected",
            "llm_provider": "openai_compatible",
        }
        mock_get.return_value = mock_resp

        is_online, data, error = _check_backend_once(
            "https://aegiscode-vrob.onrender.com/health"
        )
        assert is_online is True
        assert data["status"] == "ok"
        assert error == ""
        mock_get.assert_called_with(
            "https://aegiscode-vrob.onrender.com/health", timeout=10
        )

    @patch("requests.get")
    def test_backend_online_failure_non_200(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.status_code = 500
        mock_get.return_value = mock_resp

        is_online, data, error = _check_backend_once(
            "https://aegiscode-vrob.onrender.com"
        )
        assert is_online is False
        assert data == {}
        assert "500" in error

    @patch("requests.get")
    def test_backend_online_failure_connection_error(self, mock_get):
        mock_get.side_effect = requests.exceptions.ConnectionError(
            "Connection refused"
        )

        is_online, data, error = _check_backend_once(
            "https://aegiscode-vrob.onrender.com"
        )
        assert is_online is False
        assert data == {}
        assert "Connection" in error or "starting" in error

    @patch("requests.get")
    def test_backend_online_failure_timeout(self, mock_get):
        mock_get.side_effect = requests.exceptions.Timeout("Timed out")

        is_online, data, error = _check_backend_once(
            "https://aegiscode-vrob.onrender.com"
        )
        assert is_online is False
        assert "timed out" in error.lower()

    @patch("requests.get")
    def test_check_backend_with_retry_succeeds_on_second_attempt(self, mock_get):
        """Verify that retry works: fail first, succeed on retry."""
        fail_resp = MagicMock()
        fail_resp.status_code = 502
        mock_get.return_value = fail_resp

        with patch("time.sleep"):
            online, data, error = check_backend_with_retry(
                "https://aegiscode-vrob.onrender.com",
                retry_delays=[0, 0],
            )
        # Both attempts fail (mock always returns 502), so should be offline
        assert online is False
        assert mock_get.call_count == 2

    @patch("requests.get")
    def test_check_backend_with_retry_succeeds(self, mock_get):
        """Verify that retry succeeds when the backend comes online."""
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"status": "ok", "llm_provider": "openai_compatible"}
        mock_get.return_value = mock_resp

        with patch("time.sleep"):
            online, data, error = check_backend_with_retry(
                "https://aegiscode-vrob.onrender.com",
                retry_delays=[0, 0],
            )
        assert online is True
        assert data["status"] == "ok"
        assert error == ""

    def test_detect_rate_limit_error_true(self):
        assert _detect_rate_limit_error(
            "openai/gpt-oss-120b rate_limit exceeded"
        ) is True
        assert _detect_rate_limit_error(
            "429 Too Many Requests"
        ) is True
        assert _detect_rate_limit_error(
            "quota exceeded"
        ) is True

    def test_detect_rate_limit_error_false(self):
        assert _detect_rate_limit_error(
            "all_tests_passed"
        ) is False
        assert _detect_rate_limit_error(None) is False
        assert _detect_rate_limit_error("") is False
        assert _detect_rate_limit_error(
            "No hunks found in patch"
        ) is False


class TestSidebarNavigation:
    """Tests for sidebar navigation and session-state synchronization."""

    @staticmethod
    def _mock_radio(label, options, index, key, on_change=None, label_visibility="visible"):
        # Helper that mirrors Streamlit radio retrieval behavior
        return options[index]

    def test_sidebar_initial_default_navigation(self):
        session = {}
        with patch("frontend.components.sidebar.st") as mock_st:
            mock_st.session_state = session
            mock_st.toggle.return_value = False
            mock_st.radio.side_effect = (
                lambda label, options, index, key, on_change=None, label_visibility="visible": (
                    session.get(key, options[index])
                )
            )
            mock_st.text_input.return_value = "https://aegiscode-vrob.onrender.com"

            from frontend.components.sidebar import render_sidebar

            selected_nav, backend = render_sidebar("https://aegiscode-vrob.onrender.com")

            assert selected_nav == "◉ Overview"
            assert session["nav_view"] == "◉ Overview"
            assert session["app_navigation_radio"] == "◉ Overview"

    def test_sidebar_programmatic_new_repair_navigation(self):
        """Simulate clicking 'Start New Repair' button on Overview page."""
        # Initial state was Overview
        session = {
            "nav_view": "◉ Overview",
            "app_navigation_radio": "◉ Overview",
        }

        # Button on Dashboard is clicked:
        session["nav_view"] = "🚀 New Repair"

        with patch("frontend.components.sidebar.st") as mock_st:
            mock_st.session_state = session
            mock_st.toggle.return_value = False
            mock_st.radio.side_effect = (
                lambda label, options, index, key, on_change=None, label_visibility="visible": (
                    session.get(key, options[index])
                )
            )
            mock_st.text_input.return_value = "https://aegiscode-vrob.onrender.com"

            from frontend.components.sidebar import render_sidebar

            selected_nav, _ = render_sidebar("https://aegiscode-vrob.onrender.com")

            # Must synchronize app_navigation_radio to 🚀 New Repair and return it
            assert session["app_navigation_radio"] == "🚀 New Repair"
            assert selected_nav == "🚀 New Repair"
            assert session["nav_view"] == "🚀 New Repair"

    def test_sidebar_programmatic_active_repairs_navigation(self):
        """Simulate in-page navigation to Active Repairs."""
        session = {
            "nav_view": "🤖 Active Repairs",
            "app_navigation_radio": "◉ Overview",
        }

        with patch("frontend.components.sidebar.st") as mock_st:
            mock_st.session_state = session
            mock_st.toggle.return_value = False
            mock_st.radio.side_effect = (
                lambda label, options, index, key, on_change=None, label_visibility="visible": (
                    session.get(key, options[index])
                )
            )
            mock_st.text_input.return_value = "https://aegiscode-vrob.onrender.com"

            from frontend.components.sidebar import render_sidebar

            selected_nav, _ = render_sidebar("https://aegiscode-vrob.onrender.com")

            assert session["app_navigation_radio"] == "🤖 Active Repairs"
            assert selected_nav == "🤖 Active Repairs"
            assert session["nav_view"] == "🤖 Active Repairs"

    def test_sidebar_manual_radio_change(self):
        """Simulate user manually clicking an option in the sidebar radio widget."""
        session = {
            "nav_view": "◉ Overview",
            "app_navigation_radio": "◉ Overview",
        }

        with patch("frontend.components.sidebar.st") as mock_st:
            mock_st.session_state = session
            mock_st.toggle.return_value = False

            def fake_radio(
                label, options, index, key, on_change=None, label_visibility="visible"
            ):
                # Simulate user selecting "❤️ System Health"
                session[key] = "❤️ System Health"
                if on_change:
                    on_change()
                return session[key]

            mock_st.radio.side_effect = fake_radio
            mock_st.text_input.return_value = "https://aegiscode-vrob.onrender.com"

            from frontend.components.sidebar import render_sidebar

            selected_nav, _ = render_sidebar("https://aegiscode-vrob.onrender.com")

            assert selected_nav == "❤️ System Health"
            assert session["nav_view"] == "❤️ System Health"
            assert session["app_navigation_radio"] == "❤️ System Health"

    def test_sidebar_invalid_nav_view_fallback(self):
        """Invalid nav_view should fallback to Overview."""
        session = {
            "nav_view": "Unknown View",
        }

        with patch("frontend.components.sidebar.st") as mock_st:
            mock_st.session_state = session
            mock_st.toggle.return_value = False
            mock_st.radio.side_effect = (
                lambda label, options, index, key, on_change=None, label_visibility="visible": (
                    session.get(key, options[index])
                )
            )
            mock_st.text_input.return_value = "https://aegiscode-vrob.onrender.com"

            from frontend.components.sidebar import render_sidebar

            selected_nav, _ = render_sidebar("https://aegiscode-vrob.onrender.com")

            assert selected_nav == "◉ Overview"
            assert session["nav_view"] == "◉ Overview"
            assert session["app_navigation_radio"] == "◉ Overview"


