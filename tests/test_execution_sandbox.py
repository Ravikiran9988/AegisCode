"""
Regression test suite for AegisCode production execution & sandbox architecture.

Tests:
1. Local execution backend runs pytest properly.
2. Execution backend selection (get_execution_backend) reflects configuration.
3. LangGraph repair nodes use get_execution_backend() instead of direct bypasses.
4. Docker backend failure/unavailability raises DockerNotAvailable and NEVER falls back.
5. Runs API imports cleanly without NameError or circular dependency.
6. Guest run ownership and access permissions.
7. LLM provider kwargs resilience (ignoring reasoning_effort or extra parameters).
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException

from backend.core.config import settings
from backend.execution import (
    DockerExecutionBackend,
    DockerNotAvailable,
    ExecutionBackend,
    LocalExecutionBackend,
    get_execution_backend,
)
from backend.graph.nodes import initial_test_node as _initial_test_node
from backend.graph.nodes import test_node as _test_node
from backend.llm.mock import MockLLMProvider
from backend.llm.openai import OpenAICompatibleLLMProvider
from backend.tools.pytest_runner import TestResult


def test_runs_api_import_safety():
    """Verify backend.api.runs imports cleanly and router is defined before use."""
    from backend.api.runs import RunCreateRequest, RunResponse, router
    assert router is not None
    assert router.prefix == f"{settings.api_prefix}/runs"
    assert RunCreateRequest is not None
    assert RunResponse is not None


def test_get_execution_backend_local(monkeypatch):
    """Verify local backend selection."""
    monkeypatch.setattr(settings, "execution_backend", "local")
    monkeypatch.setattr(settings, "use_docker_sandbox", False)

    backend = get_execution_backend()
    assert isinstance(backend, LocalExecutionBackend)
    assert backend.name == "local"


def test_get_execution_backend_docker_unavailable(monkeypatch):
    """Verify Docker selection fails clearly if Docker daemon/CLI is missing."""
    monkeypatch.setattr(settings, "execution_backend", "docker")
    monkeypatch.setattr(settings, "use_docker_sandbox", True)

    with patch.object(
        DockerExecutionBackend,
        "_check_docker",
        side_effect=DockerNotAvailable("Docker missing"),
    ):
        with pytest.raises(DockerNotAvailable, match="Docker missing"):
            get_execution_backend()


def test_graph_nodes_use_configured_backend(tmp_path: Path):
    """Verify initial_test_node and test_node call get_execution_backend().run_pytest."""
    dummy_path = tmp_path / "dummy_proj"
    dummy_path.mkdir()

    mock_backend = MagicMock(spec=ExecutionBackend)
    mock_backend.run_pytest.return_value = TestResult(
        passed=1,
        failed=0,
        errors=0,
        skipped=0,
        exit_code=0,
        stdout="",
        stderr="",
        duration=0.1,
        success=True,
    )

    state = {
        "run_id": "test_run_123",
        "workspace_id": "ws_123",
        "project_path": str(dummy_path),
    }

    with patch("backend.graph.nodes.get_execution_backend", return_value=mock_backend) as mock_get:
        # Initial test node
        updates = _initial_test_node(state, db=None)
        mock_get.assert_called_once()
        mock_backend.run_pytest.assert_called_once_with(dummy_path)
        assert updates["status"] == "already_passing"

        # Test node
        mock_get.reset_mock()
        mock_backend.run_pytest.reset_mock()

        test_state = {
            "run_id": "test_run_123",
            "iteration": 1,
            "project_path": str(dummy_path),
        }
        updates_test = _test_node(test_state, db=None)
        mock_get.assert_called_once()
        mock_backend.run_pytest.assert_called_once_with(dummy_path)
        assert updates_test["final_failed_count"] == 0


def test_guest_run_access_control():
    """Verify guest and authenticated user ownership checks."""
    from backend.api.runs import _check_run_access
    from backend.database.models import Run, User

    user_a = User(id="user_a", email="a@example.com", hashed_password="pw", is_superuser=False)
    user_b = User(id="user_b", email="b@example.com", hashed_password="pw", is_superuser=False)
    admin = User(id="admin", email="admin@example.com", hashed_password="pw", is_superuser=True)

    user_a_run = Run(id="run_a", user_id="user_a", project_id="proj_1")
    guest_run = Run(id="run_guest", user_id=None, project_id="proj_2")

    # User A accessing own run -> OK
    _check_run_access(user_a_run, user_a)

    # User B accessing User A run -> Forbidden
    with pytest.raises(HTTPException) as exc_info:
        _check_run_access(user_a_run, user_b)
    assert exc_info.value.status_code == 403

    # Superuser accessing User A run -> OK
    _check_run_access(user_a_run, admin)

    # Guest user accessing guest run -> OK
    _check_run_access(guest_run, None)


def test_llm_provider_extra_kwargs_resilience():
    """Verify LLM providers handle unknown kwargs like reasoning_effort without crashing."""
    mock_provider = MockLLMProvider()
    res = mock_provider.generate("Hello", reasoning_effort="high", unexpected_arg=123)
    assert res == "Mock generated text response"

    from backend.agents.schemas import ArchitecturePlan
    plan = mock_provider.generate_structured(ArchitecturePlan, "Analyze", reasoning_effort="high")
    assert isinstance(plan, ArchitecturePlan)

    # Test OpenAICompatibleLLMProvider kwargs tolerance
    openai_provider = OpenAICompatibleLLMProvider(api_key="test_key")
    with patch.object(openai_provider, "_call_with_retry") as mock_call:
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"choices": [{"message": {"content": "ok"}}]}
        mock_call.return_value = mock_resp

        output = openai_provider.generate(
            "Test prompt",
            reasoning_effort="high",
            custom_option="val",
        )
        assert output == "ok"
