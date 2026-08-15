"""
LangGraph Repair State — Phase 4.

Strongly typed state definition for the AegisCode self-healing repair graph.
Passed between graph nodes and updated during state transitions.
"""

from __future__ import annotations

from typing import Any, TypedDict


class RepairState(TypedDict, total=False):
    """
    State dictionary for the AegisCode LangGraph repair graph.
    """

    # Identifiers & Environment
    run_id: str
    workspace_id: str
    project_path: str

    # Iteration bounds
    iteration: int
    max_iterations: int

    # Project context
    project_structure: str
    custom_instructions: str | None

    # Node outputs
    initial_test_result: dict[str, Any] | None
    test_result: dict[str, Any] | None
    architecture_plan: dict[str, Any] | None
    code_change: dict[str, Any] | None
    review_result: dict[str, Any] | None
    git_diff: dict[str, Any] | None

    # Failure history & Loop detection
    previous_failures: list[str]  # list of failure fingerprints
    repeated_failure_count: int

    # Overall Graph Status & Termination
    status: str  # "running", "passed", "failed", "stalled", "already_passing", "error"
    termination_reason: str | None
    # Options: "all_tests_passed", "max_iterations_reached", "repeated_failure",
    #          "policy_violation", "llm_error", "workspace_error"

    # Evaluation Metrics
    start_time: float
    total_duration: float
    initial_failed_count: int
    final_failed_count: int
    tool_call_count: int
    reviewer_rejections: int
