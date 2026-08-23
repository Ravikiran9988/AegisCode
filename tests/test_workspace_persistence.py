"""
Tests for workspace archive persistence and automatic re-hydration.

Verifies:
1. upload -> repair (normal flow)
2. missing workspace on disk -> automatic re-hydration from database archive -> repair succeeds
3. missing workspace with no archive data -> raises WorkspaceError (HTTP 500)
4. invalid/corrupted archive data -> raises validation error
5. repeated workspace restoration (idempotent / clean recovery)
6. path traversal attack in archive is blocked during restoration
"""

from __future__ import annotations

import io
import os
import shutil
import stat
import zipfile
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.database.models import Base, Project, Run
from backend.database.session import get_db
from backend.execution.workspace import (
    PathTraversalError,
    WorkspaceError,
    WorkspaceManager,
    ZipValidationError,
)
from backend.main import create_app


def _safe_rmtree(path: Path) -> None:
    def _remove_readonly(func, p, _exc_info):
        os.chmod(p, stat.S_IWRITE)
        func(p)

    if path.exists():
        shutil.rmtree(path, onerror=_remove_readonly)


def _create_sample_zip() -> bytes:
    """Create a minimal valid Python project ZIP with calc.py and test_calc.py."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(
            "calc.py",
            "def add(a: int, b: int) -> int:\n    return a - b\n",
        )
        zf.writestr(
            "test_calc.py",
            "from calc import add\n\ndef test_add():\n    assert add(2, 3) == 5\n",
        )
    return buf.getvalue()


def _create_traversal_zip() -> bytes:
    """Create a ZIP with path traversal attempt."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(
            "../../evil.py",
            "print('evil')",
        )
    return buf.getvalue()


