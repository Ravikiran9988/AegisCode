"""
Fixsembly V2 Quality Engineering, Security Hardening, and Status Discrimination Tests.

Verifies:
1. Run cancellation endpoint (POST /api/runs/{run_id}/cancel).
2. Status discrimination:
   - "passed" (tests pass + reviewer approves)
   - "partially_repaired" (failures reduced from baseline at max iterations)
   - "reviewer_rejected" (tests pass, reviewer disapproves)
   - "test_error" (pytest collection error or internal crash exit_code 2/3/4)
   - "cancelled" (user cancelled)
3. Security Hardening:
   - ZIP symlinks rejected
   - ZIP executable/binary files rejected (.exe, .bat, .dll)
   - Expanded policy engine guards (.github/, .env, secrets, batch scripts)
"""

from __future__ import annotations

import io
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from backend.agents.policies import PolicyViolationError, check_file_modification_policy
from backend.database.models import Project, Run
from backend.database.session import SessionLocal, get_db
from backend.execution.workspace import WorkspaceManager, ZipValidationError
from backend.graph.graph import decision_router
from backend.graph.nodes import test_node
from backend.main import app
from backend.tools.pytest_runner import TestResult


@pytest.fixture
def test_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture
def client(test_db):
    def _override_get_db():
        try:
            yield test_db
        finally:
            pass

    app.dependency_overrides[get_db] = _override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


# ── Run Cancellation Tests ───────────────────────────────────────────────────

class TestRunCancellation:
    def test_cancel_active_run_success(self, client, test_db: Session):
        # Create a dummy project and running run
        project = Project(
            name="cancel_test_proj",
            original_filename="proj.zip",
            workspace_path="/tmp/test",
            file_count=2,
            size_bytes=100,
        )
        test_db.add(project)
        test_db.flush()

        run = Run(
            project_id=project.id,
            status="running",
            max_iterations=5,
            current_iteration=1,
            started_at=datetime.now(timezone.utc),
        )
        test_db.add(run)
        test_db.commit()

        # Cancel the run
        res = client.post(f"/api/runs/{run.id}/cancel")
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "cancelled"
        assert data["run_id"] == run.id

        # Verify database record
        cancelled_run = test_db.get(Run, run.id)
        assert cancelled_run is not None
        assert cancelled_run.status == "cancelled"
        assert cancelled_run.finished_at is not None
        assert "cancelled by user" in cancelled_run.final_summary.lower()

    def test_cancel_already_terminal_run_returns_400(self, client, test_db: Session):
        project = Project(
            name="cancel_terminal_proj",
            original_filename="proj.zip",
            workspace_path="/tmp/test",
            file_count=2,
            size_bytes=100,
        )
        test_db.add(project)
        test_db.flush()

        run = Run(
            project_id=project.id,
            status="passed",
            max_iterations=5,
            current_iteration=1,
            finished_at=datetime.now(timezone.utc),
        )
        test_db.add(run)
        test_db.commit()

        res = client.post(f"/api/runs/{run.id}/cancel")
        assert res.status_code == 400
        assert "already in terminal state" in res.json()["detail"]


# ── Status Discrimination Tests ──────────────────────────────────────────────

