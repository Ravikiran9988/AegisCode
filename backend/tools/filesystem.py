"""
Filesystem tools — Phase 2.

All tools operate on a WorkspaceManager instance. Paths supplied by
callers (future LLM agents) are validated through ``workspace.safe_path()``
before any filesystem operation occurs.

Security model
--------------
* Callers supply relative paths only.
* ``safe_path()`` resolves and validates that the result stays inside
  the workspace root. Any escape attempt raises PathTraversalError.
* Binary files are rejected for read/write operations that expect text.
* File size is capped at MAX_FILE_SIZE_MB.
* .env and common secret file names are flagged.
* apply_patch uses a pure-Python unified-diff applicator — no shell.
"""

from __future__ import annotations

import re
from pathlib import Path

from pydantic import BaseModel, Field

from backend.core.config import settings
from backend.core.logging import get_logger
from backend.execution.workspace import PathTraversalError, WorkspaceManager

logger = get_logger(__name__)

_MAX_FILE_BYTES = settings.max_file_size_mb * 1024 * 1024
_BINARY_CHUNK = 8192  # bytes to sample when guessing binary
_SENSITIVE_NAMES = frozenset({
    ".env", ".env.local", ".env.production", "secrets.toml",
    "credentials.json", "id_rsa", "id_ed25519",
})
_SKIP_DIRS = frozenset({"__pycache__", ".git", ".venv", "venv", "node_modules", ".mypy_cache"})


# ── Pydantic result models ────────────────────────────────────────────────────

class FileListResult(BaseModel):
    success: bool
    files: list[str] = Field(default_factory=list)
    error: str | None = None


class FileReadResult(BaseModel):
    success: bool
    path: str
    content: str | None = None
    size_bytes: int = 0
    error: str | None = None


class FileWriteResult(BaseModel):
    success: bool
    path: str
    bytes_written: int = 0
    error: str | None = None


class PatchResult(BaseModel):
    success: bool
    path: str
    lines_before: int = 0
    lines_after: int = 0
    error: str | None = None


class ProjectStructure(BaseModel):
    success: bool
    tree: str = ""
    files: list[str] = Field(default_factory=list)
    total_files: int = 0
    error: str | None = None


# ── Tool implementations ──────────────────────────────────────────────────────

def list_files(workspace: WorkspaceManager, pattern: str = "**/*.py") -> FileListResult:
    """
    List files matching *pattern* relative to the project root.

    Returns relative paths (POSIX separators) suitable for passing back
    to read_file / write_file.
    """
    try:
        project = workspace.get_project_path()
        results: list[str] = []
        for path in sorted(project.rglob(pattern)):
            # Skip hidden/internal dirs
            parts = path.relative_to(project).parts
            if any(p in _SKIP_DIRS or p.startswith(".") for p in parts[:-1]):
                continue
            results.append(path.relative_to(project).as_posix())
        logger.debug("list_files: found %d files matching %r", len(results), pattern)
        return FileListResult(success=True, files=results)
    except Exception as exc:
        logger.warning("list_files failed: %s", exc)
        return FileListResult(success=False, error=str(exc))


