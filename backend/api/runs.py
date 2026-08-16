"""
Runs API — Phase 2 / Phase 6.

POST /api/runs                    — create a run and execute initial pytest
GET  /api/runs/{run_id}           — get run status and metadata
GET  /api/runs/{run_id}/results   — get detailed test results
GET  /api/runs/{run_id}/download  — download repaired project as ZIP

Phase 2: runs execute the test suite only — no LLM agents yet.
LangGraph agents are wired in Phase 4.
"""

from __future__ import annotations

import fnmatch
import io
import zipfile
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from starlette.responses import StreamingResponse

from backend.core.config import settings
from backend.core.logging import get_logger
from backend.database.models import Event, Iteration, Project, Run
from backend.database.persistence import upsert_iteration
from backend.database.session import get_db
from backend.execution.local import LocalExecutionBackend
from backend.execution.workspace import WorkspaceError, WorkspaceManager
from backend.graph.graph import run_repair_workflow
from backend.llm.factory import get_llm_provider
from backend.tools.pytest_runner import TestResult

logger = get_logger(__name__)

# ── Security exclusion rules for the download ZIP ─────────────────────────────

# Directory/component names that are always excluded from the download ZIP
_EXCLUDED_DIR_COMPONENTS: frozenset[str] = frozenset({
    ".git",
    "__pycache__",
    ".pytest_cache",
    ".ruff_cache",
    ".mypy_cache",
    ".tox",
    ".venv",
    "venv",
    "node_modules",
})

# Glob patterns matched against the *filename* (not full path)
_EXCLUDED_FILENAME_PATTERNS: tuple[str, ...] = (
    ".env",
    ".env.*",
    "*.db",
    "*.db-shm",
    "*.db-wal",
    "*.pyc",
    "*.pyo",
    "secrets",
    "credentials",
    ".DS_Store",
    "Thumbs.db",
)


def _is_excluded(file_path: Path, project_root: Path) -> bool:
    """
    Return True if *file_path* should be excluded from the download ZIP.

    Checks
    ------
    1. Any path component matches an excluded directory name.
    2. The filename matches an excluded glob pattern.
    """
    try:
        rel = file_path.relative_to(project_root)
    except ValueError:
        # Path is outside the project root — always exclude
        return True

    # Check every component of the relative path
    for part in rel.parts:
        if part in _EXCLUDED_DIR_COMPONENTS:
            return True

    # Check filename against glob patterns
    fname = file_path.name
    for pattern in _EXCLUDED_FILENAME_PATTERNS:
        if fnmatch.fnmatch(fname, pattern):
            return True

    return False

router = APIRouter(prefix=f"{settings.api_prefix}/runs", tags=["runs"])


# ── Request / Response schemas ────────────────────────────────────────────────

class RunCreateRequest(BaseModel):
    project_id: str = Field(description="ID of an uploaded project")
    max_iterations: int = Field(default=5, ge=1, le=10)


class RunResponse(BaseModel):
    run_id: str
    project_id: str
    status: str
    max_iterations: int
    current_iteration: int
    created_at: str
    started_at: str | None = None
    finished_at: str | None = None
    final_summary: str | None = None
    initial_test_results: dict | None = None


class TestResultSchema(BaseModel):
    passed: int
    failed: int
    errors: int
    skipped: int
    exit_code: int
    success: bool
    duration: float
    stdout: str
    stderr: str


class IterationSchema(BaseModel):
    iteration_number: int
    tests_passed: int | None
    tests_failed: int | None
    approved: bool | None
    duration_seconds: float | None
    test_results: dict | None
    architecture_plan: dict | None = None
    code_changes: list | dict | None = None
    review_result: dict | None = None


class RunResultsResponse(BaseModel):
    run_id: str
    status: str
    iterations: list[IterationSchema]
    final_summary: str | None


# ── Helpers ───────────────────────────────────────────────────────────────────

def _dt(dt: datetime | None) -> str | None:
    return dt.isoformat() if dt else None


def _get_run_or_404(run_id: str, db: Session) -> Run:
    run = db.get(Run, run_id)
    if not run:
        raise HTTPException(status_code=404, detail=f"Run {run_id!r} not found")
    return run


