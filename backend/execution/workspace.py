"""
Workspace Manager — Phase 2.

Each repair run gets a unique, isolated workspace on disk.
"""

from __future__ import annotations

import os
import shutil
import uuid
import zipfile
from pathlib import Path

from backend.core.config import settings
from backend.core.logging import get_logger

logger = get_logger(__name__)

_MAX_FILES = settings.max_workspace_files
_MAX_UNCOMPRESSED_BYTES = settings.max_upload_size_mb * 1024 * 1024 * 10


class WorkspaceError(Exception):
    """Base class for workspace-related errors."""


class ZipValidationError(WorkspaceError):
    """Raised when the uploaded ZIP is invalid or dangerous."""


class PathTraversalError(WorkspaceError):
    """Raised when a path attempts to escape the workspace."""


def _is_within(path: Path, root: Path) -> bool:
    """Return True only when path is root or a descendant of root."""
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False


def validate_zip(data: bytes) -> None:
    """Validate a ZIP archive before extraction."""
    max_files = settings.max_workspace_files
    max_uncompressed = settings.max_upload_size_mb * 1024 * 1024 * 10
    max_bytes = settings.max_upload_size_mb * 1024 * 1024

    if len(data) > max_bytes:
        raise ZipValidationError(
            f"Upload size {len(data):,} bytes exceeds limit of "
            f"{settings.max_upload_size_mb} MB"
        )

    try:
        import io
        with zipfile.ZipFile(io.BytesIO(data), "r") as zf:
            entries = zf.infolist()
    except zipfile.BadZipFile as exc:
        raise ZipValidationError(f"Invalid or corrupt ZIP file: {exc}") from exc

    if len(entries) > max_files:
        raise ZipValidationError(
            f"ZIP contains {len(entries)} files; limit is {max_files}"
        )

    total_uncompressed = 0
    for entry in entries:
        total_uncompressed += entry.file_size
        if total_uncompressed > max_uncompressed:
            raise ZipValidationError(
                f"Total uncompressed size exceeds "
                f"{max_uncompressed // (1024 * 1024)} MB"
            )

        name = entry.filename
        if name.startswith("/"):
            raise ZipValidationError(f"ZIP entry has absolute path: {name!r}")
        if len(name) >= 2 and name[1] == ":" and name[2:3] in ("/", "\\"):
            raise ZipValidationError(
                f"ZIP entry has Windows absolute path: {name!r}"
            )
        parts = name.replace("\\", "/").split("/")
        if ".." in parts:
            raise ZipValidationError(
                f"ZIP entry contains path traversal: {name!r}"
            )

    logger.debug(
        "ZIP validation passed: %d entries, %d bytes uncompressed",
        len(entries),
        total_uncompressed,
    )


class WorkspaceManager:
    """Manage the lifecycle of a single repair-run workspace."""

    def __init__(self, workspace_id: str, base_dir: Path | None = None) -> None:
        self.workspace_id = workspace_id
        self._base_dir = (base_dir or settings.workspace_path).resolve()
        self._workspace_root = self._base_dir / f"run_{workspace_id}"
        self._project_path = self._workspace_root / "project"

    @classmethod
    def create(cls, base_dir: Path | None = None) -> "WorkspaceManager":
        workspace_id = str(uuid.uuid4())
        wm = cls(workspace_id, base_dir)
        wm._workspace_root.mkdir(parents=True, exist_ok=True)
        wm._project_path.mkdir(parents=True, exist_ok=True)
        logger.info("Workspace created: %s", wm._workspace_root)
        return wm

    @classmethod
    def from_id(
        cls, workspace_id: str, base_dir: Path | str | None = None
    ) -> "WorkspaceManager":
        base = Path(base_dir or settings.workspace_path).resolve()
        target = base / f"run_{workspace_id}"
        if not target.exists() or not _is_within(target, base):
            raise WorkspaceError(f"Workspace directory {target} does not exist")
        wm = cls(workspace_id=workspace_id, base_dir=base)
        wm._workspace_root = target
        return wm

    @classmethod
    def from_project_path(cls, project_path: Path | str) -> "WorkspaceManager":
        p = Path(project_path).resolve()
        ws_root = p.parent if p.name == "project" else p
        ws_id = ws_root.name.replace("run_", "", 1)
        base = ws_root.parent.resolve()
        if not _is_within(ws_root, base):
            raise WorkspaceError("Project path is outside workspace base directory")
        wm = cls(workspace_id=ws_id, base_dir=base)
        wm._workspace_root = ws_root
        return wm

    def extract_project(self, zip_data: bytes) -> Path:
        """Validate and safely extract a ZIP archive into the project directory."""
        import io

        validate_zip(zip_data)
        self._project_path.mkdir(parents=True, exist_ok=True)
        try:
            with zipfile.ZipFile(io.BytesIO(zip_data), "r") as zf:
                project_root = self._project_path.resolve()
                for entry in zf.infolist():
                    target = (self._project_path / entry.filename).resolve()
                    if not _is_within(target, project_root):
                        raise PathTraversalError(
                            f"ZIP entry would escape workspace: {entry.filename!r}"
                        )
                zf.extractall(self._project_path)
        except (zipfile.BadZipFile, OSError) as exc:
            raise WorkspaceError(f"Extraction failed: {exc}") from exc

        effective_root = self._detect_project_root(self._project_path)
        logger.info("Project extracted to %s", effective_root)
        return effective_root

    def validate_workspace(self) -> bool:
        return self._workspace_root.exists() and self._project_path.exists()

    def get_workspace_path(self) -> Path:
        return self._workspace_root

    def get_project_path(self) -> Path:
        effective = self._workspace_root / "project_root"
        if effective.exists():
            target = effective.read_text(encoding="utf-8").strip()
            p = Path(target).resolve()
            if _is_within(p, self._workspace_root) and p.exists():
                return p
        return self._project_path

    def set_project_root(self, path: Path) -> None:
        resolved = path.resolve()
        if not _is_within(resolved, self._workspace_root):
            raise PathTraversalError("Project root must remain inside the workspace")
        (self._workspace_root / "project_root").write_text(
            str(resolved), encoding="utf-8"
        )

    def safe_path(self, relative: str) -> Path:
        project_root = self.get_project_path().resolve()
        clean = relative.lstrip("/\\").replace("\\", "/")
        target = (project_root / clean).resolve()
        if not _is_within(target, self._workspace_root):
            raise PathTraversalError(
                f"Path {relative!r} would escape the workspace"
            )
        return target

    def cleanup(self) -> None:
        if self._workspace_root.exists():
            def _remove_readonly(func, path, exc_info):
                import stat
                os.chmod(path, stat.S_IWRITE)
                try:
                    func(path)
                except Exception:
                    pass
            shutil.rmtree(self._workspace_root, onerror=_remove_readonly)
            logger.info("Workspace cleaned up: %s", self._workspace_root)

    @staticmethod
    def _detect_project_root(extracted_dir: Path) -> Path:
        entries = [e for e in extracted_dir.iterdir()]
        if len(entries) == 1 and entries[0].is_dir():
            return entries[0]
        return extracted_dir

    def __enter__(self) -> "WorkspaceManager":
        return self

    def __exit__(self, *_: object) -> None:
        self.cleanup()

    def __repr__(self) -> str:
        return f"<WorkspaceManager id={self.workspace_id!r} path={self._workspace_root}>"
