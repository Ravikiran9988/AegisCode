"""
LangGraph State Machine Assembly — Phase 4.

Assembles the AegisCode self-healing repair loop. The repair path keeps the
Architect result cached across normal test failures so retries go directly to
Coder instead of spending another LLM call re-analyzing the same failure.
"""

from __future__ import annotations

import time
from datetime import datetime, timezone
from functools import partial
from pathlib import Path
from typing import Literal

from langgraph.graph import END, START, StateGraph
from sqlalchemy.orm import Session

from backend.agents.schemas import ReviewResult
from backend.core.config import settings
from backend.core.logging import get_logger
from backend.database.models import Run
from backend.graph.loop_detector import compute_failure_fingerprint, is_repeated_failure
from backend.graph.nodes import (
    architect_node,
    coder_node,
    initial_test_node,
    reviewer_node,
    test_node,
)
from backend.graph.state import RepairState
from backend.llm.base import BaseLLMProvider, QuotaExhaustedError
from backend.llm.openai import RateLimitError
from backend.tools.git_tools import init_repo
from backend.tools.pytest_runner import TestResult

logger = get_logger(__name__)


def decision_router(state: RepairState) -> Literal["retry", "end"]:
    """Deterministically decide whether the reviewer-rejected repair should retry."""
    run_id = state.get("run_id", "")
    status = state.get("status", "running")
    current_iteration = state.get("iteration", 1)

    logger.info(
        "[ITERATION COMPLETE] run_id=%s iteration=%d status=%s",
        run_id, current_iteration, status,
    )

    if status in ("error", "stalled", "passed", "already_passing"):
        logger.info("[DECISION ROUTER] run_id=%s Early exit on status=%r", run_id, status)
        return "end"

    test_data = state.get("test_result")
    review_data = state.get("review_result")

    test_res = TestResult(**test_data) if test_data else None
    review_res = ReviewResult(**review_data) if review_data else None

    if test_res and test_res.success and review_res and review_res.approved:
        logger.info("[REPAIR SUCCESS] run_id=%s Tests pass and Reviewer approved -> END", run_id)
        state["status"] = "passed"
        state["termination_reason"] = "all_tests_passed"
        return "end"

    max_iterations = state.get("max_iterations", settings.max_agent_iterations)
    if current_iteration >= max_iterations:
        logger.info(
            "[REPAIR FAILED] run_id=%s Max iterations (%d) reached -> END",
            run_id, max_iterations,
        )
        state["status"] = "failed"
        state["termination_reason"] = "max_iterations_reached"
        return "end"

    curr_fp = compute_failure_fingerprint(test_res)
    prev_fps = state.get("previous_failures", [])
    if is_repeated_failure(curr_fp, prev_fps, threshold=2):
        logger.warning(
            "[REPAIR STALLED] run_id=%s Repeated failure detected (%s) -> STALLED",
            run_id, curr_fp,
        )
        state["status"] = "stalled"
        state["termination_reason"] = "repeated_failure"
        return "end"

    logger.info(
        "[DECISION ROUTER] Reviewer rejected; restarting from Architect: run_id=%s (iteration %d -> %d)",
        run_id, current_iteration, current_iteration + 1,
    )
    state["iteration"] = current_iteration + 1
    prev_fps.append(curr_fp)
    state["previous_failures"] = prev_fps

    return "retry"


def test_router(state: RepairState) -> Literal["reviewer", "coder_retry", "end"]:
    """Route after Pytest: review on success, reuse the existing plan on failure."""
    status = state.get("status", "running")
    if status in ("error", "stalled", "failed", "passed", "already_passing"):
        logger.info("[TEST ROUTER] Terminal status=%r -> ending graph", status)
        return "end"

    test_data = state.get("test_result")
    if not test_data:
        return "end"

    test_res = TestResult(**test_data)
    if test_res.success:
        logger.info("[TEST ROUTER] Pytest PASSED -> routing to Reviewer node")
        return "reviewer"

    # test_node has already advanced the iteration and recorded the failure.
    # Keep the existing ArchitecturePlan and let Coder use the fresh pytest
    # output. This removes one expensive Architect LLM call from every retry.
    logger.info(
        "[TEST ROUTER] Pytest FAILED (exit_code=%d, failed=%d) -> reusing architecture plan; routing directly to Coder",
        test_res.exit_code, test_res.failed,
    )
    return "coder_retry"


