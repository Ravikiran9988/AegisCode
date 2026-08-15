"""
LangGraph Nodes — Phase 4.

Individual node implementations for the AegisCode repair state machine.
Each node takes a `RepairState`, invokes the appropriate Phase 2 tools or Phase 3 agents,
persists DB events, and returns updated state fields.
"""

from __future__ import annotations

from pathlib import Path

from sqlalchemy.orm import Session

from backend.agents.architect import ArchitectAgent
from backend.agents.coder import CoderAgent
from backend.agents.policies import PolicyViolationError
from backend.agents.reviewer import ReviewerAgent
from backend.agents.schemas import ArchitecturePlan, CodeChange, ReviewResult
from backend.core.logging import get_logger
from backend.database.models import Event, Iteration
from backend.execution.workspace import WorkspaceManager
from backend.graph.state import RepairState
from backend.llm.base import BaseLLMProvider
from backend.tools.git_tools import get_git_diff
from backend.tools.pytest_runner import TestResult, run_pytest

logger = get_logger(__name__)


def initial_test_node(
    state: RepairState,
    db: Session | None = None,
) -> dict:
    """Run initial pytest pass before invoking Architect Agent."""
    run_id = state.get("run_id", "")
    workspace_id = state.get("workspace_id", "")
    project_path = Path(state["project_path"])

    _emit_event(db, run_id, 0, "system", "INITIAL_TEST_STARTED", {"workspace_id": workspace_id})
    logger.info("LangGraph Node: initial_test_node executing in %s", project_path)

    res: TestResult = run_pytest(project_path)
    res_dict = res.model_dump()

    _emit_event(
        db, run_id, 0, "tester", "INITIAL_TEST_COMPLETED",
        {
            "exit_code": res.exit_code,
            "passed": res.passed,
            "failed": res.failed,
            "duration": res.duration,
        }
    )

    updates: dict = {
        "initial_test_result": res_dict,
        "test_result": res_dict,
        "initial_failed_count": res.failed,
        "final_failed_count": res.failed,
    }

    if res.success:
        logger.info("Initial test pass: ALL TESTS PASSED ALREADY")
        updates["status"] = "already_passing"
        updates["termination_reason"] = "all_tests_passed"

    return updates


def architect_node(
    state: RepairState,
    llm_provider: BaseLLMProvider,
    db: Session | None = None,
) -> dict:
    """Invoke Architect Agent to produce an ArchitecturePlan."""
    run_id = state.get("run_id", "")
    iteration = state.get("iteration", 1)
    project_path = state["project_path"]

    _emit_event(db, run_id, iteration, "architect", "ARCHITECT_STARTED")
    logger.info("LangGraph Node: architect_node starting iteration %d", iteration)

    wm = WorkspaceManager.from_project_path(project_path)
    agent = ArchitectAgent(llm_provider)

    test_res = TestResult(**state["test_result"]) if state.get("test_result") else None
    plan: ArchitecturePlan = agent.analyze(
        workspace=wm,
        test_result=test_res,
        run_id=run_id,
        db=db,
    )

    _emit_event(
        db, run_id, iteration, "architect", "ARCHITECT_COMPLETED",
        {"summary": plan.summary, "relevant_files": plan.relevant_files}
    )

    return {"architecture_plan": plan.model_dump()}


def coder_node(
    state: RepairState,
    llm_provider: BaseLLMProvider,
    db: Session | None = None,
) -> dict:
    """Invoke Coder Agent to apply targeted code modifications."""
    run_id = state.get("run_id", "")
    iteration = state.get("iteration", 1)
    project_path = state["project_path"]

    _emit_event(db, run_id, iteration, "coder", "CODER_STARTED")
    logger.info("LangGraph Node: coder_node starting iteration %d", iteration)

    wm = WorkspaceManager.from_project_path(project_path)
    agent = CoderAgent(llm_provider)

    plan = ArchitecturePlan(**state["architecture_plan"])
    test_res = TestResult(**state["test_result"]) if state.get("test_result") else None

    try:
        change: CodeChange = agent.generate_and_apply_fix(
            workspace=wm,
            plan=plan,
            test_result=test_res,
            run_id=run_id,
            db=db,
        )
    except PolicyViolationError as exc:
        _emit_event(db, run_id, iteration, "coder", "POLICY_VIOLATION", {"error": str(exc)})
        logger.warning("Coder security policy violation: %s", exc)
        return {
            "status": "error",
            "termination_reason": "policy_violation",
            "code_change": {"change_type": "none", "explanation": str(exc)},
        }

    diff_res = get_git_diff(wm)

    _emit_event(
        db, run_id, iteration, "coder", "CODER_COMPLETED",
        {"file_path": change.file_path, "change_type": change.change_type}
    )

    return {
        "code_change": change.model_dump(),
        "git_diff": diff_res.model_dump(),
        "tool_call_count": state.get("tool_call_count", 0) + 1,
    }


