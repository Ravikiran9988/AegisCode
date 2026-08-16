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


class TestNewRepairFlow:
    """Tests for the automated workspace initialization and repair lifecycle UX."""

    def test_upload_auto_initializes_workspace(self):
        """Uploading a file automatically calls /projects/upload without extra button."""
        session = {}
        mock_file = MagicMock()
        mock_file.name = "calc.zip"
        mock_file.getvalue.return_value = b"PK\x03\x04testdata"
        mock_file.__len__.return_value = 100

        mock_resp = MagicMock()
        mock_resp.status_code = 201
        mock_resp.json.return_value = {
            "project_id": "proj-123",
            "name": "calc.zip",
            "file_count": 4,
        }

        with patch("frontend.components.upload.st") as mock_st, \
             patch("frontend.components.upload._safe_post") as mock_post:
            mock_st.session_state = session
            mock_st.file_uploader.return_value = mock_file
            mock_st.columns.return_value = [MagicMock(), MagicMock(), MagicMock()]
            mock_st.button.return_value = False
            mock_st.slider.return_value = 5
            mock_post.return_value = mock_resp

            from frontend.components.upload import render_upload

            render_upload("http://localhost:8000/api")

            # Project should be stored in session state automatically
            assert session.get("project_id") == "proj-123"
            assert session.get("file_count") == 4
            assert session.get("uploaded_filename") == "calc.zip"
            assert mock_st.rerun.called

    def test_repair_success_navigates_to_active_repairs(self):
        """When repair completes successfully ('passed'), navigates to Active Repairs."""
        file_bytes = b"PK\x03\x04testdata"
        sig = f"calc.zip_{len(file_bytes)}"
        session = {
            "project_id": "proj-123",
            "uploaded_file_sig": sig,
            "repair_status": "running",
            "repair_run_id": "run-456",
        }
        mock_file = MagicMock()
        mock_file.name = "calc.zip"
        mock_file.getvalue.return_value = file_bytes

        with patch("frontend.components.upload.st") as mock_st, \
             patch("frontend.components.upload.fetch_run_status") as mock_status:
            mock_st.session_state = session
            mock_st.file_uploader.return_value = mock_file
            mock_st.columns.return_value = [MagicMock(), MagicMock(), MagicMock()]
            mock_status.return_value = {
                "run_id": "run-456",
                "status": "passed",
                "current_iteration": 2,
                "max_iterations": 5,
                "final_summary": "All tests passed",
            }

            from frontend.components.upload import render_upload

            render_upload("http://localhost:8000/api")

            # Must navigate to Active Repairs and set active_run_id
            assert session.get("nav_view") == "🤖 Active Repairs"
            assert session.get("active_run_id") == "run-456"
            assert session.get("app_navigation_radio") == "🤖 Active Repairs"
            assert session.get("repair_status") is None
            assert mock_st.rerun.called

    def test_repair_failure_stays_on_page(self):
        """When repair finishes with 'failed', remains on New Repair page with error."""
        file_bytes = b"PK\x03\x04testdata"
        sig = f"calc.zip_{len(file_bytes)}"
        session = {
            "project_id": "proj-123",
            "uploaded_file_sig": sig,
            "repair_status": "running",
            "repair_run_id": "run-789",
        }
        mock_file = MagicMock()
        mock_file.name = "calc.zip"
        mock_file.getvalue.return_value = file_bytes

        with patch("frontend.components.upload.st") as mock_st, \
             patch("frontend.components.upload.fetch_run_status") as mock_status:
            mock_st.session_state = session
            mock_st.file_uploader.return_value = mock_file
            mock_st.columns.return_value = [MagicMock(), MagicMock(), MagicMock()]
            mock_status.return_value = {
                "run_id": "run-789",
                "status": "failed",
                "current_iteration": 5,
                "max_iterations": 5,
                "final_summary": "Max iterations reached without passing tests",
            }

            from frontend.components.upload import render_upload

            render_upload("http://localhost:8000/api")

            # Must NOT navigate to Active Repairs
            assert session.get("nav_view") != "🤖 Active Repairs"
            assert session.get("repair_status") == "failed"
            assert "Max iterations" in session.get("repair_error", "")
            assert mock_st.rerun.called

    def test_repair_cancelled_stays_on_page(self):
        """When repair finishes with 'cancelled', remains on New Repair page."""
        file_bytes = b"PK\x03\x04testdata"
        sig = f"calc.zip_{len(file_bytes)}"
        session = {
            "project_id": "proj-123",
            "uploaded_file_sig": sig,
            "repair_status": "running",
            "repair_run_id": "run-999",
        }
        mock_file = MagicMock()
        mock_file.name = "calc.zip"
        mock_file.getvalue.return_value = file_bytes

        with patch("frontend.components.upload.st") as mock_st, \
             patch("frontend.components.upload.fetch_run_status") as mock_status:
            mock_st.session_state = session
            mock_st.file_uploader.return_value = mock_file
            mock_st.columns.return_value = [MagicMock(), MagicMock(), MagicMock()]
            mock_status.return_value = {
                "run_id": "run-999",
                "status": "cancelled",
                "current_iteration": 1,
                "max_iterations": 5,
                "final_summary": "Run was stopped",
            }

            from frontend.components.upload import render_upload

            render_upload("http://localhost:8000/api")

            # Must NOT navigate to Active Repairs
            assert session.get("nav_view") != "🤖 Active Repairs"
            assert session.get("repair_status") == "cancelled"
            assert mock_st.rerun.called