test_router.__test__ = False


def initial_test_router(state: RepairState) -> Literal["continue", "end"]:
    """Route after a fresh initial pytest pass."""
    status = state.get("status", "running")
    if status == "already_passing":
        return "end"
    return "continue"


def initial_entry_router(state: RepairState) -> Literal["run_initial_test", "architect", "end"]:
    """Skip duplicate baseline pytest when POST /runs already persisted its result."""
    baseline = state.get("initial_test_result")
    if baseline:
        if TestResult(**baseline).success:
            state["status"] = "already_passing"
            state["termination_reason"] = "all_tests_passed"
            return "end"
        return "architect"
    return "run_initial_test"


def coder_router(state: RepairState) -> Literal["test", "coder_retry", "architect_retry", "end"]:
    """Route patch failures directly back to repair instead of validating unchanged code."""
    status = state.get("status", "running")
    if status in ("error", "failed", "stalled"):
        return "end"

    patch_status = state.get("patch_status")
    if patch_status == "failed":
        patch_retries = state.get("patch_retry_count", 0)
        eff_max = state.get("max_iterations", settings.max_agent_iterations)
        current_iter = state.get("iteration", 1)
        if patch_retries >= 3 or current_iter >= eff_max:
            if current_iter >= eff_max:
                return "end"
            return "architect_retry"
        return "coder_retry"

    return "test"


def build_repair_graph(
    llm_provider: BaseLLMProvider,
    db: Session | None = None,
) -> StateGraph:
    """Construct and compile the AegisCode LangGraph repair graph."""
    builder = StateGraph(RepairState)

    builder.add_node("initial_test", partial(initial_test_node, db=db))
    builder.add_node("architect", partial(architect_node, llm_provider=llm_provider, db=db))
    builder.add_node("coder", partial(coder_node, llm_provider=llm_provider, db=db))
    builder.add_node("test", partial(test_node, db=db))
    builder.add_node("reviewer", partial(reviewer_node, llm_provider=llm_provider, db=db))

    builder.add_conditional_edges(
        START,
        initial_entry_router,
        {
            "run_initial_test": "initial_test",
            "architect": "architect",
            "end": END,
        },
    )

    builder.add_conditional_edges(
        "initial_test",
        initial_test_router,
        {
            "continue": "architect",
            "end": END,
        },
    )

    builder.add_edge("architect", "coder")

    builder.add_conditional_edges(
        "coder",
        coder_router,
        {
            "test": "test",
            "coder_retry": "coder",
            "architect_retry": "architect",
            "end": END,
        },
    )

    builder.add_conditional_edges(
        "test",
        test_router,
        {
            "reviewer": "reviewer",
            "coder_retry": "coder",
            "end": END,
        },
    )

    builder.add_conditional_edges(
        "reviewer",
        decision_router,
        {
            "retry": "architect",
            "end": END,
        },
    )

    return builder.compile()


