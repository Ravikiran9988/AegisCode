"""
test_end_to_end_repair.py — Comprehensive end-to-end self-healing and data flow tests.

Tests:
1. test_already_healthy_project_workflow
2. test_broken_calculator_self_healing_workflow
3. test_patch_fallback_and_persistence
4. test_reviewer_rejection_prevents_false_success
5. test_download_endpoint_after_repair
6. test_repair_results_api_contains_full_agent_data
7. test_failed_run_retains_partial_iteration_details
8. test_api_response_contains_nested_conceptual_schema
9. test_persistence_survives_db_session_reopen
"""

from __future__ import annotations

import io
import zipfile
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.agents.schemas import ArchitecturePlan, CodeChange, ReviewResult
from backend.database.models import Base, Iteration, Project, Run
from backend.database.persistence import upsert_iteration
from backend.database.session import get_db
from backend.execution.workspace import WorkspaceManager
from backend.graph.graph import run_repair_workflow
from backend.llm.base import BaseLLMProvider
from backend.main import create_app
from backend.tools.git_tools import init_repo

# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def e2e_db():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    session_cls = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = session_cls()
    yield session
    session.close()
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def e2e_client(e2e_db):
    app = create_app()

    def override_get_db():
        try:
            yield e2e_db
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()


# ── Tests ─────────────────────────────────────────────────────────────────────

