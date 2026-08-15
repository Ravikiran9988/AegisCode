"""
Phase 4 Tests — LangGraph StateGraph, Autonomous Repair Loop, & API Integration.

Tests run 100% offline using `MockLLMProvider`.
Includes optional live Ollama integration test.
"""

from __future__ import annotations

import io
import zipfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.agents.schemas import CodeChange
from backend.core.config import settings
from backend.database.models import Base
from backend.database.session import get_db
from backend.execution.workspace import WorkspaceManager
from backend.graph.graph import build_repair_graph, run_repair_workflow
from backend.graph.loop_detector import compute_failure_fingerprint, is_repeated_failure
from backend.llm.mock import MockLLMProvider
from backend.llm.ollama import OllamaLLMProvider
from backend.main import app
from backend.tools.git_tools import init_repo
from backend.tools.pytest_runner import TestResult

# ── Fixture Paths ──────────────────────────────────────────────────────────────

FIXTURES_DIR = Path(__file__).parent / "fixtures" / "projects"
PASSING_PROJECT = FIXTURES_DIR / "passing_project"
FAILING_PROJECT = FIXTURES_DIR / "failing_project"
UNFIXABLE_PROJECT = FIXTURES_DIR / "unfixable_project"


def _zip_from_dir(directory: Path) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for file in directory.rglob("*"):
            if file.is_file():
                zf.write(file, file.relative_to(directory))
    return buf.getvalue()


