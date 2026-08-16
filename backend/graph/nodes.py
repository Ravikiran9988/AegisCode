"""
LangGraph Nodes — Phase 4.

Individual node implementations for the AegisCode repair state machine.
Each node takes a `RepairState`, invokes the appropriate Phase 2 tools or Phase 3 agents,
persists DB events and iterations via authoritative upserts, and returns updated state fields.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy.orm import Session

from backend.agents.architect import ArchitectAgent
from backend.agents.coder import CoderAgent
from backend.agents.policies import PolicyViolationError
from backend.agents.reviewer import ReviewerAgent
from backend.agents.schemas import ArchitecturePlan, CodeChange, ReviewResult
from backend.core.logging import get_logger
from backend.database.models import Event, Run
from backend.database.persistence import upsert_iteration
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
    logger.info(
        "[INITIAL TEST START] run_id=%s workspace=%s path=%s",
        run_id, workspace_id, project_path,
    )

    res: TestResult = run_pytest(project_path)
    res_dict = res.model_dump()

    _emit_event(
        db, run_id, 0, "tester", "INITIAL_TEST_COMPLETED",
        {
            "exit_code": res.exit_code,
            "passed": res.passed,
            "failed": res.failed,
            "duration": res.duration,
        },
    )
    logger.info(
        "[INITIAL TEST COMPLETE] run_id=%s exit_code=%d passed=%d failed=%d success=%s",
        run_id, res.exit_code, res.passed, res.failed, res.success,
    )

    updates: dict = {
        "initial_test_result": res_dict,
        "test_result": res_dict,
        "initial_failed_count": res.failed,
        "final_failed_count": res.failed,
    }

    if res.success:
        logger.info("[INITIAL TEST] ALL TESTS PASSED ALREADY for run_id=%s", run_id)
        updates["status"] = "already_passing"
        updates["termination_reason"] = "all_tests_passed"

        # Authoritatively persist iteration 1 as healthy and approved
        upsert_iteration(
            db=db,
            run_id=run_id,
            iteration_number=1,
            test_results=res_dict,
            tests_passed=res.passed,
            tests_failed=0,
            approved=True,
            duration_seconds=res.duration,
        )
        if db and run_id:
            try:
                run_rec = db.get(Run, run_id)
                if run_rec:
                    run_rec.status = "already_passing"
                    run_rec.finished_at = datetime.now(timezone.utc)
                    run_rec.final_summary = "All tests already pass — project is healthy"
                    db.commit()
            except Exception as exc:
                logger.warning("Failed to update Run record on already_passing: %s", exc)
    else:
        # Record baseline test metrics for iteration 1
        upsert_iteration(
            db=db,
            run_id=run_id,
            iteration_number=1,
            test_results=res_dict,
            tests_passed=res.passed,
            tests_failed=res.failed,
            duration_seconds=res.duration,
        )

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
    logger.info("[ARCHITECT START] run_id=%s iteration=%d", run_id, iteration)

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
        {"summary": plan.summary, "relevant_files": plan.relevant_files},
    )
    logger.info(
        "[ARCHITECT COMPLETE] run_id=%s iteration=%d summary=%r relevant_files=%s",
        run_id, iteration, plan.summary, plan.relevant_files,
    )

    plan_dict = plan.model_dump()
    upsert_iteration(
        db=db,
        run_id=run_id,
        iteration_number=iteration,
        architecture_plan=plan_dict,
    )

    return {"architecture_plan": plan_dict}


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
    logger.info("[CODER START] run_id=%s iteration=%d", run_id, iteration)

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
        logger.warning("[CODER POLICY VIOLATION] run_id=%s: %s", run_id, exc)
        failed_change = CodeChange(
            file_path=plan.relevant_files[0] if plan.relevant_files else "unknown",
            change_type="none",
            explanation=f"Policy violation: {exc}",
            root_cause=str(exc),
            patch="",
            confidence=0.0,
        )
        upsert_iteration(
            db=db,
            run_id=run_id,
            iteration_number=iteration,
            code_changes=[failed_change.model_dump()],
        )
        return {
            "status": "error",
            "termination_reason": "policy_violation",
            "code_change": failed_change.model_dump(),
        }
    except RuntimeError as exc:
        err_msg = str(exc)
        _emit_event(db, run_id, iteration, "coder", "PATCH_ERROR", {"error": err_msg})
        logger.warning("[CODER PATCH ERROR] run_id=%s iteration=%d: %s", run_id, iteration, err_msg)
        diff_res = get_git_diff(wm)
        failed_change = CodeChange(
            file_path=plan.relevant_files[0] if plan.relevant_files else "unknown",
            change_type="none",
            explanation=f"Patch application failed: {err_msg}",
            root_cause=err_msg,
            patch="",
            confidence=0.0,
        )
        upsert_iteration(
            db=db,
            run_id=run_id,
            iteration_number=iteration,
            code_changes=[failed_change.model_dump()],
        )
        return {
            "code_change": failed_change.model_dump(),
            "coder_error": err_msg,
            "git_diff": diff_res.model_dump(),
            "tool_call_count": state.get("tool_call_count", 0) + 1,
        }

    diff_res = get_git_diff(wm)

    _emit_event(
        db, run_id, iteration, "coder", "CODER_COMPLETED",
        {"file_path": change.file_path, "change_type": change.change_type},
    )
    logger.info(
        "[CODER COMPLETE] run_id=%s iteration=%d file=%s type=%s",
        run_id, iteration, change.file_path, change.change_type,
    )

    change_dict = change.model_dump()
    upsert_iteration(
        db=db,
        run_id=run_id,
        iteration_number=iteration,
        code_changes=[change_dict],
    )

    return {
        "code_change": change_dict,
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
    logger.info("[TEST START] run_id=%s iteration=%d", run_id, iteration)

    res: TestResult = run_pytest(project_path)
    res_dict = res.model_dump()

    _emit_event(
        db, run_id, iteration, "tester", "TEST_COMPLETED",
        {
            "exit_code": res.exit_code,
            "passed": res.passed,
            "failed": res.failed,
            "duration": res.duration,
        },
    )
    logger.info(
        "[TEST COMPLETE] run_id=%s iteration=%d passed=%d failed=%d exit_code=%d",
        run_id, iteration, res.passed, res.failed, res.exit_code,
    )

    upsert_iteration(
        db=db,
        run_id=run_id,
        iteration_number=iteration,
        test_results=res_dict,
        tests_passed=res.passed,
        tests_failed=res.failed,
        duration_seconds=res.duration,
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
    logger.info("[REVIEWER START] run_id=%s iteration=%d", run_id, iteration)

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

    review_dict = review.model_dump()
    upsert_iteration(
        db=db,
        run_id=run_id,
        iteration_number=iteration,
        review_result=review_dict,
        approved=review.approved,
    )

    _emit_event(
        db, run_id, iteration, "reviewer", "REVIEWER_COMPLETED",
        {
            "approved": review.approved,
            "root_cause_fixed": review.root_cause_fixed,
            "regression_risk": review.regression_risk,
        },
    )
    logger.info(
        "[REVIEWER COMPLETE] run_id=%s iteration=%d approved=%s root_cause_fixed=%s risk=%s",
        run_id, iteration, review.approved, review.root_cause_fixed, review.regression_risk,
    )

    rejections = state.get("reviewer_rejections", 0)
    if not review.approved:
        rejections += 1

    updates: dict = {
        "review_result": review_dict,
        "reviewer_rejections": rejections,
    }

    if new_res and new_res.success and review.approved:
        updates["status"] = "passed"
        updates["termination_reason"] = "all_tests_passed"
        if db and run_id:
            try:
                run_rec = db.get(Run, run_id)
                if run_rec:
                    run_rec.status = "passed"
                    run_rec.finished_at = datetime.now(timezone.utc)
                    run_rec.final_summary = (
                        "Repair completed successfully — all tests passed and reviewer approved"
                    )
                    db.commit()
            except Exception as exc:
                logger.warning("Failed to update Run record on review approval: %s", exc)

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
