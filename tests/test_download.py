"""
test_download.py — Phase 6 Tests.

Tests for GET /api/runs/{run_id}/download:

1.  Successful run → download endpoint returns ZIP.
2.  ZIP contains repaired source files.
3.  ZIP does NOT contain .env.
4.  ZIP does NOT contain database files (*.db, *.db-shm, *.db-wal).
5.  ZIP does NOT contain __pycache__.
6.  Invalid run_id → 404.
7.  Running run → download rejected (409).
8.  Failed run → download rejected (409).
9.  Path traversal cannot escape workspace.
10. Download response headers are correct.
11. Stalled run → download rejected (409).
12. _is_excluded helper covers all exclusion patterns.
"""

from __future__ import annotations

import io
import zipfile
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.api.runs import _is_excluded
from backend.core.config import settings
from backend.database.models import Base, Project, Run
from backend.database.session import get_db
from backend.execution.workspace import WorkspaceManager
from backend.main import app

# ── Shared fixtures ───────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def dl_engine(tmp_path_factory):
    """In-memory SQLite engine for download tests."""
    db_file = tmp_path_factory.mktemp("dl_db") / "test_download.db"
    engine = create_engine(
        f"sqlite:///{db_file}",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(bind=engine)
    yield engine
    engine.dispose()


@pytest.fixture()
def dl_db(dl_engine):
    DLSession = sessionmaker(bind=dl_engine, autocommit=False, autoflush=False)
    session = DLSession()
    yield session
    session.rollback()
    session.close()


@pytest.fixture()
def dl_workspace(tmp_path_factory):
    """A real temp workspace containing some source files and sensitive files."""
    base = tmp_path_factory.mktemp("dl_workspaces")
    wm = WorkspaceManager.create(base_dir=base)
    proj_dir = wm.get_workspace_path() / "project"
    proj_dir.mkdir(exist_ok=True)

    # Normal source files that SHOULD be in the ZIP
    (proj_dir / "main.py").write_text("print('hello')\n", encoding="utf-8")
    (proj_dir / "utils.py").write_text("def helper(): pass\n", encoding="utf-8")
    (proj_dir / "README.md").write_text("# My Project\n", encoding="utf-8")

    # ── Sensitive / excluded files ──────────────────────────────────────────
    # .env
    (proj_dir / ".env").write_text("OPENAI_API_KEY=sk-secret\n", encoding="utf-8")
    # .env variant
    (proj_dir / ".env.production").write_text("DB_PASS=secret\n", encoding="utf-8")
    # database files
    (proj_dir / "app.db").write_bytes(b"SQLite binary content")
    (proj_dir / "app.db-shm").write_bytes(b"shared memory")
    (proj_dir / "app.db-wal").write_bytes(b"write-ahead log")
    # __pycache__
    cache_dir = proj_dir / "__pycache__"
    cache_dir.mkdir()
    (cache_dir / "main.cpython-311.pyc").write_bytes(b"\xc4\x0d compiled")
    # .git directory
    git_dir = proj_dir / ".git"
    git_dir.mkdir()
    (git_dir / "config").write_text("[core]\n", encoding="utf-8")
    # pytest cache
    pytest_cache = proj_dir / ".pytest_cache"
    pytest_cache.mkdir()
    (pytest_cache / "v" ).mkdir()

    # Record project root marker so WorkspaceManager.get_project_path() returns proj_dir
    (wm.get_workspace_path() / "project_root").write_text(
        str(proj_dir), encoding="utf-8"
    )

    yield wm, base


@pytest.fixture()
def dl_client(dl_engine, dl_workspace):
    """TestClient with DB override pointing to the temp workspace."""
    wm, base = dl_workspace
    DLSession = sessionmaker(bind=dl_engine, autocommit=False, autoflush=False)

    def override_get_db():
        db = DLSession()
        try:
            yield db
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    original_ws = settings.workspace_base_dir
    settings.workspace_base_dir = str(base)
    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app) as client:
        yield client, wm, base

    app.dependency_overrides.clear()
    settings.workspace_base_dir = original_ws


