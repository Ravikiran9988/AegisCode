from __future__ import annotations

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from backend.api.auth import get_optional_current_user
from backend.core.config import settings
from backend.execution.factory import (
    UnsafeLocalExecutionError,
    get_execution_backend,
)
from backend.execution.workspace import PathTraversalError, WorkspaceManager
from backend.main import create_app


def test_optional_auth_does_not_downgrade_invalid_bearer_token():
    with pytest.raises(HTTPException) as exc_info:
        get_optional_current_user("Bearer definitely-not-a-valid-token", db=None)

    assert exc_info.value.status_code == 401


def test_optional_auth_allows_requests_without_credentials():
    assert get_optional_current_user(None, db=None) is None


def test_guest_run_routes_require_a_session_id():
    client = TestClient(create_app())
    response = client.get("/api/runs/nonexistent/status")

    assert response.status_code == 401
    assert "guest session" in response.json()["detail"].lower()


def test_production_never_uses_the_local_uploaded_code_runner(monkeypatch):
    monkeypatch.setenv("ENV", "production")
    monkeypatch.delenv("ENVIRONMENT", raising=False)
    monkeypatch.setattr(settings, "execution_backend", "local")
    monkeypatch.setattr(settings, "use_docker_sandbox", False)

    with pytest.raises(UnsafeLocalExecutionError, match="disabled"):
        get_execution_backend()


def test_local_execution_remains_available_outside_production(monkeypatch):
    monkeypatch.setenv("ENV", "test")
    monkeypatch.setenv("ENVIRONMENT", "test")
    monkeypatch.setattr(settings, "execution_backend", "local")
    monkeypatch.setattr(settings, "use_docker_sandbox", False)

    assert get_execution_backend().name == "local"


def test_agent_paths_cannot_escape_the_extracted_project(tmp_path):
    workspace = WorkspaceManager.create(base_dir=tmp_path)
    try:
        safe_file = workspace.safe_path("src/module.py")
        assert safe_file == workspace.get_project_path() / "src" / "module.py"

        with pytest.raises(PathTraversalError):
            workspace.safe_path("../outside.py")
    finally:
        workspace.cleanup()