def _emit_event(
    db: Session,
    run_id: str,
    agent: str,
    event_type: str,
    payload: dict | None = None,
    iteration: int | None = None,
) -> None:
    ev = Event(
        run_id=run_id,
        agent=agent,
        event_type=event_type,
        payload=payload or {},
        iteration_number=iteration,
    )
    db.add(ev)
    db.flush()


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post(
    "",
    response_model=RunResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Start a repair run for an uploaded project",
)
def create_run(
    body: RunCreateRequest,
    db: Session = Depends(get_db),
) -> RunResponse:
    """
    Create a repair run and execute the initial pytest pass.

    Phase 2: runs the test suite only.
    Phase 4 will wire this into the full LangGraph repair loop.
    """
    # ── Validate project exists ───────────────────────────────────────────────
    project = db.get(Project, body.project_id)
    if not project:
        raise HTTPException(
            status_code=404,
            detail=f"Project {body.project_id!r} not found. Upload it first.",
        )

    # ── Create Run record ─────────────────────────────────────────────────────
    now = datetime.now(timezone.utc)
    run = Run(
        project_id=body.project_id,
        status="running",
        max_iterations=body.max_iterations,
        current_iteration=1,
        started_at=now,
    )
    db.add(run)
    db.flush()

    _emit_event(db, run.id, "system", "run_started", {"project_id": body.project_id})
    logger.info("Run %s started for project %s", run.id, body.project_id)

    # ── Reattach workspace ────────────────────────────────────────────────────
    try:
        workspace = WorkspaceManager.from_id(
            _workspace_id_from_project(project),
            base_dir=settings.workspace_path,
        )
        project_path = workspace.get_project_path()
    except WorkspaceError as exc:
        run.status = "error"
        run.finished_at = datetime.now(timezone.utc)
        run.final_summary = f"Workspace error: {exc}"
        _emit_event(db, run.id, "system", "error", {"detail": str(exc)})
        raise HTTPException(status_code=500, detail=f"Workspace not found: {exc}") from exc

    # ── Execute initial pytest ────────────────────────────────────────────────
    _emit_event(db, run.id, "tester", "tool_call", {"tool": "run_pytest"}, iteration=1)

    backend = LocalExecutionBackend()
    result: TestResult = backend.run_pytest(project_path)

    # ── Persist iteration ─────────────────────────────────────────────────────
    upsert_iteration(
        db=db,
        run_id=run.id,
        iteration_number=1,
        test_results=result.model_dump(),
        tests_passed=result.passed,
        tests_failed=result.failed,
        approved=True if result.success else None,
        duration_seconds=result.duration,
    )

    _emit_event(
        db, run.id, "tester", "agent_output",
        {
            "passed": result.passed,
            "failed": result.failed,
            "exit_code": result.exit_code,
            "success": result.success,
        },
        iteration=1,
    )

    # ── Finalise initial run status ───────────────────────────────────────────
    run.status = "passed" if result.success else "failed"
    run.finished_at = datetime.now(timezone.utc)
    run.final_summary = (
        f"Initial test run: {result.passed} passed, {result.failed} failed"
        + (" — all tests pass!" if result.success else " — failures detected")
    )
    db.commit()

    return RunResponse(
        run_id=run.id,
        project_id=run.project_id,
        status=run.status,
        max_iterations=run.max_iterations,
        current_iteration=run.current_iteration,
        created_at=run.created_at.isoformat(),
        started_at=run.started_at.isoformat() if run.started_at else None,
        finished_at=run.finished_at.isoformat() if run.finished_at else None,
        initial_test_results=result.model_dump(),
    )