def run_repair_workflow(
    run_id: str,
    workspace_id: str,
    project_path: str,
    llm_provider: BaseLLMProvider,
    db: Session | None = None,
    max_iterations: int | None = None,
    custom_instructions: str | None = None,
) -> RepairState:
    """High-level entry point to execute the repair graph for a run."""
    start_time = time.monotonic()
    eff_max = max_iterations or settings.max_agent_iterations

    logger.info(
        "[RUN START] run_id=%s workspace_id=%s max_iterations=%d path=%s",
        run_id, workspace_id, eff_max, project_path,
    )

    init_repo(Path(project_path))

    # POST /api/runs already executes and persists the baseline pytest pass.
    # Reuse that result so the background graph does not run the same suite twice.
    persisted_baseline: dict | None = None
    if db and run_id:
        try:
            run_record = db.get(Run, run_id)
            if run_record:
                baseline_it = next(
                    (
                        it
                        for it in run_record.iterations
                        if it.iteration_number == 1 and it.test_results
                    ),
                    None,
                )
                if baseline_it:
                    persisted_baseline = dict(baseline_it.test_results)
        except Exception as exc:
            logger.warning("Failed to load persisted baseline for run %s: %s", run_id, exc)

    initial_failed = int((persisted_baseline or {}).get("failed", 0))
    initial_state: RepairState = {
        "run_id": run_id,
        "workspace_id": workspace_id,
        "project_path": project_path,
        "iteration": 1,
        "max_iterations": eff_max,
        "project_structure": "",
        "custom_instructions": custom_instructions,
        "previous_failures": [],
        "repeated_failure_count": 0,
        "status": "running",
        "termination_reason": None,
        "patch_status": None,
        "patch_error": None,
        "files_modified": [],
        "patch_retry_count": 0,
        "coder_status": None,
        "validation_status": "pending",
        "targeted_test_status": "pending",
        "iteration_reason": None,
        "start_time": start_time,
        "total_duration": 0.0,
        "initial_failed_count": initial_failed,
        "final_failed_count": initial_failed,
        "tool_call_count": 0,
        "reviewer_rejections": 0,
    }

    if persisted_baseline:
        initial_state["initial_test_result"] = persisted_baseline
        initial_state["test_result"] = persisted_baseline
        initial_state["validation_status"] = "passed" if not initial_failed else "failed"

    graph = build_repair_graph(llm_provider=llm_provider, db=db)

    try:
        final_state = graph.invoke(initial_state)
    except QuotaExhaustedError as exc:
        logger.error("[QUOTA EXHAUSTED] run_id=%s: %s", run_id, exc)
        final_state = dict(initial_state)
        final_state["status"] = "failed"
        final_state["termination_reason"] = "quota_exhausted"
        final_state["final_summary"] = str(exc)
    except RateLimitError as exc:
        logger.warning("[RATE LIMIT EXCEEDED] run_id=%s: %s", run_id, exc)
        final_state = dict(initial_state)
        final_state["status"] = "error"
        final_state["termination_reason"] = f"rate_limit_exceeded: {exc}"
    except Exception as exc:
        logger.error("[REPAIR GRAPH ERROR] run_id=%s: %s", run_id, exc)
        final_state = dict(initial_state)
        final_state["status"] = "error"
        final_state["termination_reason"] = f"llm_error: {exc}"

    if final_state.get("status") in ("running", "passed"):
        test_data = final_state.get("test_result")
        review_data = final_state.get("review_result")
        test_res = TestResult(**test_data) if test_data else None
        review_res = ReviewResult(**review_data) if review_data else None

        if test_res and test_res.success and review_res and review_res.approved:
            final_state["status"] = "passed"
            final_state["termination_reason"] = "all_tests_passed"
        elif final_state.get("status") == "already_passing":
            pass
        elif final_state.get("iteration", 1) >= eff_max:
            final_state["status"] = "failed"
            final_state["termination_reason"] = (
                "reviewer_rejected"
                if (review_res and not review_res.approved)
                else "max_iterations_reached"
            )
        else:
            final_state["status"] = "failed"
            final_state["termination_reason"] = (
                "reviewer_rejected"
                if (review_res and not review_res.approved)
                else "stopped"
            )

    elapsed = time.monotonic() - start_time
    final_state["total_duration"] = elapsed

    if db and run_id:
        try:
            run_rec = db.get(Run, run_id)
            if run_rec:
                run_rec.status = final_state.get("status", "error")
                run_rec.current_iteration = final_state.get("iteration", 1)
                run_rec.finished_at = datetime.now(timezone.utc)
                run_rec.final_summary = (
                    f"Graph terminated with status={run_rec.status!r}, "
                    f"reason={final_state.get('termination_reason')!r}"
                )
                db.commit()
        except Exception as exc:
            logger.warning("Failed to update Run record status: %s", exc)

    timings = final_state.get("iteration_timings", {})
    for it_num, t_map in timings.items():
        arch_t = t_map.get("architect", 0.0)
        coder_t = t_map.get("coder", 0.0)
        test_t = t_map.get("pytest", 0.0)
        rev_t_val = t_map.get("reviewer")
        rev_str = f"{rev_t_val:.2f}s" if rev_t_val is not None else "skipped (tests failed)"
        iter_tot = round(sum(v for v in t_map.values() if isinstance(v, int | float)), 2)

        logger.info(
            "[TIMING TELEMETRY] run_id=%s iteration=%d | Architect: %.2fs | Coder: %.2fs | Pytest: %.2fs | Reviewer: %s | Iteration total: %.2fs",
            run_id, it_num, arch_t, coder_t, test_t, rev_str, iter_tot,
        )

    logger.info(
        "[RUN COMPLETE] run_id=%s final_status=%s duration=%.2fs termination_reason=%s",
        run_id, final_state.get("status"), elapsed, final_state.get("termination_reason"),
    )

    return final_state