def test_node(
    state: RepairState,
    db: Session | None = None,
) -> dict:
    """Execute Pytest after Coder modifications."""
    run_id = state.get("run_id", "")
    iteration = state.get("iteration", 1)
    project_path = Path(state["project_path"])

    _emit_event(db, run_id, iteration, "tester", "TEST_STARTED")
    logger.info("LangGraph Node: test_node starting iteration %d", iteration)

    res: TestResult = run_pytest(project_path)
    res_dict = res.model_dump()

    _emit_event(
        db, run_id, iteration, "tester", "TEST_COMPLETED",
        {
            "exit_code": res.exit_code,
            "passed": res.passed,
            "failed": res.failed,
            "duration": res.duration,
        }
    )

    return {
        "test_result": res_dict,
        "final_failed_count": res.failed,
    }


def reviewer_node(
    state: RepairState,
    llm_provider: BaseLLMProvider,
    db: Session | None = None,
) -> dict:
    """Invoke Reviewer Agent to audit changes and test outputs."""
    run_id = state.get("run_id", "")
    iteration = state.get("iteration", 1)
    project_path = state["project_path"]

    _emit_event(db, run_id, iteration, "reviewer", "REVIEWER_STARTED")
    logger.info("LangGraph Node: reviewer_node starting iteration %d", iteration)

    wm = WorkspaceManager.from_project_path(project_path)
    agent = ReviewerAgent(llm_provider)

    code_change = CodeChange(**state["code_change"]) if state.get("code_change") else None
    init_data = state.get("initial_test_result")
    initial_res = TestResult(**init_data) if init_data else None
    new_res = TestResult(**state["test_result"]) if state.get("test_result") else None

    review: ReviewResult = agent.review(
        workspace=wm,
        coder_explanation=code_change.explanation if code_change else "",
        initial_test_result=initial_res,
        new_test_result=new_res,
        run_id=run_id,
        db=db,
    )

    # Persist iteration details to DB
    if db and run_id:
        try:
            it = Iteration(
                run_id=run_id,
                iteration_number=iteration,
                architecture_plan=state.get("architecture_plan"),
                code_changes=[state.get("code_change")] if state.get("code_change") else [],
                test_results=state.get("test_result"),
                review_result=review.model_dump(),
                tests_passed=new_res.passed if new_res else 0,
                tests_failed=new_res.failed if new_res else 0,
                duration_seconds=new_res.duration if new_res else 0.0,
            )
            db.add(it)
            db.flush()
        except Exception as exc:
            logger.warning("Failed to persist iteration record: %s", exc)

    _emit_event(
        db, run_id, iteration, "reviewer", "REVIEWER_COMPLETED",
        {
            "approved": review.approved,
            "root_cause_fixed": review.root_cause_fixed,
            "regression_risk": review.regression_risk,
        }
    )

    rejections = state.get("reviewer_rejections", 0)
    if not review.approved:
        rejections += 1

    updates: dict = {
        "review_result": review.model_dump(),
        "reviewer_rejections": rejections,
    }

    if new_res and new_res.success and review.approved:
        updates["status"] = "passed"
        updates["termination_reason"] = "all_tests_passed"

    return updates


def _emit_event(
    db: Session | None,
    run_id: str,
    iteration: int,
    agent: str,
    event_type: str,
    payload: dict | None = None,
) -> None:
    if not db or not run_id:
        return
    try:
        ev = Event(
            run_id=run_id,
            agent=agent,
            event_type=event_type,
            payload=payload or {},
            iteration_number=iteration,
        )
        db.add(ev)
        db.flush()
    except Exception as exc:
        logger.warning("Failed to emit event %s: %s", event_type, exc)