@pytest.fixture
def test_app_and_db(tmp_path: Path):
    db_path = tmp_path / "test_workspace_persist.db"
    engine = create_engine(f"sqlite:///{db_path}", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app = create_app()
    app.dependency_overrides[get_db] = override_get_db
    app.state.db_session_factory = TestingSessionLocal

    db = TestingSessionLocal()
    yield app, db, TestingSessionLocal
    db.close()


class TestWorkspacePersistenceAndRestoration:
    """Unit and Integration tests for workspace persistence and automatic re-hydration."""

    def test_workspace_manager_from_id_restores_missing_workspace(self, tmp_path: Path):
        """When workspace directory is missing on disk, from_id() restores from archive."""
        zip_bytes = _create_sample_zip()
        wid = "test-restore-uuid-1"

        # Directory does not exist yet
        target = tmp_path / f"run_{wid}"
        assert not target.exists()

        # from_id with archive_data should create directory and extract files
        wm = WorkspaceManager.from_id(wid, base_dir=tmp_path, archive_data=zip_bytes)
        try:
            assert wm.validate_workspace()
            assert (wm.get_project_path() / "calc.py").exists()
            assert (wm.get_project_path() / "test_calc.py").exists()
            assert (wm.get_project_path() / ".git").exists()
        finally:
            wm.cleanup()

    def test_workspace_manager_from_id_missing_no_archive_fails(self, tmp_path: Path):
        """When workspace directory is missing and no archive is provided, raise WorkspaceError."""
        wid = "test-restore-uuid-missing"
        with pytest.raises(WorkspaceError, match="does not exist"):
            WorkspaceManager.from_id(wid, base_dir=tmp_path, archive_data=None)

    def test_workspace_manager_from_id_corrupted_archive_fails(self, tmp_path: Path):
        """When workspace directory is missing and archive is corrupted, raise error."""
        wid = "test-restore-uuid-corrupt"
        with pytest.raises((WorkspaceError, ZipValidationError)):
            WorkspaceManager.from_id(wid, base_dir=tmp_path, archive_data=b"not a valid zip")

    def test_workspace_manager_from_id_traversal_archive_fails(self, tmp_path: Path):
        """When workspace restore is attempted with path traversal zip, raise PathTraversalError."""
        wid = "test-restore-uuid-traversal"
        traversal_zip = _create_traversal_zip()
        with pytest.raises((PathTraversalError, ZipValidationError, WorkspaceError)):
            WorkspaceManager.from_id(wid, base_dir=tmp_path, archive_data=traversal_zip)

    def test_workspace_repeated_restoration(self, tmp_path: Path):
        """Workspace can be deleted and restored multiple times cleanly."""
        zip_bytes = _create_sample_zip()
        wid = "test-repeated-restore-uuid"

        # First restore
        wm1 = WorkspaceManager.from_id(wid, base_dir=tmp_path, archive_data=zip_bytes)
        assert wm1.validate_workspace()

        # Wipe directory from disk (simulating container restart)
        wm1.cleanup()
        assert not (tmp_path / f"run_{wid}").exists()

        # Second restore
        wm2 = WorkspaceManager.from_id(wid, base_dir=tmp_path, archive_data=zip_bytes)
        try:
            assert wm2.validate_workspace()
            assert (wm2.get_project_path() / "calc.py").exists()
        finally:
            wm2.cleanup()


class TestEndToEndWorkspaceAutoRestorationAPI:
    """Integration tests testing the full upload -> disk wipe -> run -> repair flow via API."""

    def test_upload_disk_wipe_and_start_repair_auto_restores(self, test_app_and_db):
        """
        Uploads a project, deletes the physical workspace folder from disk,
        then calls create_run and start_repair_loop to verify transparent auto-restoration.
        """
        app, db, _ = test_app_and_db
        client = TestClient(app)
        zip_bytes = _create_sample_zip()

        # 1. Upload project
        upload_resp = client.post(
            "/api/projects/upload",
            files={"file": ("calc_project.zip", zip_bytes, "application/zip")},
            headers={"X-Guest-Session-ID": "guest-persist-test-1"},
        )
        assert upload_resp.status_code == 201
        data = upload_resp.json()
        project_id = data["project_id"]

        # Verify project record has archive_data in database
        project = db.get(Project, project_id)
        assert project is not None
        assert project.archive_data is not None
        assert len(project.archive_data) == len(zip_bytes)

        # 2. Simulate container restart / disk wipe
        ws_path = Path(project.workspace_path)
        _safe_rmtree(ws_path)
        assert not ws_path.exists()

        # 3. Create run (triggers initial pytest via rehydrated workspace)
        run_resp = client.post(
            "/api/runs",
            json={"project_id": project_id, "max_iterations": 3},
            headers={"X-Guest-Session-ID": "guest-persist-test-1"},
        )
        assert run_resp.status_code == 201
        run_id = run_resp.json()["run_id"]

        # Workspace directory should now be restored on disk
        assert ws_path.exists()
        assert (ws_path / "project" / "calc.py").exists()

        # 4. Wipe disk AGAIN before repair loop
        _safe_rmtree(ws_path)
        assert not ws_path.exists()

        # 5. Start repair loop (POST /api/runs/{run_id}/repair)
        with patch("backend.api.runs.run_repair_workflow"):
            repair_resp = client.post(
                f"/api/runs/{run_id}/repair",
                headers={"X-Guest-Session-ID": "guest-persist-test-1"},
            )
            assert repair_resp.status_code == 202
            # Verify workspace was re-hydrated on disk before graph dispatch
            assert ws_path.exists()
            assert (ws_path / "project" / "calc.py").exists()

        # Clean up workspace
        _safe_rmtree(ws_path)

    def test_repaired_project_download_auto_restores_if_disk_wiped(self, test_app_and_db):
        """When downloading project after disk wipe, it auto-restores workspace from archive."""
        app, db, _ = test_app_and_db
        client = TestClient(app)
        zip_bytes = _create_sample_zip()

        # 1. Upload project
        upload_resp = client.post(
            "/api/projects/upload",
            files={"file": ("calc_proj.zip", zip_bytes, "application/zip")},
            headers={"X-Guest-Session-ID": "guest-download-test-1"},
        )
        project_id = upload_resp.json()["project_id"]

        # 2. Create Run and set status to passed
        run = Run(
            project_id=project_id,
            guest_id=db.get(Project, project_id).guest_id,
            status="passed",
        )
        db.add(run)
        db.commit()

        # 3. Delete workspace from disk
        project = db.get(Project, project_id)
        ws_path = Path(project.workspace_path)
        _safe_rmtree(ws_path)
        assert not ws_path.exists()

        # 4. Download project
        dl_resp = client.get(
            f"/api/runs/{run.id}/download",
            headers={"X-Guest-Session-ID": "guest-download-test-1"},
        )
        assert dl_resp.status_code == 200
        assert dl_resp.headers["content-type"] == "application/zip"
        assert len(dl_resp.content) > 0

        # Clean up workspace
        _safe_rmtree(ws_path)

    def test_init_db_adds_archive_data_column_if_missing(self, tmp_path: Path):
        """Verify that init_db safely alters older database schemas missing archive_data."""
        from sqlalchemy import inspect, text

        from backend.database.init_db import init_db

        # Create a database with old projects table without archive_data
        db_path = tmp_path / "legacy.db"
        test_engine = create_engine(f"sqlite:///{db_path}")
        with test_engine.begin() as conn:
            conn.execute(
                text(
                    """
                    CREATE TABLE projects (
                        id VARCHAR PRIMARY KEY,
                        name VARCHAR(255) NOT NULL,
                        original_filename VARCHAR(512) NOT NULL,
                        workspace_path VARCHAR(1024) NOT NULL,
                        file_count INTEGER DEFAULT 0,
                        size_bytes INTEGER DEFAULT 0,
                        uploaded_at DATETIME
                    )
                    """
                )
            )

        inspector_before = inspect(test_engine)
        cols_before = [c["name"] for c in inspector_before.get_columns("projects")]
        assert "archive_data" not in cols_before

        with patch("backend.database.init_db.engine", test_engine):
            init_db()

        inspector_after = inspect(test_engine)
        cols_after = [c["name"] for c in inspector_after.get_columns("projects")]
        assert "archive_data" in cols_after

