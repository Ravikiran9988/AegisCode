"""
Tests for Fixsembly V2 Server-Sent Events (SSE) streaming endpoint.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from backend.database.models import Project, Run
from backend.main import app


@pytest.fixture
def test_client():
    return TestClient(app)


def test_stream_nonexistent_run(test_client):
    """Streaming a non-existent run returns an SSE error event."""
    resp = test_client.get("/api/runs/non-existent-run-id/stream")
    assert resp.status_code == 200
    assert "text/event-stream" in resp.headers["content-type"]
    text = resp.text
    assert "event: error" in text
    assert "not found" in text.lower()


def test_stream_existing_run(test_client):
    """Streaming an existing run streams status and completion events."""
    from backend.database.session import SessionLocal

    db = SessionLocal()
    try:
        project = Project(
            name="TestStreamProject",
            original_filename="test.zip",
            workspace_path="/tmp/test",
            file_count=1,
            size_bytes=100,
        )
        db.add(project)
        db.flush()

        run = Run(
            project_id=project.id,
            status="passed",
            max_iterations=5,
            current_iteration=1,
            final_summary="All tests passed successfully",
        )
        db.add(run)
        db.commit()
        run_id = run.id
    finally:
        db.close()

    resp = test_client.get(f"/api/runs/{run_id}/stream")
    assert resp.status_code == 200
    assert "text/event-stream" in resp.headers["content-type"]
    content = resp.text
    assert "event: status" in content or "event: complete" in content
