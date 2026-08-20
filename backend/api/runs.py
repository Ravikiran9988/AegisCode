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

from backend.api.auth import get_optional_current_user
from backend.core.config import settings
from backend.core.logging import get_logger
from backend.database.models import Event, Iteration, Project, Run, User
from backend.database.persistence import upsert_iteration
from backend.database.session import get_db
from backend.execution.local import LocalExecutionBackend
from backend.execution.workspace import WorkspaceError, WorkspaceManager
from backend.graph.graph import run_repair_workflow
from backend.llm.factory import get_llm_provider
from backend.tools.pytest_runner import TestResult

logger = get_logger(__name__)

# ── Security exclusion rules for the download ZIP ─────────────────────────────


# ── Run creation ─────────────────────────────────────────────────────────────

def _workspace_id_from_project(project: Project) -> str:
    """Return the workspace identifier stored on the project."""
    return project.workspace_id


def _check_run_access(run: Run, current_user: User | None) -> None:
    """Check ownership for JWT-authenticated runs."""
    if current_user is None:
        return
    if run.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="You do not have permission to access this repair run.")


def _format_run_summary(run: Run) -> dict:
    return {
        "run_id": run.id,
        "project_id": run.project_id,
        "status": run.status,
        "max_iterations": run.max_iterations,
        "current_iteration": run.current_iteration,
        "created_at": run.created_at.isoformat() if run.created_at else None,
        "started_at": run.started_at.isoformat() if run.started_at else None,
        "finished_at": run.finished_at.isoformat() if run.finished_at else None,
    }


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
    current_user: User | None = Depends(get_optional_current_user),
) -> RunResponse:
    """
    Create a repair run and execute the initial pytest pass.

    Phase 2: runs the test suite only.
    Phase 4 will wire this into the full LangGraph repair loop.
    """
    project = db.get(Project, body.project_id)
    if not project:
        raise HTTPException(
            status_code=404,
            detail=f"Project {body.project_id!r} not found. Upload it first.",
        )

    now = datetime.now(timezone.utc)
    run = Run(
        user_id=current_user.id if current_user else None,
        guest_id=project.guest_id if current_user is None else None,
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

    _emit_event(db, run.id, "tester", "tool_call", {"tool": "run_pytest"}, iteration=1)

    backend = LocalExecutionBackend()
    result: TestResult = backend.run_pytest(project_path)

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