def _make_run(
    db,
    workspace_path: str,
    run_status: str = "passed",
) -> tuple[Project, Run]:
    """Insert a Project + Run record into the DB and return both."""
    proj = Project(
        name="test-project",
        original_filename="test-project.zip",
        workspace_path=workspace_path,
        file_count=3,
        size_bytes=1024,
    )
    db.add(proj)
    db.flush()

    now = datetime.now(timezone.utc)
    run = Run(
        project_id=proj.id,
        status=run_status,
        max_iterations=5,
        current_iteration=1,
        started_at=now,
        finished_at=now,
        final_summary=f"Test run with status={run_status}",
    )
    db.add(run)
    db.commit()
    db.refresh(run)
    return proj, run


# ══════════════════════════════════════════════════════════════════════════════
# Test Class
# ══════════════════════════════════════════════════════════════════════════════

class TestDownloadEndpoint:

    # 1. Successful run → download endpoint returns ZIP
    def test_successful_run_download_returns_zip(self, dl_client, dl_db):
        client, wm, base = dl_client
        proj, run = _make_run(dl_db, str(wm.get_workspace_path()), "passed")

        resp = client.get(f"/api/runs/{run.id}/download")
        assert resp.status_code == 200, resp.text
        assert resp.headers["content-type"] == "application/zip"

    # 2. ZIP contains repaired source files
    def test_zip_contains_source_files(self, dl_client, dl_db):
        client, wm, base = dl_client
        proj, run = _make_run(dl_db, str(wm.get_workspace_path()), "passed")

        resp = client.get(f"/api/runs/{run.id}/download")
        assert resp.status_code == 200, resp.text

        zf = zipfile.ZipFile(io.BytesIO(resp.content))
        names = zf.namelist()
        assert any(n.endswith(".py") for n in names), f"No .py files in ZIP: {names}"

    # 3. ZIP does NOT contain .env
    def test_zip_excludes_dotenv(self, dl_client, dl_db):
        client, wm, base = dl_client
        proj, run = _make_run(dl_db, str(wm.get_workspace_path()), "passed")

        resp = client.get(f"/api/runs/{run.id}/download")
        assert resp.status_code == 200, resp.text

        zf = zipfile.ZipFile(io.BytesIO(resp.content))
        names = zf.namelist()
        env_files = [n for n in names if ".env" in n.lower() or n.startswith(".env")]
        assert not env_files, f".env files found in ZIP: {env_files}"

    # 4. ZIP does NOT contain database files
    def test_zip_excludes_database_files(self, dl_client, dl_db):
        client, wm, base = dl_client
        proj, run = _make_run(dl_db, str(wm.get_workspace_path()), "passed")

        resp = client.get(f"/api/runs/{run.id}/download")
        assert resp.status_code == 200, resp.text

        zf = zipfile.ZipFile(io.BytesIO(resp.content))
        names = zf.namelist()
        _DB_EXTS = (".db", ".db-shm", ".db-wal")
        db_files = [n for n in names if any(n.endswith(e) for e in _DB_EXTS)]
        assert not db_files, (
            f"Database files found in ZIP: {db_files}"
        )

    # 5. ZIP does NOT contain __pycache__
    def test_zip_excludes_pycache(self, dl_client, dl_db):
        client, wm, base = dl_client
        proj, run = _make_run(dl_db, str(wm.get_workspace_path()), "passed")

        resp = client.get(f"/api/runs/{run.id}/download")
        assert resp.status_code == 200, resp.text

        zf = zipfile.ZipFile(io.BytesIO(resp.content))
        names = zf.namelist()
        cache_files = [n for n in names if "__pycache__" in n or n.endswith(".pyc")]
        assert not cache_files, f"Cache files found in ZIP: {cache_files}"

    # 6. Invalid run_id → 404
    def test_invalid_run_id_returns_404(self, dl_client, dl_db):
        client, wm, base = dl_client
        resp = client.get("/api/runs/nonexistent-run-id-does-not-exist/download")
        assert resp.status_code == 404
        assert "not found" in resp.json()["detail"].lower()

    # 7. Running run → download rejected with 409
    def test_running_run_download_rejected(self, dl_client, dl_db):
        client, wm, base = dl_client
        proj, run = _make_run(dl_db, str(wm.get_workspace_path()), "running")

        resp = client.get(f"/api/runs/{run.id}/download")
        assert resp.status_code == 409
        detail = resp.json()["detail"].lower()
        assert "in progress" in detail or "running" in detail or "complete" in detail

    # 8. Failed run → download rejected with 409
    def test_failed_run_download_rejected(self, dl_client, dl_db):
        client, wm, base = dl_client
        proj, run = _make_run(dl_db, str(wm.get_workspace_path()), "failed")

        resp = client.get(f"/api/runs/{run.id}/download")
        assert resp.status_code == 409
        detail = resp.json()["detail"].lower()
        assert "not available" in detail or "did not complete" in detail or "failed" in detail

    # 9. Path traversal cannot escape workspace
    def test_path_traversal_cannot_escape_workspace(self, dl_client, dl_db, tmp_path):
        """
        Verify that _is_excluded correctly excludes files outside project_root
        by simulating a resolved path that escapes the project root.
        """
        project_root = tmp_path / "project"
        project_root.mkdir()

        # A file legitimately inside the project root
        legit_file = project_root / "main.py"
        legit_file.write_text("pass")
        assert not _is_excluded(legit_file, project_root)

        # A file outside the project root (simulates traversal)
        escaped_file = tmp_path / "secret.txt"
        escaped_file.write_text("SECRET")
        # _is_excluded returns True for any file outside project_root
        assert _is_excluded(escaped_file, project_root)

        # .env always excluded regardless of location
        env_file = project_root / ".env"
        env_file.write_text("KEY=val")
        assert _is_excluded(env_file, project_root)

    # 10. Download response has correct Content-Disposition header
    def test_download_response_headers(self, dl_client, dl_db):
        client, wm, base = dl_client
        proj, run = _make_run(dl_db, str(wm.get_workspace_path()), "passed")

        resp = client.get(f"/api/runs/{run.id}/download")
        assert resp.status_code == 200

        cd = resp.headers.get("content-disposition", "")
        assert "attachment" in cd
        assert f"aegiscode-repaired-{run.id}.zip" in cd

    # 11. Stalled run → download rejected with 409
    def test_stalled_run_download_rejected(self, dl_client, dl_db):
        client, wm, base = dl_client
        proj, run = _make_run(dl_db, str(wm.get_workspace_path()), "stalled")

        resp = client.get(f"/api/runs/{run.id}/download")
        assert resp.status_code == 409
        assert "not available" in resp.json()["detail"].lower() or \
               "did not complete" in resp.json()["detail"].lower()

    # 12. _is_excluded helper covers all exclusion patterns
    def test_is_excluded_helper_patterns(self, tmp_path):
        root = tmp_path / "project"
        root.mkdir()

        # Should be excluded
        excluded_cases = [
            root / ".env",
            root / ".env.production",
            root / "app.db",
            root / "app.db-shm",
            root / "app.db-wal",
            root / "__pycache__" / "main.cpython-311.pyc",
            root / ".git" / "config",
            root / ".pytest_cache" / "v" / "cache" / "lastfailed",
            root / ".ruff_cache" / "0.1.0" / "something",
            root / "main.pyc",
        ]
        # Should NOT be excluded
        included_cases = [
            root / "main.py",
            root / "utils.py",
            root / "README.md",
            root / "tests" / "test_main.py",
            root / "src" / "module" / "helper.py",
        ]

        # Create parent dirs for deeply nested paths
        for p in excluded_cases + included_cases:
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text("x")

        for p in excluded_cases:
            assert _is_excluded(p, root), f"Expected {p} to be excluded"

        for p in included_cases:
            assert not _is_excluded(p, root), f"Expected {p} to be included"