def read_file(workspace: WorkspaceManager, relative_path: str) -> FileReadResult:
    """
    Read a text file from the workspace.

    Rejects
    -------
    * Paths that escape the workspace.
    * Binary files.
    * Files exceeding MAX_FILE_SIZE_MB.
    * Sensitive credential files.
    """
    try:
        target = workspace.safe_path(relative_path)

        if not target.exists():
            return FileReadResult(
                success=False, path=relative_path,
                error=f"File not found: {relative_path!r}"
            )
        if not target.is_file():
            return FileReadResult(
                success=False, path=relative_path,
                error=f"Not a file: {relative_path!r}"
            )
        if target.name in _SENSITIVE_NAMES:
            return FileReadResult(
                success=False, path=relative_path,
                error=f"Reading sensitive file {target.name!r} is not allowed"
            )

        size = target.stat().st_size
        if size > _MAX_FILE_BYTES:
            return FileReadResult(
                success=False, path=relative_path, size_bytes=size,
                error=f"File too large: {size:,} bytes (limit {settings.max_file_size_mb} MB)"
            )
        if _is_binary(target):
            return FileReadResult(
                success=False, path=relative_path, size_bytes=size,
                error=f"Binary file cannot be read as text: {relative_path!r}"
            )

        content = target.read_text(encoding="utf-8", errors="replace")
        logger.debug("read_file: %s (%d bytes)", relative_path, size)
        return FileReadResult(success=True, path=relative_path, content=content, size_bytes=size)

    except PathTraversalError as exc:
        logger.warning("read_file path traversal attempt: %s", exc)
        return FileReadResult(success=False, path=relative_path, error=str(exc))
    except Exception as exc:
        logger.warning("read_file error for %r: %s", relative_path, exc)
        return FileReadResult(success=False, path=relative_path, error=str(exc))


def write_file(
    workspace: WorkspaceManager,
    relative_path: str,
    content: str,
) -> FileWriteResult:
    """
    Write *content* to a file inside the workspace.

    * Creates intermediate directories if needed.
    * Rejects paths that escape the workspace.
    * Rejects content exceeding MAX_FILE_SIZE_MB.
    * Rejects writes to sensitive credential files.
    """
    try:
        target = workspace.safe_path(relative_path)

        if target.name in _SENSITIVE_NAMES:
            return FileWriteResult(
                success=False, path=relative_path,
                error=f"Writing to {target.name!r} is not allowed"
            )

        encoded = content.encode("utf-8")
        if len(encoded) > _MAX_FILE_BYTES:
            return FileWriteResult(
                success=False,
                path=relative_path,
                error=(
                    f"Content too large: {len(encoded):,} bytes "
                    f"(limit {settings.max_file_size_mb} MB)"
                ),
            )

        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        logger.info("write_file: wrote %d bytes to %s", len(encoded), relative_path)
        return FileWriteResult(success=True, path=relative_path, bytes_written=len(encoded))

    except PathTraversalError as exc:
        logger.warning("write_file path traversal attempt: %s", exc)
        return FileWriteResult(success=False, path=relative_path, error=str(exc))
    except Exception as exc:
        logger.warning("write_file error for %r: %s", relative_path, exc)
        return FileWriteResult(success=False, path=relative_path, error=str(exc))


def apply_patch(
    workspace: WorkspaceManager,
    relative_path: str,
    patch: str,
) -> PatchResult:
    """
    Apply a unified diff *patch* to a file inside the workspace.

    The patch string must be in standard unified diff format (as produced
    by ``git diff`` or ``difflib.unified_diff``).

    Uses a pure-Python patch applicator — no shell, no external tools.
    """
    try:
        target = workspace.safe_path(relative_path)

        if not target.exists():
            return PatchResult(
                success=False, path=relative_path,
                error=f"File not found: {relative_path!r}"
            )

        original = target.read_text(encoding="utf-8", errors="replace")
        lines_before = original.count("\n")

        patched, err = _apply_unified_diff(original, patch)
        if err:
            return PatchResult(success=False, path=relative_path, error=err)

        target.write_text(patched, encoding="utf-8")
        lines_after = patched.count("\n")
        logger.info(
            "apply_patch: %s — %d → %d lines", relative_path, lines_before, lines_after
        )
        return PatchResult(
            success=True,
            path=relative_path,
            lines_before=lines_before,
            lines_after=lines_after,
        )

    except PathTraversalError as exc:
        logger.warning("apply_patch path traversal attempt: %s", exc)
        return PatchResult(success=False, path=relative_path, error=str(exc))
    except Exception as exc:
        logger.warning("apply_patch error for %r: %s", relative_path, exc)
        return PatchResult(success=False, path=relative_path, error=str(exc))


