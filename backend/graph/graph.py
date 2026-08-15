"""
LangGraph State Machine Assembly — Phase 4.

Assembles the StateGraph self-healing repair loop:
START -> INITIAL_TEST -> ARCHITECT -> CODER -> TEST -> REVIEWER -> DECISION
                                                                      ├── PASS -> END
                                                                      ├── RETRY -> ARCHITECT
                                                                      └── LIMIT -> END
"""

from __future__ import annotations

import time
from functools import partial
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
from backend.llm.base import BaseLLMProvider
from backend.tools.pytest_runner import TestResult

logger = get_logger(__name__)


def decision_router(state: RepairState) -> Literal["retry", "end"]:
    """
    Deterministic decision function evaluating graph state after Reviewer node.

    Decision Rules
    --------------
    1. Status is already "error", "stalled", "passed", or "already_passing" -> END
    2. Tests pass (exit_code == 0) AND Reviewer approves -> END (status="passed")
    3. Iteration >= max_iterations -> END (status="failed")
    4. Repeated failure fingerprint 2+ times -> END (status="stalled")
    5. Otherwise -> RETRY (increment iteration, route back to Architect)
    """
    status = state.get("status", "running")
    if status in ("error", "stalled", "passed", "already_passing"):
        logger.info("Decision Router: Early termination due to status=%r", status)
        return "end"

    test_data = state.get("test_result")
    review_data = state.get("review_result")

    test_res = TestResult(**test_data) if test_data else None
    review_res = ReviewResult(**review_data) if review_data else None

    # Condition 1: Success & Approved
    if test_res and test_res.success and review_res and review_res.approved:
        logger.info("Decision Router: All tests pass and Reviewer approved -> END")
        state["status"] = "passed"
        state["termination_reason"] = "all_tests_passed"
        return "end"

    # Condition 2: Max Iterations Reached
    current_iteration = state.get("iteration", 1)
    max_iterations = state.get("max_iterations", settings.max_agent_iterations)
    if current_iteration >= max_iterations:
        logger.info("Decision Router: Max iterations (%d) reached -> END", max_iterations)
        state["status"] = "failed"
        state["termination_reason"] = "max_iterations_reached"
        return "end"

    # Condition 3: Loop Detection / Repeated Failures
    curr_fp = compute_failure_fingerprint(test_res)
    prev_fps = state.get("previous_failures", [])
    if is_repeated_failure(curr_fp, prev_fps, threshold=2):
        logger.warning("Decision Router: Repeated failure detected (%s) -> STALLED", curr_fp)
        state["status"] = "stalled"
        state["termination_reason"] = "repeated_failure"
        return "end"

    # Condition 4: Retry next iteration
    logger.info(
        "Decision Router: Retrying repair loop (iteration %d -> %d)",
        current_iteration, current_iteration + 1,
    )
    state["iteration"] = current_iteration + 1
    prev_fps.append(curr_fp)
    state["previous_failures"] = prev_fps

    return "retry"


def initial_test_router(state: RepairState) -> Literal["continue", "end"]:
    """Route after initial_test_node: if already passing, skip agents entirely."""
    status = state.get("status", "running")
    if status == "already_passing":
        return "end"
    return "continue"


def coder_router(state: RepairState) -> Literal["test", "end"]:
    """Route after coder_node: if policy violation or error occurred, terminate safely."""
    status = state.get("status", "running")
    if status == "error":
        return "end"
    return "test"


def build_repair_graph(
    llm_provider: BaseLLMProvider,
    db: Session | None = None,
) -> StateGraph:
    """
    Construct and compile the AegisCode LangGraph repair graph.
    """
    builder = StateGraph(RepairState)

    # Bind provider & db session to nodes using partials
    builder.add_node("initial_test", partial(initial_test_node, db=db))
    builder.add_node("architect", partial(architect_node, llm_provider=llm_provider, db=db))
    builder.add_node("coder", partial(coder_node, llm_provider=llm_provider, db=db))
    builder.add_node("test", partial(test_node, db=db))
    builder.add_node("reviewer", partial(reviewer_node, llm_provider=llm_provider, db=db))

    # Add edges
    builder.add_edge(START, "initial_test")

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
            "end": END,
        },
    )

    builder.add_edge("test", "reviewer")

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
    """
    High-level entry point to execute the repair graph for a run.
    """
    start_time = time.monotonic()
    eff_max = max_iterations or settings.max_agent_iterations

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
        "start_time": start_time,
        "total_duration": 0.0,
        "initial_failed_count": 0,
        "final_failed_count": 0,
        "tool_call_count": 0,
        "reviewer_rejections": 0,
    }

    graph = build_repair_graph(llm_provider=llm_provider, db=db)

    try:
        final_state = graph.invoke(initial_state)
    except Exception as exc:
        logger.error("Repair graph execution error: %s", exc)
        final_state = dict(initial_state)
        final_state["status"] = "error"
        final_state["termination_reason"] = f"llm_error: {exc}"

    # Ensure status is finalised if graph ended while status was still "running"
    if final_state.get("status") == "running":
        test_data = final_state.get("test_result")
        test_res = TestResult(**test_data) if test_data else None

        if test_res and test_res.success:
            final_state["status"] = "passed"
            final_state["termination_reason"] = "all_tests_passed"
        else:
            curr_fp = compute_failure_fingerprint(test_res)
            prev_fps = final_state.get("previous_failures", [])
            if is_repeated_failure(curr_fp, prev_fps, threshold=2):
                final_state["status"] = "stalled"
                final_state["termination_reason"] = "repeated_failure"
            elif final_state.get("iteration", 1) >= eff_max:
                final_state["status"] = "failed"
                final_state["termination_reason"] = "max_iterations_reached"
            else:
                final_state["status"] = "failed"
                final_state["termination_reason"] = "stopped"

    elapsed = time.monotonic() - start_time
    final_state["total_duration"] = elapsed

    # Update DB Run record status
    if db and run_id:
        try:
            run_rec = db.get(Run, run_id)
            if run_rec:
                run_rec.status = final_state.get("status", "error")
                run_rec.current_iteration = final_state.get("iteration", 1)
                run_rec.final_summary = (
                    f"Graph terminated with status={run_rec.status!r}, "
                    f"reason={final_state.get('termination_reason')!r}"
                )
                db.commit()
        except Exception as exc:
            logger.warning("Failed to update Run record status: %s", exc)

    return final_state