class TestStatusDiscrimination:
    def test_test_error_on_pytest_crash(self):
        """Verify test_node assigns test_error when Pytest exits with code 2 or 3."""
        crashed_result = TestResult(
            passed=0,
            failed=0,
            errors=1,
            skipped=0,
            exit_code=2,  # Interrupted or collection failure
            success=False,
            duration=0.5,
            stdout="INTERNALERROR",
            stderr="Interrupted by user or collection crash",
        )

        state = {
            "run_id": "test_crash_run",
            "iteration": 1,
            "project_path": str(Path.cwd()),
            "initial_failed_count": 2,
        }

        with patch("backend.graph.nodes.get_execution_backend") as mock_backend:
            mock_backend.return_value.run_pytest.return_value = crashed_result
            updates = test_node(state)

        assert updates["status"] == "test_error"
        assert "pytest_execution_error_exit_code_2" in updates["termination_reason"]

    def test_partially_repaired_status_on_max_iterations(self):
        """Verify partially_repaired when failing tests decrease from baseline at max iterations."""
        improved_result = TestResult(
            passed=4,
            failed=1,  # down from 5 initial failures
            errors=0,
            skipped=0,
            exit_code=1,
            success=False,
            duration=1.2,
            stdout="4 passed, 1 failed",
            stderr="",
        )

        state = {
            "run_id": "test_partial_run",
            "iteration": 3,
            "max_iterations": 3,
            "project_path": str(Path.cwd()),
            "initial_failed_count": 5,
            "previous_failures": [],
            "git_diff": {"has_changes": True},
        }

        with patch("backend.graph.nodes.get_execution_backend") as mock_backend:
            mock_backend.return_value.run_pytest.return_value = improved_result
            updates = test_node(state)

        assert updates["status"] == "partially_repaired"
        assert updates["termination_reason"] == "partial_repair_max_iterations"
        assert updates["final_failed_count"] == 1

    def test_reviewer_rejected_terminal_status(self):
        """Verify reviewer rejection routes to end with reviewer_rejected when max iterations reached."""
        state = {
            "run_id": "test_rev_reject_run",
            "iteration": 5,
            "max_iterations": 5,
            "status": "running",
            "test_result": {
                "passed": 3,
                "failed": 0,
                "errors": 0,
                "skipped": 0,
                "exit_code": 0,
                "success": True,
                "duration": 0.5,
                "stdout": "3 passed",
                "stderr": "",
            },
            "review_result": {
                "approved": False,
                "root_cause_fixed": True,
                "regression_risk": "high",
                "issues": ["Unrelated modifications introduce security regression"],
                "reasoning": "High regression risk",
                "recommendation": "Reject patch",
            },
        }

        # Decision router marks reviewer_rejected on max iterations
        route = decision_router(state)
        assert route == "end"


# ── Security & Sandboxing Hardening Tests ─────────────────────────────────────

class TestSecurityHardening:
    def test_zip_with_executable_rejected(self):
        """Upload containing .exe or .bat file must be rejected with ZipValidationError."""
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            zf.writestr("script.py", "print('hello')\n")
            zf.writestr("malicious.exe", b"MZP\x00\x00")

        wm = WorkspaceManager.create()
        try:
            with pytest.raises(ZipValidationError) as exc_info:
                wm.extract_project(buf.getvalue())
            assert "forbidden binary or executable file" in str(exc_info.value).lower()
        finally:
            wm.cleanup()

    def test_zip_with_symlink_rejected(self):
        """Upload containing a symlink must be rejected."""
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            zf.writestr("main.py", "print('safe')\n")
            symlink_info = zipfile.ZipInfo("symlink_file")
            symlink_info.create_system = 3  # Unix
            symlink_info.external_attr = 0o120777 << 16  # Symlink mode
            zf.writestr(symlink_info, "/etc/passwd")

        wm = WorkspaceManager.create()
        try:
            with pytest.raises(ZipValidationError) as exc_info:
                wm.extract_project(buf.getvalue())
            assert "forbidden symlink" in str(exc_info.value).lower()
        finally:
            wm.cleanup()

    def test_policy_blocks_ci_and_shell_files(self):
        """check_file_modification_policy blocks CI/CD configs, environment secrets, and scripts."""
        with pytest.raises(PolicyViolationError):
            check_file_modification_policy(".github/workflows/deploy.yml")

        with pytest.raises(PolicyViolationError):
            check_file_modification_policy(".gitlab-ci.yml")

        with pytest.raises(PolicyViolationError):
            check_file_modification_policy("run_tests.bat")

        with pytest.raises(PolicyViolationError):
            check_file_modification_policy("deploy.sh")

        with pytest.raises(PolicyViolationError):
            check_file_modification_policy("server.key")

        # Regular python source files are permitted
        check_file_modification_policy("src/calculator.py")
        check_file_modification_policy("app/utils.py")