class TestEndToEndRepair:

    def test_already_healthy_project_workflow(self, e2e_db):
        """Verify that an already-passing project is marked healthy and approved in iteration 1."""
        wm = WorkspaceManager.create()
        try:
            pdir = wm.get_project_path()
            calc_file = pdir / "calculator.py"
            calc_file.write_text("def add(a, b):\n    return a + b\n", encoding="utf-8")

            test_file = pdir / "test_calculator.py"
            test_file.write_text(
                "from calculator import add\n\ndef test_add():\n    assert add(2, 3) == 5\n",
                encoding="utf-8",
            )

            init_repo(pdir)

            project = Project(
                id="proj-healthy-1",
                name="healthy_calc",
                original_filename="healthy.zip",
                workspace_path=str(wm.get_workspace_path()),
                file_count=2,
                size_bytes=100,
            )
            run = Run(
                id="run-healthy-1",
                project_id=project.id,
                status="running",
                max_iterations=5,
            )
            e2e_db.add(project)
            e2e_db.add(run)
            e2e_db.commit()

            mock_llm = MagicMock(spec=BaseLLMProvider)

            final_state = run_repair_workflow(
                run_id=run.id,
                workspace_id=wm.workspace_id,
                project_path=str(pdir),
                llm_provider=mock_llm,
                db=e2e_db,
                max_iterations=5,
            )

            assert final_state["status"] == "already_passing"
            assert final_state["termination_reason"] == "all_tests_passed"

            # Verify database persistence
            e2e_db.refresh(run)
            assert run.status == "already_passing"

            it = e2e_db.query(Iteration).filter(Iteration.run_id == run.id).first()
            assert it is not None
            assert it.approved is True
            assert it.tests_passed == 1
            assert it.tests_failed == 0
        finally:
            wm.cleanup()

    def test_broken_calculator_self_healing_workflow(self, e2e_db):
        """
        Verify end-to-end self-healing for deliberately broken calculator.py:
        4 failed tests -> Architect analyzes -> Coder applies fix -> Pytest -> Reviewer approves.
        """
        wm = WorkspaceManager.create()
        try:
            pdir = wm.get_project_path()
            calc_file = pdir / "calculator.py"
            calc_file.write_text("def add(a, b):\n    return a - b\n", encoding="utf-8")

            test_file = pdir / "test_calculator.py"
            test_file.write_text(
                "from calculator import add\n\n"
                "def test_add():\n    assert add(2, 3) == 5\n"
                "def test_add_zero():\n    assert add(10, 0) == 10\n"
                "def test_add_negative():\n    assert add(-2, -3) == -5\n"
                "def test_add_mixed():\n    assert add(-2, 3) == 1\n",
                encoding="utf-8",
            )

            init_repo(pdir)

            project = Project(
                id="proj-calc-1",
                name="broken_calc",
                original_filename="calc.zip",
                workspace_path=str(wm.get_workspace_path()),
                file_count=2,
                size_bytes=200,
            )
            run = Run(
                id="run-calc-1",
                project_id=project.id,
                status="running",
                max_iterations=5,
            )
            e2e_db.add(project)
            e2e_db.add(run)
            e2e_db.commit()

            # Mock LLM calls: Architect -> Coder -> Reviewer
            mock_llm = MagicMock(spec=BaseLLMProvider)

            def mock_generate_structured(schema, prompt, system_prompt=None):
                if schema == ArchitecturePlan:
                    return ArchitecturePlan(
                        summary="Fix subtraction operator in add() to addition",
                        project_type="library",
                        relevant_files=["calculator.py"],
                        suspected_issues=["add() uses subtraction instead of addition"],
                        test_strategy="Run pytest test_calculator.py",
                        confidence=0.98,
                    )
                elif schema == CodeChange:
                    return CodeChange(
                        file_path="calculator.py",
                        change_type="write",
                        explanation="Fixed add() function to return a + b",
                        root_cause="Operator bug in add()",
                        patch="def add(a, b):\n    return a + b\n",
                        confidence=0.99,
                    )
                elif schema == ReviewResult:
                    return ReviewResult(
                        approved=True,
                        root_cause_fixed=True,
                        regression_risk="low",
                        issues=[],
                        reasoning="All 4 tests pass with addition fix in calculator.py",
                        recommendation="Approve fix",
                        confidence=0.99,
                    )
                raise ValueError(f"Unexpected schema: {schema}")

            mock_llm.generate_structured.side_effect = mock_generate_structured

            final_state = run_repair_workflow(
                run_id=run.id,
                workspace_id=wm.workspace_id,
                project_path=str(pdir),
                llm_provider=mock_llm,
                db=e2e_db,
                max_iterations=5,
            )

            assert final_state["status"] == "passed"
            assert final_state["termination_reason"] == "all_tests_passed"

            # Check file was modified
            repaired_content = calc_file.read_text(encoding="utf-8")
            assert "return a + b" in repaired_content

            # Verify database persistence of all agent outputs
            e2e_db.refresh(run)
            assert run.status == "passed"

            it = e2e_db.query(Iteration).filter(Iteration.run_id == run.id).first()
            assert it is not None
            assert it.architecture_plan is not None
            assert "Fix subtraction operator" in it.architecture_plan["summary"]
            assert it.code_changes is not None
            assert it.code_changes[0]["file_path"] == "calculator.py"
            assert it.test_results is not None
            assert it.test_results["passed"] == 4
            assert it.test_results["failed"] == 0
            assert it.review_result is not None
            assert it.review_result["approved"] is True
            assert it.approved is True
        finally:
            wm.cleanup()

    def test_patch_fallback_and_persistence(self, e2e_db):
        """Verify when Coder returns change_type='patch' with full code, fallback applies fix."""
        wm = WorkspaceManager.create()
        try:
            pdir = wm.get_project_path()
            calc_file = pdir / "calculator.py"
            calc_file.write_text("def add(a, b):\n    return a - b\n", encoding="utf-8")

            test_file = pdir / "test_calculator.py"
            test_file.write_text(
                "from calculator import add\n\ndef test_add():\n    assert add(2, 3) == 5\n",
                encoding="utf-8",
            )

            init_repo(pdir)

            project = Project(
                id="proj-fallback-1",
                name="fallback_calc",
                original_filename="calc.zip",
                workspace_path=str(wm.get_workspace_path()),
                file_count=2,
                size_bytes=200,
            )
            run = Run(
                id="run-fallback-1",
                project_id=project.id,
                status="running",
                max_iterations=5,
            )
            e2e_db.add(project)
            e2e_db.add(run)
            e2e_db.commit()

            mock_llm = MagicMock(spec=BaseLLMProvider)

            def mock_generate_structured(schema, prompt, system_prompt=None):
                if schema == ArchitecturePlan:
                    return ArchitecturePlan(
                        summary="Fix calculator bug",
                        relevant_files=["calculator.py"],
                        test_strategy="Run pytest",
                    )
                elif schema == CodeChange:
                    return CodeChange(
                        file_path="calculator.py",
                        change_type="patch",
                        explanation="Full file replacement provided",
                        root_cause="Bug in add",
                        patch="def add(a, b):\n    return a + b\n",
                        confidence=0.95,
                    )
                elif schema == ReviewResult:
                    return ReviewResult(
                        approved=True,
                        root_cause_fixed=True,
                        regression_risk="low",
                        reasoning="Tests passed",
                        recommendation="Approve",
                    )
                raise ValueError(f"Unexpected schema: {schema}")

            mock_llm.generate_structured.side_effect = mock_generate_structured

            final_state = run_repair_workflow(
                run_id=run.id,
                workspace_id=wm.workspace_id,
                project_path=str(pdir),
                llm_provider=mock_llm,
                db=e2e_db,
                max_iterations=5,
            )

            assert final_state["status"] == "passed"
            repaired_content = calc_file.read_text(encoding="utf-8")
            assert "return a + b" in repaired_content
        finally:
            wm.cleanup()

    def test_reviewer_rejection_prevents_false_success(self, e2e_db):
        """Verify that if Reviewer rejects changes, the repair does not succeed."""
        wm = WorkspaceManager.create()
        try:
            pdir = wm.get_project_path()
            calc_file = pdir / "calculator.py"
            calc_file.write_text("def add(a, b):\n    return a - b\n", encoding="utf-8")

            test_file = pdir / "test_calculator.py"
            test_file.write_text(
                "from calculator import add\n\ndef test_add():\n    assert add(2, 3) == 5\n",
                encoding="utf-8",
            )

            init_repo(pdir)

            project = Project(
                id="proj-reject-1",
                name="reject_calc",
                original_filename="calc.zip",
                workspace_path=str(wm.get_workspace_path()),
                file_count=2,
                size_bytes=200,
            )
            run = Run(
                id="run-reject-1",
                project_id=project.id,
                status="running",
                max_iterations=1,
            )
            e2e_db.add(project)
            e2e_db.add(run)
            e2e_db.commit()

            mock_llm = MagicMock(spec=BaseLLMProvider)

            def mock_generate_structured(schema, prompt, system_prompt=None):
                if schema == ArchitecturePlan:
                    return ArchitecturePlan(
                        summary="Plan",
                        relevant_files=["calculator.py"],
                        test_strategy="Run pytest",
                    )
                elif schema == CodeChange:
                    return CodeChange(
                        file_path="calculator.py",
                        change_type="write",
                        explanation="Fix",
                        root_cause="Bug",
                        patch="def add(a, b):\n    return a + b\n",
                        confidence=0.9,
                    )
                elif schema == ReviewResult:
                    return ReviewResult(
                        approved=False,
                        root_cause_fixed=False,
                        regression_risk="high",
                        reasoning="Suspicious modification",
                        recommendation="Reject patch",
                        confidence=0.9,
                    )
                raise ValueError(f"Unexpected schema: {schema}")

            mock_llm.generate_structured.side_effect = mock_generate_structured

            final_state = run_repair_workflow(
                run_id=run.id,
                workspace_id=wm.workspace_id,
                project_path=str(pdir),
                llm_provider=mock_llm,
                db=e2e_db,
                max_iterations=1,
            )

            assert final_state["status"] == "failed"
            assert final_state["termination_reason"] in (
                "reviewer_rejected", "max_iterations_reached",
            )
        finally:
            wm.cleanup()

    def test_download_endpoint_after_repair(self, e2e_client, e2e_db):
        """Verify GET /api/runs/{run_id}/download returns a valid ZIP of repaired code."""
        wm = WorkspaceManager.create()
        try:
            pdir = wm.get_project_path()
            calc_file = pdir / "calculator.py"
            calc_file.write_text("def add(a, b):\n    return a + b\n", encoding="utf-8")

            project = Project(
                id="proj-dl-test",
                name="dl_test",
                original_filename="calc.zip",
                workspace_path=str(wm.get_workspace_path()),
                file_count=1,
                size_bytes=50,
            )
            run = Run(
                id="run-dl-test",
                project_id=project.id,
                status="passed",
                max_iterations=5,
            )
            e2e_db.add(project)
            e2e_db.add(run)
            e2e_db.commit()

            resp = e2e_client.get(f"/api/runs/{run.id}/download")
            assert resp.status_code == 200
            assert resp.headers["content-type"] == "application/zip"
            assert "attachment;" in resp.headers["content-disposition"]

            # Validate ZIP content
            zf = zipfile.ZipFile(io.BytesIO(resp.content))
            files = zf.namelist()
            assert any("calculator.py" in f for f in files)
        finally:
            wm.cleanup()

    def test_repair_results_api_contains_full_agent_data(self, e2e_client, e2e_db):
        """Verify GET /api/runs/{run_id}/results returns complete populated agent details."""
        run = Run(
            id="run-results-test",
            project_id="dummy-proj",
            status="passed",
            max_iterations=5,
            current_iteration=1,
            final_summary="Repair completed successfully",
        )
        e2e_db.add(run)

        upsert_iteration(
            db=e2e_db,
            run_id=run.id,
            iteration_number=1,
            architecture_plan={
                "summary": "Fix operator in calculator.py",
                "relevant_files": ["calculator.py"],
                "test_strategy": "Run pytest",
            },
            code_changes=[
                {
                    "file_path": "calculator.py",
                    "change_type": "write",
                    "explanation": "Fixed subtraction to addition",
                    "patch": "def add(a, b):\n    return a + b\n",
                }
            ],
            test_results={
                "passed": 4,
                "failed": 0,
                "exit_code": 0,
                "duration": 0.42,
                "stdout": "4 passed in 0.42s",
                "stderr": "",
            },
            review_result={
                "approved": True,
                "root_cause_fixed": True,
                "regression_risk": "low",
                "reasoning": "Clean fix",
            },
            tests_passed=4,
            tests_failed=0,
            approved=True,
            duration_seconds=0.42,
        )

        resp = e2e_client.get(f"/api/runs/{run.id}/results")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "passed"
        assert len(data["iterations"]) == 1

        it_data = data["iterations"][0]
        assert it_data["architecture_plan"]["summary"] == "Fix operator in calculator.py"
        assert it_data["code_changes"][0]["file_path"] == "calculator.py"
        assert it_data["test_results"]["passed"] == 4
        assert it_data["review_result"]["approved"] is True
        assert it_data["approved"] is True

        # Check conceptual aliases
        assert it_data["architect"]["summary"] == "Fix operator in calculator.py"
        assert it_data["coder"]["file_path"] == "calculator.py"
        assert it_data["tests"]["passed"] == 4
        assert it_data["reviewer"]["approved"] is True

    def test_failed_run_retains_partial_iteration_details(self, e2e_client, e2e_db):
        """Verify that when a run fails/rejects, all intermediate agent outputs are retained."""
        run = Run(
            id="run-failed-partial",
            project_id="dummy-proj",
            status="failed",
            max_iterations=1,
            current_iteration=1,
            final_summary="Graph terminated with status='failed', reason='reviewer_rejected'",
        )
        e2e_db.add(run)

        # Architect and Coder and Test completed, but Reviewer rejected
        upsert_iteration(
            db=e2e_db,
            run_id=run.id,
            iteration_number=1,
            architecture_plan={
                "summary": "Attempted fix for math bug",
                "relevant_files": ["calculator.py"],
                "suspected_issues": ["Bug in add"],
                "test_strategy": "Run test_calculator.py",
            },
            code_changes=[
                {
                    "file_path": "calculator.py",
                    "change_type": "write",
                    "explanation": "Applied temporary patch",
                    "root_cause": "Bug in add",
                    "patch": "def add(a, b): return a + b",
                }
            ],
            test_results={
                "passed": 4,
                "failed": 0,
                "exit_code": 0,
                "duration": 0.5,
                "stdout": "4 passed",
                "stderr": "",
            },
            review_result={
                "approved": False,
                "root_cause_fixed": False,
                "regression_risk": "high",
                "reasoning": "Code style violation and missing docstring",
            },
            tests_passed=4,
            tests_failed=0,
            approved=False,
            duration_seconds=0.5,
        )

        resp = e2e_client.get(f"/api/runs/{run.id}/results")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "failed"
        assert data["reviewer_approved"] is False
        assert data["termination_reason"] == "reviewer_rejected"

        it = data["iterations"][0]
        # Verify Architect data is NOT lost
        assert it["architect"]["summary"] == "Attempted fix for math bug"
        # Verify Coder data is NOT lost
        assert it["coder"]["file_path"] == "calculator.py"
        # Verify Test data is NOT lost
        assert it["tests"]["passed"] == 4
        # Verify Reviewer rejection is clear
        assert it["reviewer"]["approved"] is False

    def test_api_response_contains_nested_conceptual_schema(self, e2e_client, e2e_db):
        """Verify the exact conceptual JSON schema returned by the results endpoint."""
        run = Run(
            id="run-nested-schema",
            project_id="dummy-proj",
            status="passed",
            max_iterations=5,
            current_iteration=1,
            final_summary="Graph terminated with status='passed', reason='all_tests_passed'",
        )
        e2e_db.add(run)

        upsert_iteration(
            db=e2e_db,
            run_id=run.id,
            iteration_number=1,
            architecture_plan={
                "summary": "Architectural repair plan",
                "relevant_files": ["calculator.py"],
                "suspected_issues": ["Wrong operator"],
                "test_strategy": "pytest -v",
            },
            code_changes=[
                {
                    "file_path": "calculator.py",
                    "change_type": "write",
                    "explanation": "Fixed operator",
                    "root_cause": "Typo",
                    "patch": "def add(a, b): return a + b",
                }
            ],
            test_results={
                "passed": 4,
                "failed": 0,
                "exit_code": 0,
                "duration": 7.7,
                "stdout": "4 passed in 7.70s",
                "stderr": "",
            },
            review_result={
                "approved": True,
                "root_cause_fixed": True,
                "regression_risk": "low",
                "reasoning": "Clean fix",
            },
            tests_passed=4,
            tests_failed=0,
            approved=True,
            duration_seconds=7.7,
        )

        resp = e2e_client.get(f"/api/runs/{run.id}/results")
        assert resp.status_code == 200
        data = resp.json()

        # Top-level conceptual fields
        assert data["status"] == "passed"
        assert data["tests_passed"] == 4
        assert data["tests_failed"] == 0
        assert data["reviewer_approved"] is True
        assert data["total_iterations"] == 1
        assert data["termination_reason"] == "all_tests_passed"

        # Nested iteration_details
        assert "iteration_details" in data
        it = data["iteration_details"][0]
        assert it["iteration"] == 1
        assert it["architect"]["summary"] == "Architectural repair plan"
        assert it["coder"]["change_type"] == "write"
        assert it["tests"]["exit_code"] == 0
        assert it["reviewer"]["approved"] is True

    def test_persistence_survives_db_session_reopen(self, e2e_db):
        """Verify that persisting iteration data can be queried from fresh database sessions."""
        run = Run(
            id="run-reopen-test",
            project_id="proj-123",
            status="passed",
            max_iterations=3,
        )
        e2e_db.add(run)
        e2e_db.commit()

        # Stage 1: Architect writes
        upsert_iteration(
            db=e2e_db,
            run_id=run.id,
            iteration_number=1,
            architecture_plan={"summary": "Plan stage"},
        )

        # Query in fresh transaction
        it1 = e2e_db.query(Iteration).filter(Iteration.run_id == run.id).first()
        assert it1 is not None
        assert it1.architecture_plan["summary"] == "Plan stage"
        assert it1.code_changes is None

        # Stage 2: Coder updates without overwriting Architect
        upsert_iteration(
            db=e2e_db,
            run_id=run.id,
            iteration_number=1,
            code_changes=[{"file_path": "main.py", "change_type": "write"}],
        )

        it2 = e2e_db.query(Iteration).filter(Iteration.run_id == run.id).first()
        assert it2 is not None
        assert it2.architecture_plan["summary"] == "Plan stage"
        assert it2.code_changes[0]["file_path"] == "main.py"
