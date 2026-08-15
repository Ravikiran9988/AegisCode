"""
Runs API — Phase 2.

POST /api/runs            — create a run and execute initial pytest
GET  /api/runs/{run_id}   — get run status and metadata
GET  /api/runs/{run_id}/results — get detailed test results

Phase 2: runs execute the test suite only — no LLM agents yet.
LangGraph agents are wired in Phase 4.
"""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from backend.core.config import settings
from backend.core.logging import get_logger
from backend.database.models import Event, Iteration, Project, Run
from backend.database.session import get_db
from backend.execution.local import LocalExecutionBackend
from backend.execution.workspace import WorkspaceError, WorkspaceManager
from backend.graph.graph import run_repair_workflow
from backend.llm.factory import get_llm_provider
from backend.tools.pytest_runner import TestResult

logger = get_logger(__name__)

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
    iteration = Iteration(
        run_id=run.id,
        iteration_number=1,
        test_results=result.model_dump(),
        tests_passed=result.passed,
        tests_failed=result.failed,
        duration_seconds=result.duration,
    )
    db.add(iteration)

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
    iterations = [
        IterationSchema(
            iteration_number=it.iteration_number,
            tests_passed=it.tests_passed,
            tests_failed=it.tests_failed,
            approved=it.approved,
            duration_seconds=it.duration_seconds,
            test_results=it.test_results,
        )
        for it in sorted(run.iterations, key=lambda x: x.iteration_number)
    ]
    return RunResultsResponse(
        run_id=run.id,
        status=run.status,
        iterations=iterations,
        final_summary=run.final_summary,
    )


# ── Utility ───────────────────────────────────────────────────────────────────

def _workspace_id_from_project(project: Project) -> str:
    """Extract the UUID from the stored workspace path ``run_<uuid>``."""
    from pathlib import Path
    ws_path = Path(project.workspace_path)
    folder = ws_path.name  # e.g. "run_<uuid>"
    return folder.removeprefix("run_")