@router.post(
    "/{run_id}/repair",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Start the autonomous self-healing LangGraph repair loop",
)
def start_repair_loop(
    run_id: str,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
) -> dict[str, str]:
    """
    Launch the LangGraph repair graph in the background for run `run_id`.
    """
    run = db.get(Run, run_id)
    if not run:
        raise HTTPException(status_code=404, detail=f"Run {run_id!r} not found.")

    project = db.get(Project, run.project_id)
    if not project:
        raise HTTPException(status_code=404, detail=f"Project for run {run_id!r} not found.")

    workspace = WorkspaceManager.from_id(
        _workspace_id_from_project(project),
        base_dir=settings.workspace_path,
    )
    project_path = str(workspace.get_project_path())

    run.status = "running"
    run.started_at = datetime.now(timezone.utc)
    db.commit()

    provider = get_llm_provider()

    # Launch graph repair asynchronously
    def _async_repair():
        from backend.database.session import SessionLocal
        bg_db = SessionLocal()
        try:
            run_repair_workflow(
                run_id=run_id,
                workspace_id=workspace.workspace_id,
                project_path=project_path,
                llm_provider=provider,
                db=bg_db,
                max_iterations=run.max_iterations,
            )
        finally:
            bg_db.close()

    background_tasks.add_task(_async_repair)

    return {
        "run_id": run_id,
        "status": "running",
        "message": "Self-healing repair graph launched in background.",
    }


@router.get(
    "/{run_id}/status",
    summary="Get live status and progress metrics of a repair run",
)
def get_run_status(
    run_id: str,
    db: Session = Depends(get_db),
) -> dict:
    """
    Return detailed status, iteration progress, test metrics, and termination status.
    """
    run = db.get(Run, run_id)
    if not run:
        raise HTTPException(status_code=404, detail=f"Run {run_id!r} not found.")

    # Get latest iteration
    iterations = (
        db.query(Iteration)
        .filter(Iteration.run_id == run_id)
        .order_by(Iteration.iteration_number.desc())
        .all()
    )

    latest = iterations[0] if iterations else None

    tests_passed = (latest.tests_failed == 0) if latest else False
    review_approved = (
        latest.review_result.get("approved", False)
        if latest and latest.review_result else False
    )

    return {
        "run_id": run.id,
        "project_id": run.project_id,
        "status": run.status,
        "current_iteration": run.current_iteration,
        "max_iterations": run.max_iterations,
        "tests_passed": tests_passed,
        "review_approved": review_approved,
        "final_summary": run.final_summary,
        "started_at": run.started_at.isoformat() if run.started_at else None,
        "finished_at": run.finished_at.isoformat() if run.finished_at else None,
    }


@router.get(
    "/{run_id}",
    response_model=RunResponse,
    summary="Get run status",
)
def get_run(run_id: str, db: Session = Depends(get_db)) -> RunResponse:
    """Return metadata and status for a run."""
    run = _get_run_or_404(run_id, db)
    return RunResponse(
        run_id=run.id,
        project_id=run.project_id,
        status=run.status,
        max_iterations=run.max_iterations,
        current_iteration=run.current_iteration,
        created_at=run.created_at.isoformat(),
        started_at=_dt(run.started_at),
        finished_at=_dt(run.finished_at),
        final_summary=run.final_summary,
    )


@router.get(
    "/{run_id}/results",
    response_model=RunResultsResponse,
    summary="Get detailed run results",
)
def get_run_results(run_id: str, db: Session = Depends(get_db)) -> RunResultsResponse:
    """Return all iteration results for a run."""
    run = _get_run_or_404(run_id, db)

    # Deduplicate iterations by iteration_number (latest/most populated wins)
    iter_map: dict[int, Iteration] = {}
    for it in run.iterations:
        num = it.iteration_number
        if num not in iter_map:
            iter_map[num] = it
        else:
            curr = iter_map[num]
            # Prefer the record that has architecture_plan or review_result or code_changes
            if (
                (not curr.architecture_plan and it.architecture_plan)
                or (not curr.review_result and it.review_result)
                or (not curr.code_changes and it.code_changes)
            ):
                iter_map[num] = it

    iterations = [
        IterationSchema(
            iteration_number=it.iteration_number,
            tests_passed=it.tests_passed,
            tests_failed=it.tests_failed,
            approved=it.approved,
            duration_seconds=it.duration_seconds,
            test_results=it.test_results,
            architecture_plan=it.architecture_plan,
            code_changes=it.code_changes,
            review_result=it.review_result,
        )
        for num, it in sorted(iter_map.items(), key=lambda x: x[0])
    ]
    return RunResultsResponse(
        run_id=run.id,
        status=run.status,
        iterations=iterations,
        final_summary=run.final_summary,
    )


