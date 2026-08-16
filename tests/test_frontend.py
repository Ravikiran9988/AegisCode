"""
test_frontend.py — Tests for Streamlit Frontend Helpers & Health Connectivity.

Tests:
1.  _normalize_backend_url strips trailing slashes, /health, /api.
2.  _backend_online queries /health endpoint and returns (True, health_data) when status == "ok".
3.  _backend_online handles full /health URLs (e.g., https://aegiscode-vrob.onrender.com/health).
4.  _backend_online returns (False, {}) when status is not "ok" or connection fails.
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
        mock_init_get.return_value = MagicMock(status_code=200, json=lambda: {"status": "ok"})
        from frontend.app import _backend_online, _normalize_backend_url


class TestFrontendHealthConnectivity:

    def test_normalize_backend_url(self):
        assert _normalize_backend_url("https://aegiscode-vrob.onrender.com") == "https://aegiscode-vrob.onrender.com"
        assert _normalize_backend_url("https://aegiscode-vrob.onrender.com/") == "https://aegiscode-vrob.onrender.com"
        assert _normalize_backend_url("https://aegiscode-vrob.onrender.com/health") == "https://aegiscode-vrob.onrender.com"
        assert _normalize_backend_url("https://aegiscode-vrob.onrender.com/health/") == "https://aegiscode-vrob.onrender.com"
        assert _normalize_backend_url("https://aegiscode-vrob.onrender.com/api") == "https://aegiscode-vrob.onrender.com"
        assert _normalize_backend_url("http://localhost:8000") == "http://localhost:8000"

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

        is_online, data = _backend_online("https://aegiscode-vrob.onrender.com")
        assert is_online is True
        assert data["status"] == "ok"
        assert data["llm_provider"] == "openai_compatible"
        mock_get.assert_called_with(
            "https://aegiscode-vrob.onrender.com/health", timeout=5
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

        is_online, data = _backend_online("https://aegiscode-vrob.onrender.com/health")
        assert is_online is True
        assert data["status"] == "ok"
        mock_get.assert_called_with(
            "https://aegiscode-vrob.onrender.com/health", timeout=5
        )

    @patch("requests.get")
    def test_backend_online_failure_non_200(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.status_code = 500
        mock_get.return_value = mock_resp

        is_online, data = _backend_online("https://aegiscode-vrob.onrender.com")
        assert is_online is False
        assert data == {}

    @patch("requests.get")
    def test_backend_online_failure_connection_error(self, mock_get):
        mock_get.side_effect = requests.exceptions.ConnectionError("Connection refused")

        is_online, data = _backend_online("https://aegiscode-vrob.onrender.com")
        assert is_online is False
        assert data == {}
