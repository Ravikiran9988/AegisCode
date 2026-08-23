"""
LangGraph Nodes — Phase 4.

Individual node implementations for the AegisCode repair state machine.
Each node takes a `RepairState`, invokes the appropriate Phase 2 tools or Phase 3 agents,
persists DB events and iterations via authoritative upserts, and returns updated state fields.
"""

from __future__ import annotations

import time
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy.orm import Session

from backend.agents.architect import ArchitectAgent
from backend.agents.coder import CoderAgent
from backend.agents.policies import PolicyViolationError
from backend.agents.reviewer import ReviewerAgent
from backend.agents.schemas import ArchitecturePlan, CodeChange, ReviewResult
from backend.core.config import settings
from backend.core.logging import get_logger
from backend.database.models import Event, Run
from backend.database.persistence import upsert_iteration
from backend.execution import get_execution_backend
from backend.execution.workspace import WorkspaceManager
from backend.graph.loop_detector import compute_failure_fingerprint, is_repeated_failure
from backend.graph.state import RepairState
from backend.llm.base import BaseLLMProvider
from backend.tools.filesystem import get_project_structure
from backend.tools.git_tools import GitDiff, get_git_diff
from backend.tools.pytest_runner import TestResult

logger = get_logger(__name__)


def _record_timing(
    state: RepairState,
    updates: dict,
    iteration: int,
    stage_name: str,
    duration: float,
) -> None:
    timings = dict(updates.get("iteration_timings") or state.get("iteration_timings") or {})
    iter_t = dict(timings.get(iteration) or {})
    iter_t[stage_name] = round(duration, 3)
    timings[iteration] = iter_t
    updates["iteration_timings"] = timings



def initial_test_node(
    state: RepairState,
    db: Session | None = None,
) -> dict:
    """Run initial pytest pass before invoking Architect Agent."""
    run_id = state.get("run_id", "")
    workspace_id = state.get("workspace_id", "")
    project_path = Path(state["project_path"])

    _emit_event(
        db,
        run_id,
        0,
        "system",
        "INITIAL_TEST_STARTED",
        {
            "node": "initial_test",
            "agent": "Test Agent",
            "phase": "Repository Assessment",
            "description": "Executing initial baseline pytest pass to inspect test failures...",
            "workspace_id": workspace_id,
        },
    )
    logger.info(
        "[INITIAL TEST START] run_id=%s workspace=%s path=%s",
        run_id, workspace_id, project_path,
    )

    start_t = time.monotonic()
    res: TestResult = get_execution_backend().run_pytest(project_path)
    init_dur = time.monotonic() - start_t
    res_dict = res.model_dump()

    _emit_event(
        db,
        run_id,
        0,
        "tester",
        "INITIAL_TEST_COMPLETED",
        {
            "node": "initial_test",
            "agent": "Test Agent",
            "phase": "Repository Assessment",
            "description": (
                f"Initial assessment completed: {res.passed} passed, {res.failed} failed "
                f"(Pytest exit code {res.exit_code})."
            ),
            "exit_code": res.exit_code,
            "passed": res.passed,
            "failed": res.failed,
            "duration": res.duration,
        },
    )
    logger.info(
        "[INITIAL TEST COMPLETE] run_id=%s exit_code=%d passed=%d failed=%d success=%s duration=%.2fs",
        run_id, res.exit_code, res.passed, res.failed, res.success, init_dur,
    )

    updates: dict = {
        "initial_test_result": res_dict,
        "test_result": res_dict,
        "initial_failed_count": res.failed,
        "final_failed_count": res.failed,
    }

    _record_timing(state, updates, 1, "initial_test", init_dur)

    # Build and cache project structure during initial assessment
    if not state.get("project_structure"):
        try:
            wm = WorkspaceManager.from_project_path(str(project_path))
            struct = get_project_structure(wm)
            if struct.success:
                updates["project_structure"] = struct.tree
        except Exception as exc:
            logger.warning("Failed to cache project structure in initial_test_node: %s", exc)


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

    _emit_event(
        db,
        run_id,
        iteration,
        "architect",
        "ARCHITECT_STARTED",
        {
            "node": "architect",
            "agent": "Architect Agent",
            "phase": "Root Cause Analysis",
            "description": (
                f"Iteration {iteration}: Analyzing pytest diagnostics, error traces, and source "
                "repository..."
            ),
        },
    )
    logger.info("[ARCHITECT START] run_id=%s iteration=%d", run_id, iteration)

    start_t = time.monotonic()
    wm = WorkspaceManager.from_project_path(project_path)
    agent = ArchitectAgent(llm_provider)

    cached_struct = state.get("project_structure")
    test_res = TestResult(**state["test_result"]) if state.get("test_result") else None
    plan: ArchitecturePlan = agent.analyze(
        workspace=wm,
        test_result=test_res,
        run_id=run_id,
        db=db,
        cached_project_structure=cached_struct,
    )
    arch_dur = time.monotonic() - start_t

    _emit_event(
        db,
        run_id,
        iteration,
        "architect",
        "ARCHITECT_COMPLETED",
        {
            "node": "architect",
            "agent": "Architect Agent",
            "phase": "Root Cause Analysis",
            "summary": plan.summary,
            "relevant_files": plan.relevant_files,
            "duration": round(arch_dur, 2),
            "description": (
                f"Iteration {iteration}: Root cause plan formulated in {arch_dur:.2f}s — {plan.summary}"
            ),
        },
    )
    logger.info(
        "[ARCHITECT COMPLETE] run_id=%s iteration=%d summary=%r relevant_files=%s duration=%.2fs",
        run_id, iteration, plan.summary, plan.relevant_files, arch_dur,
    )

    plan_dict = plan.model_dump()
    upsert_iteration(
        db=db,
        run_id=run_id,
        iteration_number=iteration,
        architecture_plan=plan_dict,
    )

    updates = {"architecture_plan": plan_dict}
    _record_timing(state, updates, iteration, "architect", arch_dur)
    return updates