@router.get(
    "/{run_id}/download",
    summary="Download the repaired project as a ZIP archive",
    response_class=StreamingResponse,
)
def download_repaired_project(
    run_id: str,
    db: Session = Depends(get_db),
) -> StreamingResponse:
    """
    Stream the repaired project workspace as a ZIP archive.

    Security
    --------
    * Only ``status in ('passed', 'already_passing')`` runs may be downloaded.
    * All files are verified to reside inside the run's workspace before
      inclusion (path-traversal guard).
    * Sensitive files and directories (.env, *.db, __pycache__, .git, etc.)
      are explicitly excluded.
    * The archive is built entirely in memory — no temporary files on disk.
    """
    # ── Verify run exists ─────────────────────────────────────────────────────
    run = db.get(Run, run_id)
    if not run:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Run {run_id!r} not found.",
        )

    # ── Guard: only completed-successfully runs can be downloaded ─────────────
    _DOWNLOADABLE_STATUSES = {"passed", "already_passing"}
    if run.status == "running":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "Repair is still in progress. "
                "Please wait for the run to complete before downloading."
            ),
        )
    if run.status not in _DOWNLOADABLE_STATUSES:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"Repaired project is not available because the run did not "
                f"complete successfully (status={run.status!r}). "
                "Only runs with status 'passed' or 'already_passing' can be downloaded."
            ),
        )

    # ── Locate the repaired workspace ─────────────────────────────────────────
    project = db.get(Project, run.project_id)
    if not project:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Project record for run {run_id!r} not found.",
        )

    try:
        workspace = WorkspaceManager.from_id(
            _workspace_id_from_project(project),
            base_dir=settings.workspace_path,
        )
        project_path: Path = workspace.get_project_path()
    except WorkspaceError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Repaired workspace not found: {exc}",
        ) from exc

    # Resolve once so all comparisons use canonical absolute paths
    project_root: Path = project_path.resolve()
    workspace_root: Path = workspace.get_workspace_path().resolve()

    if not project_root.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Repaired project directory no longer exists on disk.",
        )

    # ── Build in-memory ZIP ───────────────────────────────────────────────────
    buf = io.BytesIO()
    file_count = 0

    with zipfile.ZipFile(buf, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
        for abs_path in sorted(project_root.rglob("*")):
            if not abs_path.is_file():
                continue

            # ── Path-traversal guard ──────────────────────────────────────────
            resolved = abs_path.resolve()
            # Must be inside the workspace root (not just the project sub-dir)
            # to defend against any symlink tricks
            try:
                resolved.relative_to(workspace_root)
            except ValueError:
                logger.warning(
                    "Download: skipping %s — resolves outside workspace", abs_path
                )
                continue

            # ── Security exclusion check ──────────────────────────────────────
            if _is_excluded(resolved, project_root):
                logger.debug("Download: excluding %s", resolved.name)
                continue

            # ── Archive name: relative path from project root ─────────────────
            try:
                arcname = str(resolved.relative_to(project_root))
            except ValueError:
                # Shouldn't happen after the guard above, but be defensive
                continue

            zf.write(resolved, arcname)
            file_count += 1

    logger.info(
        "Download: created in-memory ZIP for run=%s (%d files, %d bytes)",
        run_id, file_count, buf.tell(),
    )

    buf.seek(0)
    filename = f"aegiscode-repaired-{run_id}.zip"

    return StreamingResponse(
        content=buf,
        media_type="application/zip",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "X-AegisCode-Run-Id": run_id,
            "X-AegisCode-File-Count": str(file_count),
        },
    )


# ── Utility ───────────────────────────────────────────────────────────────────

def _workspace_id_from_project(project: Project) -> str:
    """Extract the UUID from the stored workspace path ``run_<uuid>``."""
    ws_path = Path(project.workspace_path)
    folder = ws_path.name  # e.g. "run_<uuid>"
    return folder.removeprefix("run_")