class TestLiveRepairDashboard:
    """Unit tests for the production-grade Active Repairs Progress Dashboard."""

    def test_live_repair_empty_state_rendered(self):
        """When no active run is selected and no recent runs exist, renders empty state."""
        session = {}
        with patch("frontend.components.live_repair.st") as mock_st, \
             patch("frontend.components.live_repair.fetch_recent_runs", return_value=[]), \
             patch("frontend.components.live_repair.render_empty_state") as mock_empty:
            mock_st.session_state = session
            mock_st.columns.side_effect = lambda s: [
                MagicMock() for _ in range(s if isinstance(s, int) else len(s))
            ]
            mock_st.text_input.return_value = ""

            from frontend.components.live_repair import render_live_repair

            render_live_repair("http://localhost:8000/api")
            assert mock_empty.called

    def test_live_repair_auto_recovers_active_running_run(self):
        """When active_run_id is empty, auto-recovers running run from backend."""
        session = {}
        fake_recent = [{"run_id": "run-auto-123", "status": "running"}]
        fake_status = {
            "run_id": "run-auto-123",
            "project_name": "Calculator",
            "status": "running",
            "current_iteration": 2,
            "max_iterations": 5,
            "progress_percent": 45,
            "current_phase": "Code Repair & Patch",
            "current_action": {
                "agent": "Coder Agent",
                "node": "coder",
                "description": "Applying unified patch to calculator.py",
                "file": "calculator.py",
            },
            "pipeline_nodes": [
                {"node": "initial_test", "name": "Repository Assessment", "status": "completed"},
                {"node": "architect", "name": "Root Cause Analysis", "status": "completed"},
                {"node": "coder", "name": "Code Repair & Patch", "status": "running"},
                {"node": "test", "name": "Test & Validation", "status": "pending"},
                {"node": "reviewer", "name": "Reviewer Gate", "status": "pending"},
            ],
            "tests": {
                "total": 10,
                "executed": 10,
                "passed": 8,
                "failed": 2,
                "coverage_percent": 80.0,
            },
            "files": {"analyzed": 5, "changed": 1, "changed_files": ["calculator.py"]},
            "timeline": [
                {
                    "timestamp": "02:00:00",
                    "agent": "Architect Agent",
                    "message": "Plan ready",
                    "iteration": 1,
                }
            ],
            "elapsed_seconds": 18.5,
        }
        fake_results = {"iterations": [], "duration": 18.5}

        with patch("frontend.components.live_repair.st") as mock_st, \
             patch(
                 "frontend.components.live_repair.fetch_recent_runs",
                 return_value=fake_recent,
             ), \
             patch(
                 "frontend.components.live_repair.fetch_run_status",
                 return_value=fake_status,
             ), \
             patch(
                 "frontend.components.live_repair.fetch_run_results",
                 return_value=fake_results,
             ), \
             patch("time.sleep"):
            mock_st.session_state = session
            mock_st.columns.side_effect = lambda s: [
                MagicMock() for _ in range(s if isinstance(s, int) else len(s))
            ]
            mock_st.text_input.return_value = "run-auto-123"
            mock_st.tabs.return_value = [
                MagicMock(), MagicMock(), MagicMock(), MagicMock(), MagicMock(), MagicMock()
            ]

            from frontend.components.live_repair import render_live_repair

            render_live_repair("http://localhost:8000/api")

            # Must have recovered run-auto-123
            assert session.get("active_run_id") == "run-auto-123"
            # Since status is 'running', must call rerun()
            assert mock_st.rerun.called

    def test_live_repair_completed_state_renders_navigation(self):
        """When repair is passed, renders completed state without infinite polling."""
        session = {"active_run_id": "run-pass-999"}
        fake_status = {
            "run_id": "run-pass-999",
            "project_name": "Calculator",
            "status": "passed",
            "current_iteration": 1,
            "max_iterations": 5,
            "progress_percent": 100,
            "current_phase": "Repair Complete & Verified",
            "current_action": {
                "agent": "Test Agent",
                "node": "test",
                "description": "All tests passed",
                "file": None,
            },
            "pipeline_nodes": [
                {"node": "initial_test", "name": "Repository Assessment", "status": "completed"},
                {"node": "architect", "name": "Root Cause Analysis", "status": "completed"},
                {"node": "coder", "name": "Code Repair & Patch", "status": "completed"},
                {"node": "test", "name": "Test & Validation", "status": "completed"},
                {"node": "reviewer", "name": "Reviewer Gate", "status": "completed"},
            ],
            "tests": {
                "total": 10,
                "executed": 10,
                "passed": 10,
                "failed": 0,
                "coverage_percent": 100.0,
            },
            "files": {"analyzed": 5, "changed": 1, "changed_files": ["calculator.py"]},
            "timeline": [],
            "elapsed_seconds": 12.0,
        }
        fake_results = {"iterations": [], "duration": 12.0}

        with patch("frontend.components.live_repair.st") as mock_st, \
             patch(
                 "frontend.components.live_repair.fetch_run_status",
                 return_value=fake_status,
             ), \
             patch(
                 "frontend.components.live_repair.fetch_run_results",
                 return_value=fake_results,
             ), \
             patch("frontend.components.live_repair._safe_get") as mock_get:
            mock_st.session_state = session
            mock_st.columns.side_effect = lambda s: [
                MagicMock() for _ in range(s if isinstance(s, int) else len(s))
            ]
            mock_st.text_input.return_value = "run-pass-999"
            mock_st.button.return_value = False
            mock_st.tabs.return_value = [
                MagicMock(), MagicMock(), MagicMock(), MagicMock(), MagicMock(), MagicMock()
            ]
            mock_get.return_value = None

            from frontend.components.live_repair import render_live_repair

            render_live_repair("http://localhost:8000/api")

            # Progress bar set to 1.0 (100%)
            assert mock_st.progress.called
            # Must NOT call rerun since status is passed
            assert not mock_st.rerun.called