def coder_node(
    state: RepairState,
    llm_provider: BaseLLMProvider,
    db: Session | None = None,
) -> dict:
    """Invoke Coder Agent to apply targeted code modifications."""
    run_id = state.get("run_id", "")
    iteration = state.get("iteration", 1)
    project_path = state["project_path"]

    rel_file = ""
    if state.get("architecture_plan") and state["architecture_plan"].get("relevant_files"):
        rel_file = state["architecture_plan"]["relevant_files"][0]

    _emit_event(
        db,
        run_id,
        iteration,
        "coder",
        "CODER_STARTED",
        {
            "node": "coder",
            "agent": "Coder Agent",
            "phase": "Code Repair & Patch",
            "file_path": rel_file,
            "description": (
                f"Iteration {iteration}: Synthesizing unified diff patch and updating workspace..."
            ),
        },
    )
    logger.info("[CODER START] run_id=%s iteration=%d", run_id, iteration)

    start_t = time.monotonic()
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
        _emit_event(
            db,
            run_id,
            iteration,
            "coder",
            "POLICY_VIOLATION",
            {
                "node": "coder",
                "agent": "Coder Agent",
                "phase": "Code Repair & Patch",
                "error": str(exc),
                "description": f"Iteration {iteration}: Policy violation detected — {exc}",
            },
        )
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
        _emit_event(
            db,
            run_id,
            iteration,
            "coder",
            "PATCH_ERROR",
            {
                "node": "coder",
                "agent": "Coder Agent",
                "phase": "Code Repair & Patch",
                "error": err_msg,
                "description": f"Iteration {iteration}: Patch application failed — {err_msg}",
            },
        )
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

    coder_dur = time.monotonic() - start_t
    diff_res = get_git_diff(wm)

    _emit_event(
        db,
        run_id,
        iteration,
        "coder",
        "CODER_COMPLETED",
        {
            "node": "coder",
            "agent": "Coder Agent",
            "phase": "Code Repair & Patch",
            "file_path": change.file_path,
            "change_type": change.change_type,
            "explanation": change.explanation,
            "duration": round(coder_dur, 2),
            "description": (
                f"Iteration {iteration}: Applied patch to `{change.file_path}` "
                f"({change.change_type}) in {coder_dur:.2f}s — {change.explanation}"
            ),
        },
    )
    logger.info(
        "[CODER COMPLETE] run_id=%s iteration=%d file=%s type=%s duration=%.2fs",
        run_id, iteration, change.file_path, change.change_type, coder_dur,
    )

    change_dict = change.model_dump()
    upsert_iteration(
        db=db,
        run_id=run_id,
        iteration_number=iteration,
        code_changes=[change_dict],
    )

    updates = {
        "code_change": change_dict,
        "git_diff": diff_res.model_dump(),
        "tool_call_count": state.get("tool_call_count", 0) + 1,
    }
    # Invalidate cached tree structure if files were written, created, or deleted
    if change.change_type in ("write", "create", "delete"):
        updates["project_structure"] = ""


    _record_timing(state, updates, iteration, "coder", coder_dur)
    return updates