def get_project_structure(workspace: WorkspaceManager) -> ProjectStructure:
    """
    Return a tree-formatted view of the project and a flat file list.

    Hidden directories, __pycache__, .git etc. are excluded.
    """
    try:
        project = workspace.get_project_path()
        files: list[str] = []
        tree_lines: list[str] = []
        _build_tree(project, project, files, tree_lines, prefix="")
        tree_str = "\n".join(tree_lines)
        logger.debug("get_project_structure: %d files", len(files))
        return ProjectStructure(
            success=True,
            tree=tree_str,
            files=files,
            total_files=len(files),
        )
    except Exception as exc:
        return ProjectStructure(success=False, error=str(exc))


# ── Helpers ───────────────────────────────────────────────────────────────────

def _is_binary(path: Path) -> bool:
    """Heuristic: sample the first 8 KB and look for null bytes."""
    try:
        chunk = path.read_bytes()[:_BINARY_CHUNK]
        return b"\x00" in chunk
    except OSError:
        return False


def _build_tree(
    root: Path,
    current: Path,
    files: list[str],
    lines: list[str],
    prefix: str,
) -> None:
    try:
        entries = sorted(current.iterdir(), key=lambda p: (p.is_file(), p.name))
    except PermissionError:
        return

    filtered = [
        e for e in entries
        if e.name not in _SKIP_DIRS and not e.name.startswith(".")
    ]

    for i, entry in enumerate(filtered):
        is_last = i == len(filtered) - 1
        connector = "└── " if is_last else "├── "
        lines.append(f"{prefix}{connector}{entry.name}")

        if entry.is_file():
            files.append(entry.relative_to(root).as_posix())
        elif entry.is_dir():
            extension = "    " if is_last else "│   "
            _build_tree(root, entry, files, lines, prefix + extension)


# ── Pure-Python unified-diff applicator ───────────────────────────────────────

_HUNK_RE = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@", re.MULTILINE)


def _apply_unified_diff(original: str, patch: str) -> tuple[str, str | None]:
    """
    Apply a unified diff to *original* text.

    Returns ``(patched_text, None)`` on success or ``("", error_message)`` on failure.

    Supports standard hunks (lines starting with ' ', '+', '-').
    Does NOT support binary patches or extended git diff headers.
    """
    original_lines = original.splitlines(keepends=True)
    result = list(original_lines)
    offset = 0  # cumulative line shift as hunks are applied

    hunk_matches = list(_HUNK_RE.finditer(patch))
    if not hunk_matches:
        return original, "No hunks found in patch"

    for i, match in enumerate(hunk_matches):
        old_start = int(match.group(1)) - 1   # 0-indexed
        old_count = int(match.group(2) or "1")

        # Slice out just this hunk's content lines
        body_start = match.end()
        body_end = hunk_matches[i + 1].start() if i + 1 < len(hunk_matches) else len(patch)
        body = patch[body_start:body_end]

        # Skip the trailing newline / blank line that separates hunks
        hunk_lines_raw = body.splitlines(keepends=True)

        new_lines: list[str] = []
        for line in hunk_lines_raw:
            if line.startswith("+"):
                new_lines.append(line[1:])
            elif line.startswith("-"):
                pass  # removed
            elif line.startswith(" "):
                new_lines.append(line[1:])
            elif line.startswith("\\"):
                pass  # "No newline at end of file" marker
            # blank / header lines (like "diff --git", "---", "+++") are skipped

        adjusted_start = old_start + offset

        # Bounds check
        if adjusted_start < 0 or adjusted_start + old_count > len(result):
            return "", (
                f"Patch hunk @@ -{old_start + 1},{old_count} is out of bounds "
                f"for file with {len(result)} lines"
            )

        result[adjusted_start: adjusted_start + old_count] = new_lines
        offset += len(new_lines) - old_count

    return "".join(result), None
