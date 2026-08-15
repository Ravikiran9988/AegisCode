"""
Git tools — Phase 2.

Provides:
  init_repo(project_path)   — create initial commit before any changes
  get_git_diff(workspace)   — return diff of uncommitted modifications

Design
------
* Uses GitPython (already in requirements.txt) — no subprocess shell.
* If the uploaded project is NOT already a git repo, a temporary repo
  is initialised and an initial commit is made. This allows us to
  produce a clean before/after diff after the Coder agent makes changes.
* We never touch or expose the host's actual Git repositories.
* Diff output is bounded (same MAX_OUTPUT_SIZE_MB as pytest runner).
"""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, Field

from backend.core.config import settings
from backend.core.logging import get_logger
from backend.execution.workspace import WorkspaceManager

logger = get_logger(__name__)

_MAX_DIFF_BYTES = settings.max_output_size_mb * 1024 * 1024


class GitDiff(BaseModel):
    """Structured result from get_git_diff()."""

    success: bool
    has_changes: bool = False
    diff: str = ""
    changed_files: list[str] = Field(default_factory=list)
    additions: int = 0
    deletions: int = 0
    error: str | None = None


def init_repo(project_path: Path) -> None:
    """
    Ensure *project_path* is a git repository with an initial commit.

    If a ``.git`` directory already exists, this is a no-op (we don't
    alter an existing repository's history).

    Call this immediately after extraction, before any agent makes changes.
    """
    try:
        import git  # gitpython

        if (project_path / ".git").exists():
            logger.debug("init_repo: repo already exists at %s", project_path)
            return

        logger.info("init_repo: initialising temporary git repo at %s", project_path)
        with git.Repo.init(project_path) as repo:
            # Configure a throwaway identity so git commit doesn't fail
            with repo.config_writer() as cfg:
                cfg.set_value("user", "name", "AegisCode")
                cfg.set_value("user", "email", "aegiscode@local")

            # Stage everything and make an initial commit
            repo.git.add(A=True)
            try:
                repo.index.commit("Initial state — pre-repair snapshot")
                logger.info("init_repo: initial commit created")
            except Exception as exc:
                # Empty repo (no files) — non-fatal
                logger.debug("init_repo: initial commit skipped: %s", exc)

    except ImportError:
        logger.warning("gitpython not installed — git diff will be unavailable")
    except Exception as exc:
        # Git errors must never crash the main workflow
        logger.warning("init_repo failed (non-fatal): %s", exc)


def get_git_diff(workspace: WorkspaceManager) -> GitDiff:
    """
    Return the unified diff of all uncommitted changes in the project.

    Should be called after the Coder agent has made modifications.

    Returns
    -------
    GitDiff
        Structured diff with file list, addition/deletion counts, and
        the full unified diff text.
    """
    try:
        import git

        project = workspace.get_project_path()

        if not (project / ".git").exists():
            return GitDiff(
                success=False,
                error=(
                    "Project is not a git repository. "
                    "Call init_repo() before making changes."
                ),
            )

        with git.Repo(project) as repo:
            untracked = repo.untracked_files
            additions = 0
            deletions = 0

            # Get unified diff (working tree vs HEAD)
            try:
                diff_text = repo.git.diff("HEAD", "--unified=3")
                changed_raw = repo.git.diff("HEAD", "--name-only").splitlines()
            except Exception:
                diff_text = ""
                changed_raw = []

            changed_files: list[str] = [
                f for f in changed_raw
                if not f.startswith("__pycache__") and not f.endswith(".pyc")
            ]

            # Untracked files count as changed
            for f in untracked:
                if not f.startswith("__pycache__") and not f.endswith(".pyc"):
                    changed_files.append(f)

            if len(diff_text.encode()) > _MAX_DIFF_BYTES:
                diff_text = diff_text[: _MAX_DIFF_BYTES].decode("utf-8", errors="replace")
                diff_text += "\n... [DIFF TRUNCATED] ..."

            # Count additions/deletions
            for line in diff_text.splitlines():
                if line.startswith("+") and not line.startswith("+++"):
                    additions += 1
                elif line.startswith("-") and not line.startswith("---"):
                    deletions += 1

            has_changes = bool(changed_files or diff_text.strip())
            logger.info(
                "get_git_diff: %d changed files, +%d/-%d lines",
                len(changed_files), additions, deletions,
            )

            return GitDiff(
                success=True,
                has_changes=has_changes,
                diff=diff_text,
                changed_files=sorted(set(changed_files)),
                additions=additions,
                deletions=deletions,
            )

    except ImportError:
        return GitDiff(success=False, error="gitpython is not installed")
    except Exception as exc:
        logger.warning("get_git_diff failed: %s", exc)
        return GitDiff(success=False, error=str(exc))