@pytest.fixture(scope="module")
def in_memory_engine(tmp_path_factory):
    db_file = tmp_path_factory.mktemp("db") / "test_p4.db"
    engine = create_engine(f"sqlite:///{db_file}", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    yield engine
    engine.dispose()


@pytest.fixture()
def db_session(in_memory_engine):
    TestingSession = sessionmaker(bind=in_memory_engine, autocommit=False, autoflush=False)
    session = TestingSession()
    yield session
    session.close()


@pytest.fixture()
def api_client(in_memory_engine, tmp_path_factory):
    test_workspace = tmp_path_factory.mktemp("workspaces_api")
    TestingSession = sessionmaker(bind=in_memory_engine, autocommit=False, autoflush=False)

    def override_get_db():
        db = TestingSession()
        try:
            yield db
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    original_workspace = settings.workspace_base_dir
    settings.workspace_base_dir = str(test_workspace)

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()
    settings.workspace_base_dir = original_workspace


# ══════════════════════════════════════════════════════════════════════════════
# 1. GRAPH CONSTRUCTION TESTS
# ══════════════════════════════════════════════════════════════════════════════

class TestGraphConstruction:
    def test_build_repair_graph_compiles(self):
        mock_llm = MockLLMProvider()
        graph = build_repair_graph(llm_provider=mock_llm)
        assert graph is not None


# ══════════════════════════════════════════════════════════════════════════════
# 2. DETERMINISTIC WORKFLOW TESTS
# ══════════════════════════════════════════════════════════════════════════════

class TestRepairWorkflows:
    def test_already_passing_project_terminates_immediately(self, tmp_path, db_session):
        """Passing project must terminate at initial_test_node with already_passing status."""
        wm = WorkspaceManager.create(base_dir=tmp_path)
        p_path = wm.extract_project(_zip_from_dir(PASSING_PROJECT))
        wm.set_project_root(p_path)
        init_repo(p_path)

        mock_llm = MockLLMProvider()
        state = run_repair_workflow(
            run_id="run-already-passing",
            workspace_id=wm.workspace_id,
            project_path=str(p_path),
            llm_provider=mock_llm,
            db=db_session,
        )

        assert state["status"] == "already_passing"
        assert state["termination_reason"] == "all_tests_passed"
        wm.cleanup()

    def test_successful_repair_one_iteration(self, tmp_path, db_session):
        """Failing project repaired by Coder on iteration 1 -> status passed."""
        wm = WorkspaceManager.create(base_dir=tmp_path)
        p_path = wm.extract_project(_zip_from_dir(FAILING_PROJECT))
        wm.set_project_root(p_path)
        init_repo(p_path)

        # Supply working patch to mock Coder
        calc_fix = (
            "def add(a, b):\n    return a + b\n\n"
            "def subtract(a, b):\n    return a - b\n\n"
            "def multiply(a, b):\n    return a * b\n\n"
            "def divide(a, b):\n"
            "    if b == 0:\n"
            "        raise ValueError('Cannot divide by zero')\n"
            "    return a / b\n\n"
            "def factorial(n):\n"
            "    if n < 0:\n"
            "        raise ValueError('Factorial of negative number')\n"
            "    if n == 0:\n"
            "        return 1\n"
            "    return n * factorial(n - 1)\n"
        )
        mock_llm = MockLLMProvider(
            mock_change=CodeChange(
                file_path="calculator.py",
                change_type="write",
                explanation="Fix calculator bugs",
                root_cause="Bad operators",
                patch=calc_fix,
            )
        )

        state = run_repair_workflow(
            run_id="run-success-repair",
            workspace_id=wm.workspace_id,
            project_path=str(p_path),
            llm_provider=mock_llm,
            db=db_session,
        )

        assert state["status"] == "passed"
        assert state["termination_reason"] == "all_tests_passed"
        wm.cleanup()

    def test_max_iterations_protection(self, tmp_path, db_session):
        """Unfixable project must terminate at max_iterations_reached."""
        wm = WorkspaceManager.create(base_dir=tmp_path)
        p_path = wm.extract_project(_zip_from_dir(UNFIXABLE_PROJECT))
        wm.set_project_root(p_path)
        init_repo(p_path)

        mock_llm = MockLLMProvider(
            mock_change=CodeChange(
                file_path="logic.py",
                change_type="write",
                explanation="Ineffective fix",
                root_cause="Unknown",
                patch="def compute_hash(val):\n    return 'STILL_WRONG'\n",
            )
        )

        state = run_repair_workflow(
            run_id="run-max-iter",
            workspace_id=wm.workspace_id,
            project_path=str(p_path),
            llm_provider=mock_llm,
            db=db_session,
            max_iterations=2,
        )

        assert state["status"] in ("failed", "stalled")
        assert state["termination_reason"] in ("max_iterations_reached", "repeated_failure")
        wm.cleanup()

    def test_loop_detector_repeated_failure(self):
        """Fingerprint comparison detects 2 consecutive identical failures."""
        dummy_fail = TestResult(
            exit_code=1,
            passed=2,
            failed=3,
            success=False,
            stdout="FAILED test_logic.py::test_hash - AssertionError",
        )
        fp = compute_failure_fingerprint(dummy_fail)
        assert fp != "PASS"

        history = [fp]
        assert is_repeated_failure(fp, history, threshold=2) is True

    def test_policy_violation_safe_termination(self, tmp_path, db_session):
        """Attempt by Coder to modify test_calculator.py terminates graph safely."""
        wm = WorkspaceManager.create(base_dir=tmp_path)
        p_path = wm.extract_project(_zip_from_dir(FAILING_PROJECT))
        wm.set_project_root(p_path)
        init_repo(p_path)

        mock_llm = MockLLMProvider(
            mock_change=CodeChange(
                file_path="test_calculator.py",
                change_type="write",
                explanation="Malicious test override",
                root_cause="N/A",
                patch="def test_add(): pass\n",
            )
        )

        state = run_repair_workflow(
            run_id="run-policy-violation",
            workspace_id=wm.workspace_id,
            project_path=str(p_path),
            llm_provider=mock_llm,
            db=db_session,
        )

        assert state["status"] == "error"
        assert state["termination_reason"] == "policy_violation"
        wm.cleanup()

    def test_llm_failure_safe_termination(self, tmp_path, db_session):
        """LLM error during graph execution is caught safely."""
        wm = WorkspaceManager.create(base_dir=tmp_path)
        p_path = wm.extract_project(_zip_from_dir(FAILING_PROJECT))
        wm.set_project_root(p_path)
        init_repo(p_path)

        mock_llm = MockLLMProvider(should_fail=True)

        state = run_repair_workflow(
            run_id="run-llm-fail",
            workspace_id=wm.workspace_id,
            project_path=str(p_path),
            llm_provider=mock_llm,
            db=db_session,
        )

        assert state["status"] == "error"
        assert state["termination_reason"] == "llm_error"
        wm.cleanup()


# ══════════════════════════════════════════════════════════════════════════════
# 3. API ENDPOINTS TESTS
# ══════════════════════════════════════════════════════════════════════════════

class TestRepairAPI:
    def test_repair_launch_and_status_endpoints(self, api_client):
        # 1. Upload project
        zip_data = _zip_from_dir(PASSING_PROJECT)
        up_resp = api_client.post(
            "/api/projects/upload",
            files={"file": ("passing.zip", zip_data, "application/zip")},
        )
        assert up_resp.status_code == 201
        pid = up_resp.json()["project_id"]

        # 2. Create Run
        run_resp = api_client.post("/api/runs", json={"project_id": pid})
        assert run_resp.status_code == 201
        rid = run_resp.json()["run_id"]

        # 3. Trigger repair loop endpoint
        rep_resp = api_client.post(f"/api/runs/{rid}/repair")
        assert rep_resp.status_code == 202
        assert rep_resp.json()["status"] == "running"

        # 4. Check status endpoint
        stat_resp = api_client.get(f"/api/runs/{rid}/status")
        assert stat_resp.status_code == 200
        sdata = stat_resp.json()
        assert "status" in sdata
        assert "tests_passed" in sdata


# ══════════════════════════════════════════════════════════════════════════════
# 4. OPTIONAL LIVE OLLAMA TEST
# ══════════════════════════════════════════════════════════════════════════════

class TestOllamaLiveRepair:
    def test_live_ollama_repair_if_available(self, tmp_path):
        provider = OllamaLLMProvider()
        avail, msg = provider.is_available()
        if not avail:
            pytest.skip(f"Ollama not running locally ({msg}); skipping live repair test.")

        wm = WorkspaceManager.create(base_dir=tmp_path)
        p_path = wm.extract_project(_zip_from_dir(PASSING_PROJECT))
        wm.set_project_root(p_path)

        state = run_repair_workflow(
            run_id="run-ollama-live",
            workspace_id=wm.workspace_id,
            project_path=str(p_path),
            llm_provider=provider,
            max_iterations=1,
        )

        assert state["status"] in ("already_passing", "passed", "failed")
        wm.cleanup()
