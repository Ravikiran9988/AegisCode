"""
Phase 1 tests — verify the scaffold, config, DB, and API health endpoint.

Run:
    pytest tests/test_phase1.py -v
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.core.config import settings
from backend.database.models import Base, Event, Iteration, Project, Run
from backend.database.session import get_db
from backend.main import app

# ── Fixtures ───────────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def in_memory_engine():
    """SQLite in-memory engine for isolated tests."""
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    yield engine
    engine.dispose()


@pytest.fixture(scope="module")
def db_session(in_memory_engine):
    """Session bound to in-memory engine."""
    TestingSession = sessionmaker(bind=in_memory_engine, autocommit=False, autoflush=False)
    db = TestingSession()
    yield db
    db.close()


@pytest.fixture(scope="module")
def client(in_memory_engine):
    """FastAPI test client with overridden DB dependency."""
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

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


# ── Config tests ───────────────────────────────────────────────────────────────

class TestConfig:
    def test_app_name_default(self):
        assert settings.app_name == "AegisCode"

    def test_api_port_default(self):
        assert settings.api_port == 8000

    def test_max_iterations_default(self):
        assert settings.max_iterations == 5

    def test_llm_provider_default(self):
        assert settings.llm_provider == "openai_compatible"

    def test_workspace_path_is_absolute(self):
        assert settings.workspace_path.is_absolute()


# ── Database schema tests ──────────────────────────────────────────────────────

class TestDatabase:
    def test_tables_created(self, in_memory_engine):
        tables = in_memory_engine.dialect.get_table_names(in_memory_engine.connect())
        for expected in ("projects", "runs", "iterations", "events"):
            assert expected in tables

    def test_create_project(self, db_session):
        p = Project(
            name="test_project",
            original_filename="test.zip",
            workspace_path="/tmp/test",
            file_count=3,
            size_bytes=1024,
        )
        db_session.add(p)
        db_session.commit()
        assert p.id is not None
        assert db_session.get(Project, p.id) is not None

    def test_create_run(self, db_session):
        p = Project(
            name="run_project",
            original_filename="run.zip",
            workspace_path="/tmp/run",
        )
        db_session.add(p)
        db_session.flush()

        r = Run(project_id=p.id, max_iterations=3)
        db_session.add(r)
        db_session.commit()
        assert r.id is not None
        assert r.status == "pending"

    def test_create_iteration(self, db_session):
        p = Project(
            name="iter_project",
            original_filename="iter.zip",
            workspace_path="/tmp/iter",
        )
        db_session.add(p)
        db_session.flush()
        r = Run(project_id=p.id)
        db_session.add(r)
        db_session.flush()

        it = Iteration(run_id=r.id, iteration_number=1)
        db_session.add(it)
        db_session.commit()
        assert it.id is not None

    def test_create_event(self, db_session):
        p = Project(
            name="event_project",
            original_filename="event.zip",
            workspace_path="/tmp/event",
        )
        db_session.add(p)
        db_session.flush()
        r = Run(project_id=p.id)
        db_session.add(r)
        db_session.flush()

        ev = Event(
            run_id=r.id,
            agent="architect",
            event_type="tool_call",
            payload={"tool": "list_files"},
        )
        db_session.add(ev)
        db_session.commit()
        assert ev.id is not None
        assert ev.payload["tool"] == "list_files"


# ── API tests ──────────────────────────────────────────────────────────────────

class TestHealthEndpoint:
    def test_health_returns_200(self, client):
        response = client.get("/health")
        assert response.status_code == 200

    def test_health_status_ok(self, client):
        data = client.get("/health").json()
        assert data["status"] == "ok"

    def test_health_contains_version(self, client):
        data = client.get("/health").json()
        assert data["version"] == settings.app_version

    def test_health_database_connected(self, client):
        data = client.get("/health").json()
        assert data["database"] == "connected"

    def test_health_contains_llm_provider(self, client):
        data = client.get("/health").json()
        assert data["llm_provider"] == settings.llm_provider

    def test_health_timestamp_present(self, client):
        data = client.get("/health").json()
        assert "timestamp" in data
        assert len(data["timestamp"]) > 10
