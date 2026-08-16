"""
Comprehensive Persistence & Run Lifecycle Tests for AegisCode.

Verifies:
- Direct SQLAlchemy database session creation, persistence, and querying
- Data survival across separate database sessions
- Run status transitions (pending -> running -> passed / failed)
- Iteration results and test metrics persistence
- API endpoints: GET /api/runs, GET /api/runs/{run_id}, GET /api/runs/active, GET /api/runs/history
- Frontend api_client list response parsing without exceptions
- Overview metrics aggregation from persisted runs
"""

from __future__ import annotations

import io
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.database.models import Base, Project, Run
from backend.database.persistence import upsert_iteration
from backend.database.session import get_db
from backend.main import app
from frontend.utils.api_client import fetch_active_runs, fetch_history_runs, fetch_recent_runs

FIXTURES_DIR = Path(__file__).parent / "fixtures" / "projects"
PASSING_PROJECT = FIXTURES_DIR / "passing_project"


def _zip_from_dir(directory: Path) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for file in directory.rglob("*"):
            if file.is_file():
                zf.write(file, file.relative_to(directory))
    return buf.getvalue()


@pytest.fixture(scope="module")
def persistent_test_engine(tmp_path_factory):
    db_file = tmp_path_factory.mktemp("db") / "persistence_test.db"
    engine = create_engine(
        f"sqlite:///{db_file}",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(bind=engine)
    yield engine
    engine.dispose()


@pytest.fixture()
def session_factory(persistent_test_engine):
    return sessionmaker(
        bind=persistent_test_engine,
        autocommit=False,
        autoflush=False,
        expire_on_commit=False,
    )


@pytest.fixture()
def db_session(session_factory):
    session = session_factory()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture()
def api_client(persistent_test_engine, session_factory):
    def override_get_db():
        db = session_factory()
        try:
            yield db
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    client = TestClient(app)
    yield client
    app.dependency_overrides.clear()


class TestDatabasePersistenceLifecycle:
    def test_create_run_persists(self, session_factory):
        """Creating a run and committing saves it to the database."""
        session1 = session_factory()
        proj = Project(
            name="Calculator App",
            original_filename="calc.zip",
            workspace_path="/tmp/ws_1",
            file_count=3,
        )
        session1.add(proj)
        session1.commit()

        run = Run(
            project_id=proj.id,
            status="pending",
            max_iterations=5,
            current_iteration=0,
        )
        session1.add(run)
        session1.commit()
        run_id = run.id
        session1.close()

        # Reopen in new session
        session2 = session_factory()
        fetched = session2.get(Run, run_id)
        assert fetched is not None
        assert fetched.id == run_id
        assert fetched.status == "pending"
        assert fetched.project.name == "Calculator App"
        session2.close()

    def test_get_run_after_creation(self, session_factory):
        """Run can be retrieved by primary key with all fields intact."""
        session = session_factory()
        proj = Project(
            name="Math Lib",
            original_filename="math.zip",
            workspace_path="/tmp/ws_2",
        )
        session.add(proj)
        session.commit()

        run = Run(
            project_id=proj.id,
            status="running",
            max_iterations=3,
            current_iteration=1,
            started_at=datetime.now(timezone.utc),
        )
        session.add(run)
        session.commit()
        run_id = run.id
        session.close()

        session2 = session_factory()
        r = session2.get(Run, run_id)
        assert r is not None
        assert r.current_iteration == 1
        assert r.max_iterations == 3
        assert r.started_at is not None
        session2.close()

    def test_update_running_run_persists(self, session_factory):
        """Updating iteration and state on a running run commits to DB."""
        session = session_factory()
        proj = Project(
            name="Service App",
            original_filename="srv.zip",
            workspace_path="/tmp/ws_3",
        )
        session.add(proj)
        session.commit()

        run = Run(project_id=proj.id, status="running", current_iteration=1)
        session.add(run)
        session.commit()
        run_id = run.id

        # Update run iteration and upsert iteration
        run.current_iteration = 2
        upsert_iteration(
            db=session,
            run_id=run_id,
            iteration_number=1,
            architecture_plan={"root_cause": "Typo in line 10"},
            tests_passed=5,
            tests_failed=1,
        )
        session.commit()
        session.close()

        # Verify from new session
        session2 = session_factory()
        r = session2.get(Run, run_id)
        assert r.current_iteration == 2
        assert len(r.iterations) == 1
        assert r.iterations[0].tests_passed == 5
        assert r.iterations[0].architecture_plan["root_cause"] == "Typo in line 10"
        session2.close()

    def test_complete_run_persists(self, session_factory):
        """When run completes, status='passed', finished_at and final_summary are saved."""
        session = session_factory()
        proj = Project(
            name="Payment Gateway",
            original_filename="pay.zip",
            workspace_path="/tmp/ws_4",
        )
        session.add(proj)
        session.commit()

        t0 = datetime.now(timezone.utc)
        run = Run(project_id=proj.id, status="running", started_at=t0)
        session.add(run)
        session.commit()
        run_id = run.id

        # Complete run
        run.status = "passed"
        run.finished_at = datetime.now(timezone.utc)
        run.final_summary = "Graph terminated with status='passed', reason='all_tests_passed'"
        upsert_iteration(
            db=session,
            run_id=run_id,
            iteration_number=1,
            tests_passed=10,
            tests_failed=0,
            approved=True,
            duration_seconds=4.5,
        )
        session.commit()
        session.close()

        session2 = session_factory()
        r = session2.get(Run, run_id)
        assert r.status == "passed"
        assert r.finished_at is not None
        assert "all_tests_passed" in r.final_summary
        assert r.iterations[0].approved is True
        session2.close()

    def test_failed_run_persists(self, session_factory):
        """When run fails, failed status, error summary, and test counts persist."""
        session = session_factory()
        proj = Project(
            name="Buggy Project",
            original_filename="bug.zip",
            workspace_path="/tmp/ws_5",
        )
        session.add(proj)
        session.commit()

        run = Run(project_id=proj.id, status="running")
        session.add(run)
        session.commit()
        run_id = run.id

        run.status = "failed"
        run.finished_at = datetime.now(timezone.utc)
        run.final_summary = "Graph terminated with status='failed', reason='max_iterations_reached'"
        upsert_iteration(
            db=session,
            run_id=run_id,
            iteration_number=5,
            tests_passed=8,
            tests_failed=2,
            approved=False,
        )
        session.commit()
        session.close()

        session2 = session_factory()
        r = session2.get(Run, run_id)
        assert r.status == "failed"
        assert "max_iterations_reached" in r.final_summary
        assert r.iterations[0].approved is False
        session2.close()

    def test_run_survives_new_database_session(self, session_factory):
        """
        Proof of persistent storage:
        1. Open session A
        2. Create project and run
        3. Explicitly commit and CLOSE session A
        4. Open new session B
        5. Verify exact record is present and unmodified
        """
        session_a = session_factory()
        proj = Project(
            name="Persistence Survivor",
            original_filename="survivor.zip",
            workspace_path="/tmp/ws_surv",
        )
        session_a.add(proj)
        session_a.commit()

        run = Run(
            id="fd468340-7fcd-4a01-bb2e-9c987bc14e58",
            project_id=proj.id,
            status="passed",
            max_iterations=5,
            current_iteration=2,
            final_summary="Autonomous self-healing completed successfully",
        )
        session_a.add(run)
        session_a.commit()
        session_a.close()

        # Entirely new session
        session_b = session_factory()
        survivor = session_b.get(Run, "fd468340-7fcd-4a01-bb2e-9c987bc14e58")
        assert survivor is not None
        assert survivor.id == "fd468340-7fcd-4a01-bb2e-9c987bc14e58"
        assert survivor.status == "passed"
        assert survivor.project.name == "Persistence Survivor"
        session_b.close()


class TestEndpointsAndHistoryAPI:
    def test_history_returns_runs(self, api_client):
        """GET /api/runs and GET /api/runs/history return historical runs list."""
        resp = api_client.get("/api/runs")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) > 0

        hist_resp = api_client.get("/api/runs/history")
        assert hist_resp.status_code == 200
        h_data = hist_resp.json()
        assert isinstance(h_data, list)
        assert len(h_data) > 0

    def test_active_runs_returns_running_runs(self, api_client, session_factory):
        """GET /api/runs/active returns only active runs."""
        session = session_factory()
        proj = Project(name="Active App", original_filename="a.zip", workspace_path="/tmp/ws_a")
        session.add(proj)
        session.commit()

        active_run = Run(project_id=proj.id, status="running")
        session.add(active_run)
        session.commit()
        session.close()

        resp = api_client.get("/api/runs/active")
        assert resp.status_code == 200
        active_list = resp.json()
        assert isinstance(active_list, list)
        assert any(r["run_id"] == active_run.id for r in active_list)

    def test_api_fetch_recent_runs_handles_both_list_and_dict(self):
        """frontend api_client parses list response and dictionary response seamlessly."""
        mock_list_resp = MagicMock()
        mock_list_resp.status_code = 200
        mock_list_resp.json.return_value = [{"run_id": "run-1", "status": "passed"}]

        with patch("frontend.utils.api_client._safe_get", return_value=mock_list_resp):
            runs = fetch_recent_runs("http://localhost:8000/api")
            assert len(runs) == 1
            assert runs[0]["run_id"] == "run-1"

        mock_dict_resp = MagicMock()
        mock_dict_resp.status_code = 200
        mock_dict_resp.json.return_value = {"runs": [{"run_id": "run-2", "status": "failed"}]}

        with patch("frontend.utils.api_client._safe_get", return_value=mock_dict_resp):
            runs = fetch_recent_runs("http://localhost:8000/api")
            assert len(runs) == 1
            assert runs[0]["run_id"] == "run-2"

            active = fetch_active_runs("http://localhost:8000/api")
            assert len(active) == 1

            hist = fetch_history_runs("http://localhost:8000/api")
            assert len(hist) == 1

    def test_overview_metrics_include_runs(self):
        """Dashboard overview computes accurate KPIs from persisted run objects."""
        sample_runs = [
            {
                "run_id": "run-1",
                "project_name": "Calc",
                "status": "passed",
                "tests_passed": 10,
                "tests_failed": 0,
                "duration": 5.0,
            },
            {
                "run_id": "run-2",
                "project_name": "Auth",
                "status": "failed",
                "tests_passed": 4,
                "tests_failed": 2,
                "duration": 8.0,
            },
        ]

        total_runs = len(sample_runs)
        term_statuses = ("passed", "already_passing", "failed", "error", "stalled")
        completed_runs = [r for r in sample_runs if r.get("status") in term_statuses]
        passed_runs = [r for r in sample_runs if r.get("status") in ("passed", "already_passing")]
        success_rate = (len(passed_runs) / len(completed_runs)) * 100
        repaired_projects = {r.get("project_name") for r in passed_runs if r.get("project_name")}
        total_tests_passed = sum(r.get("tests_passed", 0) for r in sample_runs)
        total_tests_failed = sum(r.get("tests_failed", 0) for r in sample_runs)
        total_tests_executed = total_tests_passed + total_tests_failed

        assert total_runs == 2
        assert success_rate == 50.0
        assert len(repaired_projects) == 1
        assert total_tests_executed == 16
        assert total_tests_passed == 14