def test_node(
    state: RepairState,
    db: Session | None = None,
) -> dict:
    """Execute Pytest after Coder modifications."""
    run_id = state.get("run_id", "")
    iteration = state.get("iteration", 1)
    project_path = Path(state["project_path"])

    _emit_event(
        db,
        run_id,
        iteration,
        "tester",
        "TEST_STARTED",
        {
            "node": "test",
            "agent": "Test Agent",
            "phase": "Test & Validation",
            "description": (
                f"Iteration {iteration}: Running pytest to validate synthesized patch..."
            ),
        },
    )
    logger.info("[TEST START] run_id=%s iteration=%d", run_id, iteration)

    start_t = time.monotonic()
    res: TestResult = get_execution_backend().run_pytest(project_path)
    pytest_dur = time.monotonic() - start_t
    res_dict = res.model_dump()

    _emit_event(
        db,
        run_id,
        iteration,
        "tester",
        "TEST_COMPLETED",
        {
            "node": "test",
            "agent": "Test Agent",
            "phase": "Test & Validation",
            "description": (
                f"Iteration {iteration}: Pytest finished with {res.passed} passed, "
                f"{res.failed} failed in {pytest_dur:.2f}s."
            ),
            "exit_code": res.exit_code,
            "passed": res.passed,
            "failed": res.failed,
            "duration": res.duration,
        },
    )
    logger.info(
        "[TEST COMPLETE] run_id=%s iteration=%d passed=%d failed=%d exit_code=%d duration=%.2fs",
        run_id, iteration, res.passed, res.failed, res.exit_code, pytest_dur,
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

    curr_fp = compute_failure_fingerprint(res)
    prev_fps = list(state.get("previous_failures") or [])

    updates: dict = {
        "test_result": res_dict,
        "final_failed_count": res.failed,
    }

    if not res.success:
        eff_max = state.get("max_iterations", settings.max_agent_iterations)
        git_diff = state.get("git_diff") or {}
        has_changes = bool(git_diff.get("has_changes", False)) if isinstance(git_diff, dict) else False

        if is_repeated_failure(curr_fp, prev_fps, threshold=2) and not has_changes:
            logger.warning(
                "[REPAIR STALLED] run_id=%s No effective code change produced for failing test (%s) -> STALLED",
                run_id, curr_fp,
            )
            updates["status"] = "stalled"
            updates["termination_reason"] = "repeated_failure"
        elif is_repeated_failure(curr_fp, prev_fps, threshold=3):

            logger.warning(
                "[REPAIR STALLED] run_id=%s Repeated failure detected (%s) -> STALLED",
                run_id, curr_fp,
            )
            updates["status"] = "stalled"
            updates["termination_reason"] = "repeated_failure"
        elif iteration >= eff_max:
            logger.info(
                "[REPAIR FAILED] run_id=%s Max iterations (%d) reached -> END",
                run_id, eff_max,
            )
            updates["status"] = "failed"
            updates["termination_reason"] = "max_iterations_reached"
        else:
            updates["iteration"] = iteration + 1
            updates["previous_failures"] = prev_fps + [curr_fp]

    _record_timing(state, updates, iteration, "pytest", pytest_dur)
    return updates



# Prevent pytest from auto-collecting LangGraph node functions as test cases
test_node.__test__ = False
initial_test_node.__test__ = False


def reviewer_node(
    state: RepairState,
    llm_provider: BaseLLMProvider,
    db: Session | None = None,
) -> dict:
    """Invoke Reviewer Agent to audit changes and test outputs."""
    run_id = state.get("run_id", "")
    iteration = state.get("iteration", 1)
    project_path = state["project_path"]

    _emit_event(
        db,
        run_id,
        iteration,
        "reviewer",
        "REVIEWER_STARTED",
        {
            "node": "reviewer",
            "agent": "Reviewer Agent",
            "phase": "Reviewer Gate",
            "description": (
                f"Iteration {iteration}: Auditing code changes for safety, style, and regression "
                "risks..."
            ),
        },
    )
    logger.info("[REVIEWER START] run_id=%s iteration=%d", run_id, iteration)

    start_t = time.monotonic()
    wm = WorkspaceManager.from_project_path(project_path)
    agent = ReviewerAgent(llm_provider)

    code_change = CodeChange(**state["code_change"]) if state.get("code_change") else None
    init_data = state.get("initial_test_result")
    initial_res = TestResult(**init_data) if init_data else None
    new_res = TestResult(**state["test_result"]) if state.get("test_result") else None

    cached_diff = GitDiff(**state["git_diff"]) if state.get("git_diff") else None
    review: ReviewResult = agent.review(
        workspace=wm,
        coder_explanation=code_change.explanation if code_change else "",
        initial_test_result=initial_res,
        new_test_result=new_res,
        run_id=run_id,
        db=db,
        git_diff=cached_diff,
    )

    rev_dur = time.monotonic() - start_t

    review_dict = review.model_dump()
    upsert_iteration(
        db=db,
        run_id=run_id,
        iteration_number=iteration,
        review_result=review_dict,
        approved=review.approved,
    )

    appr_str = "approved ✓" if review.approved else "rejected ✗"
    _emit_event(
        db,
        run_id,
        iteration,
        "reviewer",
        "REVIEWER_COMPLETED",
        {
            "node": "reviewer",
            "agent": "Reviewer Agent",
            "phase": "Reviewer Gate",
            "description": (
                f"Iteration {iteration}: Reviewer {appr_str} "
                f"patch in {rev_dur:.2f}s (Regression Risk: {review.regression_risk.upper()})."
            ),
            "approved": review.approved,
            "root_cause_fixed": review.root_cause_fixed,
            "regression_risk": review.regression_risk,
            "duration": round(rev_dur, 2),
        },
    )
    logger.info(
        "[REVIEWER COMPLETE] run_id=%s iteration=%d approved=%s risk=%s duration=%.2fs",
        run_id, iteration, review.approved, review.regression_risk, rev_dur,
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
    else:
        eff_max = state.get("max_iterations", settings.max_agent_iterations)
        curr_fp = compute_failure_fingerprint(new_res)
        prev_fps = list(state.get("previous_failures") or [])
        if is_repeated_failure(curr_fp, prev_fps, threshold=2):
            logger.warning(
                "[REPAIR STALLED] run_id=%s Repeated failure detected (%s) -> STALLED",
                run_id, curr_fp,
            )
            updates["status"] = "stalled"
            updates["termination_reason"] = "repeated_failure"
        elif iteration >= eff_max:
            logger.info(
                "[REPAIR FAILED] run_id=%s Max iterations (%d) reached -> END",
                run_id, eff_max,
            )
            updates["status"] = "failed"
            updates["termination_reason"] = "reviewer_rejected"
        else:
            updates["iteration"] = iteration + 1
            updates["previous_failures"] = prev_fps + [curr_fp]

    _record_timing(state, updates, iteration, "reviewer", rev_dur)
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
        if iteration > 0:
            run_rec = db.get(Run, run_id)
            if run_rec and run_rec.current_iteration < iteration:
                run_rec.current_iteration = iteration
        db.commit()
    except Exception as exc:
        logger.warning("Failed to emit event %s: %s", event_type, exc)

