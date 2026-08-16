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
    iteration: int | None = None
    tests_passed: int | None = None
    tests_failed: int | None = None
    approved: bool | None = None
    duration_seconds: float | None = None
    test_results: dict | None = None
    architecture_plan: dict | None = None
    code_changes: list | dict | None = None
    review_result: dict | None = None

    # Nested structured fields matching conceptual schema
    architect: dict | None = None
    coder: dict | list | None = None
    tests: dict | None = None
    reviewer: dict | None = None


class RunResultsResponse(BaseModel):
    run_id: str
    status: str
    iterations: list[IterationSchema]
    iteration_details: list[IterationSchema] | None = None
    final_summary: str | None = None
    tests_passed: int | None = None
    tests_failed: int | None = None
    reviewer_approved: bool | None = None
    total_iterations: int | None = None
    duration: float | None = None
    termination_reason: str | None = None


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
    Return detailed status, iteration progress, test metrics, real-time node state, and timeline.
    """
    run = db.get(Run, run_id)
    if not run:
        raise HTTPException(status_code=404, detail=f"Run {run_id!r} not found.")

    # Get iterations
    iterations = (
        db.query(Iteration)
        .filter(Iteration.run_id == run_id)
        .order_by(Iteration.iteration_number.asc())
        .all()
    )

    # Get events
    events = (
        db.query(Event)
        .filter(Event.run_id == run_id)
        .order_by(Event.created_at.asc())
        .all()
    )

    latest_it = iterations[-1] if iterations else None

    if latest_it and latest_it.tests_failed is not None:
        tests_passed = (latest_it.tests_failed == 0)
    else:
        tests_passed = True if run.status in ("passed", "already_passing") else False

    if latest_it and latest_it.review_result:
        review_approved = latest_it.review_result.get("approved", False)
    else:
        review_approved = True if run.status in ("passed", "already_passing") else False

    # Determine current node, agent, phase, and action from events
    cur_node = "initial_test"
    cur_agent = "Test Agent"
    cur_phase = "Repository Assessment"
    cur_action_desc = "Initializing autonomous repair pipeline..."
    cur_file = None

    if events:
        last_ev = events[-1]
        payload = last_ev.payload or {}
        cur_node = payload.get("node", last_ev.agent)
        cur_agent = payload.get("agent", last_ev.agent.replace("_", " ").title() + " Agent")
        cur_phase = payload.get("phase", "Autonomous Execution")
        cur_action_desc = payload.get("description", last_ev.event_type.replace("_", " ").title())
        cur_file = payload.get("file_path") or payload.get("file")

    # If run has reached a terminal state, reflect terminal phase
    if run.status in ("passed", "already_passing"):
        cur_phase = "Repair Complete & Verified"
        cur_action_desc = "All pytest assertions passed and reviewer approved patch."
    elif run.status in ("failed", "stalled"):
        cur_phase = "Repair Terminated"
        cur_action_desc = run.final_summary or "Repair concluded without passing patch."
    elif run.status == "error":
        cur_phase = "Execution Error"
        cur_action_desc = run.final_summary or "Encountered runtime error during repair."
    elif run.status == "cancelled":
        cur_phase = "Repair Cancelled"
        cur_action_desc = "Repair was cancelled by user."

    # Compute pipeline nodes for the current iteration
    cur_iter_num = max(run.current_iteration, 1)
    ev_types_cur_iter = {
        ev.event_type for ev in events
        if (ev.iteration_number == cur_iter_num or (ev.iteration_number == 0 and cur_iter_num == 1))
    }

    def _get_node_status(node_name: str, start_tag: str, complete_tag: str) -> str:
        if complete_tag in ev_types_cur_iter:
            return "completed"
        if start_tag in ev_types_cur_iter:
            if run.status in ("failed", "stalled", "error") and cur_node == node_name:
                return "failed"
            return "running"
        if run.status in ("passed", "already_passing"):
            return "completed"
        return "pending"

    pipeline_nodes = [
        {
            "node": "initial_test",
            "name": "Repository Assessment",
            "agent": "Test Agent",
            "status": _get_node_status(
                "initial_test", "INITIAL_TEST_STARTED", "INITIAL_TEST_COMPLETED"
            ),
        },
        {
            "node": "architect",
            "name": "Root Cause Analysis",
            "agent": "Architect Agent",
            "status": _get_node_status(
                "architect", "ARCHITECT_STARTED", "ARCHITECT_COMPLETED"
            ),
        },
        {
            "node": "coder",
            "name": "Code Repair & Patch",
            "agent": "Coder Agent",
            "status": _get_node_status(
                "coder", "CODER_STARTED", "CODER_COMPLETED"
            ),
        },
        {
            "node": "test",
            "name": "Test & Validation",
            "agent": "Test Agent",
            "status": _get_node_status(
                "test", "TEST_STARTED", "TEST_COMPLETED"
            ),
        },
        {
            "node": "reviewer",
            "name": "Reviewer Audit Gate",
            "agent": "Reviewer Agent",
            "status": _get_node_status(
                "reviewer", "REVIEWER_STARTED", "REVIEWER_COMPLETED"
            ),
        },
    ]

    # Iteration summary list
    iterations_summary = []
    files_changed_set: set[str] = set()
    for it in iterations:
        t_pass = it.tests_passed
        t_fail = it.tests_failed
        it_appr = it.approved
        it_status = "running"
        if it_appr is True and (t_fail == 0):
            it_status = "passed"
        elif t_fail is not None and (t_fail > 0 or it_appr is False):
            it_status = "failed"

        # Check code changes in this iteration
        if it.code_changes and isinstance(it.code_changes, list):
            for c in it.code_changes:
                if isinstance(c, dict) and c.get("file_path"):
                    files_changed_set.add(c["file_path"])

        iterations_summary.append({
            "iteration_number": it.iteration_number,
            "status": it_status,
            "tests_passed": t_pass,
            "tests_failed": t_fail,
            "approved": it_appr,
            "duration_seconds": it.duration_seconds,
        })

    # Test execution stats from latest available iteration
    tres_dict = (latest_it.test_results or {}) if latest_it else {}
    if latest_it and latest_it.tests_passed is not None:
        t_pass_val = latest_it.tests_passed
    else:
        t_pass_val = tres_dict.get("passed", 0)

    if latest_it and latest_it.tests_failed is not None:
        t_fail_val = latest_it.tests_failed
    else:
        t_fail_val = tres_dict.get("failed", 0)

    t_skip_val = tres_dict.get("skipped", 0)
    t_total_val = t_pass_val + t_fail_val + t_skip_val
    t_exec_val = t_pass_val + t_fail_val
    t_cov_val = round((t_pass_val / t_total_val) * 100, 1) if t_total_val > 0 else 0.0

    # Calculate real progress percentage
    max_its = max(run.max_iterations, 1)
    completed_nodes_in_cur = sum(1 for n in pipeline_nodes if n["status"] == "completed")
    if run.status in ("passed", "already_passing"):
        prog_pct = 100
    elif run.status in ("failed", "stalled", "error", "cancelled"):
        total_steps = max_its * 4
        done_steps = (max(run.current_iteration, 1) - 1) * 4 + completed_nodes_in_cur
        prog_pct = min(90, max(5, int((done_steps / total_steps) * 100)))
    else:
        total_steps = max_its * 4
        active_step = (max(run.current_iteration, 1) - 1) * 4 + completed_nodes_in_cur
        prog_pct = min(95, max(5, int((active_step / total_steps) * 100)))

    # Elapsed duration
    elapsed_sec = 0.0
    if run.started_at:
        end_time = run.finished_at or datetime.now(timezone.utc)
        if run.started_at.tzinfo is None:
            st_time = run.started_at.replace(tzinfo=timezone.utc)
        else:
            st_time = run.started_at
        if end_time.tzinfo is None:
            end_time = end_time.replace(tzinfo=timezone.utc)
        elapsed_sec = round((end_time - st_time).total_seconds(), 1)

    # Timeline list
    timeline = []
    for ev in events:
        ev_pl = ev.payload or {}
        ts_str = ev.created_at.strftime("%H:%M:%S") if ev.created_at else ""
        msg = (
            ev_pl.get("description")
            or ev_pl.get("summary")
            or ev.event_type.replace("_", " ").title()
        )
        timeline.append({
            "timestamp": ts_str,
            "created_at": ev.created_at.isoformat() if ev.created_at else None,
            "agent": ev_pl.get("agent", ev.agent.replace("_", " ").title() + " Agent"),
            "event_type": ev.event_type,
            "message": msg,
            "iteration": ev.iteration_number,
        })

    p_name = run.project.name if run.project else "Python Project"
    f_analyzed = run.project.file_count if run.project else 0

    return {
        "run_id": run.id,
        "project_id": run.project_id,
        "project_name": p_name,
        "status": run.status,
        "current_node": cur_node,
        "current_agent": cur_agent,
        "current_phase": cur_phase,
        "current_action": {
            "agent": cur_agent,
            "node": cur_node,
            "description": cur_action_desc,
            "file": cur_file,
        },
        "iteration": run.current_iteration,
        "current_iteration": run.current_iteration,
        "max_iterations": run.max_iterations,
        "progress_percent": prog_pct,
        "pipeline_nodes": pipeline_nodes,
        "iterations_summary": iterations_summary,
        "tests": {
            "total": t_total_val,
            "executed": t_exec_val,
            "passed": t_pass_val,
            "failed": t_fail_val,
            "skipped": t_skip_val,
            "coverage_percent": t_cov_val,
        },
        "files": {
            "analyzed": f_analyzed,
            "changed": len(files_changed_set),
            "changed_files": sorted(files_changed_set),
        },
        "timeline": timeline,
        "tests_passed": tests_passed,
        "review_approved": review_approved,
        "final_summary": run.final_summary,
        "started_at": run.started_at.isoformat() if run.started_at else None,
        "finished_at": run.finished_at.isoformat() if run.finished_at else None,
        "elapsed_seconds": elapsed_sec,
    }


def _format_run_summary(r: Run) -> dict:
    """Format a Run database model into a summary dictionary."""
    dur = None
    if r.started_at and r.finished_at:
        dur = round((r.finished_at - r.started_at).total_seconds(), 2)
    elif r.iterations:
        iter_durs = [it.duration_seconds for it in r.iterations if it.duration_seconds is not None]
        if iter_durs:
            dur = round(sum(iter_durs), 2)

    # Find latest iteration metrics
    t_passed = None
    t_failed = None
    r_approved = None
    if r.iterations:
        sorted_its = sorted(r.iterations, key=lambda it: it.iteration_number)
        latest = sorted_its[-1]
        t_passed = latest.tests_passed
        t_failed = latest.tests_failed
        if t_passed is None and latest.test_results:
            t_passed = latest.test_results.get("passed")
            t_failed = latest.test_results.get("failed")
        if latest.review_result:
            r_approved = latest.review_result.get("approved")
        elif latest.approved is not None:
            r_approved = latest.approved

    if r.status in ("passed", "already_passing") and r_approved is None:
        r_approved = True

    p_name = r.project.name if r.project else "unknown"

    return {
        "run_id": r.id,
        "project_id": r.project_id,
        "project_name": p_name,
        "status": r.status,
        "current_iteration": r.current_iteration,
        "max_iterations": r.max_iterations,
        "tests_passed": t_passed,
        "tests_failed": t_failed,
        "reviewer_approved": r_approved,
        "duration": dur,
        "created_at": r.created_at.isoformat() if r.created_at else None,
        "started_at": r.started_at.isoformat() if r.started_at else None,
        "finished_at": r.finished_at.isoformat() if r.finished_at else None,
        "final_summary": r.final_summary,
    }


@router.get(
    "",
    summary="List historical repair runs",
)
def list_runs(
    limit: int = 50,
    offset: int = 0,
    db: Session = Depends(get_db),
) -> list[dict]:
    """
    List historical repair runs with status, project metadata, and summary metrics.
    """
    runs = (
        db.query(Run)
        .order_by(Run.created_at.desc())
        .offset(offset)
        .limit(min(limit, 100))
        .all()
    )
    return [_format_run_summary(r) for r in runs]


@router.get(
    "/active",
    summary="List currently active / running repair runs",
)
def list_active_runs(
    limit: int = 50,
    db: Session = Depends(get_db),
) -> list[dict]:
    """
    List currently active (running or pending) repair runs.
    """
    runs = (
        db.query(Run)
        .filter(Run.status.in_(("running", "pending")))
        .order_by(Run.created_at.desc())
        .limit(min(limit, 100))
        .all()
    )
    return [_format_run_summary(r) for r in runs]


@router.get(
    "/history",
    summary="List completed / historical repair runs",
)
def list_history_runs(
    limit: int = 50,
    offset: int = 0,
    status: str | None = None,
    db: Session = Depends(get_db),
) -> list[dict]:
    """
    List historical repair runs with optional status filtering.
    """
    query = db.query(Run)
    if status:
        query = query.filter(Run.status == status)
    runs = (
        query.order_by(Run.created_at.desc())
        .offset(offset)
        .limit(min(limit, 100))
        .all()
    )
    return [_format_run_summary(r) for r in runs]


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

    iterations = []
    for it in sorted(iter_map.values(), key=lambda x: x.iteration_number):
        changes = it.code_changes
        coder_obj = changes[0] if (isinstance(changes, list) and changes) else changes
        iterations.append(
            IterationSchema(
                iteration_number=it.iteration_number,
                iteration=it.iteration_number,
                tests_passed=it.tests_passed,
                tests_failed=it.tests_failed,
                approved=it.approved,
                duration_seconds=it.duration_seconds,
                test_results=it.test_results,
                architecture_plan=it.architecture_plan,
                code_changes=it.code_changes,
                review_result=it.review_result,
                architect=it.architecture_plan,
                coder=coder_obj,
                tests=it.test_results,
                reviewer=it.review_result,
            )
        )

    # Compute duration
    dur = None
    if run.started_at and run.finished_at:
        dur = round((run.finished_at - run.started_at).total_seconds(), 2)
    elif iterations:
        dur = round(sum(it.duration_seconds or 0 for it in iterations), 2)

    # Extract termination reason
    term_reason = None
    if run.final_summary and "reason=" in run.final_summary:
        try:
            term_reason = run.final_summary.split("reason=")[1].strip("'\" ")
        except Exception:
            term_reason = None
    if not term_reason:
        if run.status in ("passed", "already_passing"):
            term_reason = "all_tests_passed"
        elif run.status == "stalled":
            term_reason = "repeated_failure"
        elif run.status == "failed":
            term_reason = "max_iterations_reached"
        elif run.status == "error":
            term_reason = "graph_error"

    latest_it = iterations[-1] if iterations else None
    t_passed = latest_it.tests_passed if latest_it else None
    t_failed = latest_it.tests_failed if latest_it else None
    r_approved = (
        latest_it.approved
        if (latest_it and latest_it.approved is not None)
        else (True if run.status in ("passed", "already_passing") else False)
    )

    return RunResultsResponse(
        run_id=run.id,
        status=run.status,
        iterations=iterations,
        iteration_details=iterations,
        final_summary=run.final_summary,
        tests_passed=t_passed,
        tests_failed=t_failed,
        reviewer_approved=r_approved,
        total_iterations=len(iterations),
        duration=dur,
        termination_reason=term_reason,
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
