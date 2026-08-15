"""
Workspace Manager — Phase 2.

Each repair run gets a unique, isolated workspace on disk:

    workspaces/
    └── run_<uuid>/
        └── project/       ← extracted Python project lives here

Security model
--------------
* Workspace IDs are UUIDs — never user-supplied.
* All resolved paths are verified to be under the workspace root.
* ZIP extraction rejects path-traversal entries (Zip Slip) before
  touching the filesystem.
* Symlinks within the project are allowed but followed only inside
  the workspace; links pointing outside are rejected.
* The workspace is cleaned up after the run, regardless of outcome.
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

# Maximum number of files allowed inside a single ZIP / workspace
_MAX_FILES = settings.max_workspace_files
# Maximum total *uncompressed* bytes (10 × upload limit as a safety buffer)
_MAX_UNCOMPRESSED_BYTES = settings.max_upload_size_mb * 1024 * 1024 * 10


# ── Exceptions ────────────────────────────────────────────────────────────────

class WorkspaceError(Exception):
    """Base class for workspace-related errors."""


class ZipValidationError(WorkspaceError):
    """Raised when the uploaded ZIP is invalid or dangerous."""


class PathTraversalError(WorkspaceError):
    """Raised when a path attempts to escape the workspace."""


# ── ZIP validation ─────────────────────────────────────────────────────────────

def validate_zip(data: bytes) -> None:
    """
    Validate a ZIP archive before extraction.

    Checks performed
    ----------------
    1. Upload size limit (raw bytes).
    2. Well-formed ZIP (not a bomb / corrupt file).
    3. File count limit.
    4. Total uncompressed size limit (zip-bomb protection).
    5. Path traversal (Zip Slip) — absolute paths and ``..`` components.
    6. Windows device paths (e.g. ``C:\\``).
    """
    max_files = settings.max_workspace_files
    max_uncompressed = settings.max_upload_size_mb * 1024 * 1024 * 10

    max_bytes = settings.max_upload_size_mb * 1024 * 1024
    if len(data) > max_bytes:
        raise ZipValidationError(
            f"Upload size {len(data):,} bytes exceeds limit of "
            f"{settings.max_upload_size_mb} MB"
        )

    try:
        with zipfile.ZipFile.__new__(zipfile.ZipFile) as zf:
            import io
            zf = zipfile.ZipFile(io.BytesIO(data), "r")
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
        # Reject absolute POSIX paths
        if name.startswith("/"):
            raise ZipValidationError(
                f"ZIP entry has absolute path: {name!r}"
            )
        # Reject Windows absolute paths  (e.g. C:\, D:/)
        if len(name) >= 2 and name[1] == ":" and name[2:3] in ("/", "\\"):
            raise ZipValidationError(
                f"ZIP entry has Windows absolute path: {name!r}"
            )
        # Reject traversal components
        parts = name.replace("\\", "/").split("/")
        if ".." in parts:
            raise ZipValidationError(
                f"ZIP entry contains path traversal: {name!r}"
            )

    logger.debug("ZIP validation passed: %d entries, %d bytes uncompressed",
                 len(entries), total_uncompressed)


# ── Workspace Manager ─────────────────────────────────────────────────────────

class WorkspaceManager:
    """
    Manages the lifecycle of a single repair-run workspace.

    Usage
    -----
        wm = WorkspaceManager.create()
        project_path = wm.extract_project(zip_bytes)
        safe_path = wm.safe_path("src/calculator.py")   # validated
        wm.cleanup()
    """

    def __init__(self, workspace_id: str, base_dir: Path | None = None) -> None:
        self.workspace_id: str = workspace_id
        self._base_dir: Path = (base_dir or settings.workspace_path).resolve()
        self._workspace_root: Path = self._base_dir / f"run_{workspace_id}"
        self._project_path: Path = self._workspace_root / "project"

    # ── Factory ────────────────────────────────────────────────────────────────

    @classmethod
    def create(cls, base_dir: Path | None = None) -> WorkspaceManager:
        """Create a new workspace with a fresh UUID and create directories."""
        workspace_id = str(uuid.uuid4())
        wm = cls(workspace_id, base_dir)
        wm._workspace_root.mkdir(parents=True, exist_ok=True)
        wm._project_path.mkdir(parents=True, exist_ok=True)
        logger.info("Workspace created: %s", wm._workspace_root)
        return wm

    @classmethod
    def from_id(cls, workspace_id: str, base_dir: Path | str | None = None) -> WorkspaceManager:
        """Re-attach to an existing workspace directory by UUID."""
        base = Path(base_dir or settings.workspace_path)
        target = base / f"run_{workspace_id}"

        if not target.exists():
            raise WorkspaceError(f"Workspace directory {target} does not exist")

        wm = cls(workspace_id=workspace_id, base_dir=base)
        wm._workspace_root = target
        return wm

    @classmethod
    def from_project_path(cls, project_path: Path | str) -> WorkspaceManager:
        """Re-attach to an existing workspace directory using the project_path."""
        p = Path(project_path).resolve()
        ws_root = p.parent if p.name == "project" else p
        ws_id = ws_root.name.replace("run_", "")
        base = ws_root.parent

        wm = cls(workspace_id=ws_id, base_dir=base)
        wm._workspace_root = ws_root
        return wm

    # ── Public API ─────────────────────────────────────────────────────────────

    def extract_project(self, zip_data: bytes) -> Path:
        """
        Validate and extract a ZIP archive into the project directory.

        Returns the effective project root (detects single top-level
        directory and unwraps it automatically).

        Raises
        ------
        ZipValidationError  — on dangerous or oversized archives.
        WorkspaceError      — on extraction failures.
        """
        import io

        validate_zip(zip_data)

        try:
            with zipfile.ZipFile(io.BytesIO(zip_data), "r") as zf:
                # --- secondary safety check during extraction ---
                for entry in zf.infolist():
                    target = (self._project_path / entry.filename).resolve()
                    if not str(target).startswith(str(self._project_path)):
                        raise PathTraversalError(
                            f"ZIP entry would escape workspace: {entry.filename!r}"
                        )
                zf.extractall(self._project_path)

        except (zipfile.BadZipFile, OSError) as exc:
            raise WorkspaceError(f"Extraction failed: {exc}") from exc

        # Unwrap single top-level directory
        effective_root = self._detect_project_root(self._project_path)
        logger.info("Project extracted to %s", effective_root)
        return effective_root

    def validate_workspace(self) -> bool:
        """Return True if the workspace directories exist and are accessible."""
        return self._workspace_root.exists() and self._project_path.exists()

    def get_workspace_path(self) -> Path:
        return self._workspace_root

    def get_project_path(self) -> Path:
        """Return the project directory (where Python files live)."""
        # Return effective project root if it was set after extraction
        effective = self._workspace_root / "project_root"
        if effective.exists():
            target = effective.read_text(encoding="utf-8").strip()
            p = Path(target)
            if p.exists():
                return p
        return self._project_path

    def set_project_root(self, path: Path) -> None:
        """Record the effective project root for later retrieval."""
        (self._workspace_root / "project_root").write_text(
            str(path), encoding="utf-8"
        )

    def safe_path(self, relative: str) -> Path:
        """
        Resolve ``relative`` within the project directory and verify
        it does not escape the workspace.

        Raises
        ------
        PathTraversalError  — if the resolved path escapes the project root.
        """
        project_root = self.get_project_path()
        # Normalise separators, strip leading slashes so callers can't
        # accidentally pass an absolute path
        clean = relative.lstrip("/\\").replace("\\", "/")
        target = (project_root / clean).resolve()

        workspace_str = str(self._workspace_root.resolve())
        if not str(target).startswith(workspace_str):
            raise PathTraversalError(
                f"Path {relative!r} would escape the workspace"
            )
        return target

    def cleanup(self) -> None:
        """Delete the entire workspace directory tree."""
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

    # ── Helpers ────────────────────────────────────────────────────────────────

    @staticmethod
    def _detect_project_root(extracted_dir: Path) -> Path:
        """
        If the ZIP contained exactly one top-level directory (common for
        GitHub-style archives), return that directory as the project root.
        Otherwise return the extraction directory itself.
        """
        entries = [e for e in extracted_dir.iterdir()]
        if len(entries) == 1 and entries[0].is_dir():
            return entries[0]
        return extracted_dir

    # ── Context manager support ────────────────────────────────────────────────

    def __enter__(self) -> WorkspaceManager:
        return self

    def __exit__(self, *_: object) -> None:
        self.cleanup()

    def __repr__(self) -> str:
        return f"<WorkspaceManager id={self.workspace_id!r} path={self._workspace_root}>"
