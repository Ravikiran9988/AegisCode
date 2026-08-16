"""
Database Persistence Helpers for AegisCode.

Provides authoritative upsert functions for Iteration and Run records,
ensuring all agent outputs (Architect, Coder, Test, Reviewer) and test metrics
are immediately and transactionally committed to the database.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from backend.core.logging import get_logger
from backend.database.models import Iteration

logger = get_logger(__name__)


def upsert_iteration(
    db: Session | None,
    run_id: str,
    iteration_number: int,
    architecture_plan: dict[str, Any] | None = None,
    code_changes: list[dict[str, Any]] | dict[str, Any] | None = None,
    test_results: dict[str, Any] | None = None,
    review_result: dict[str, Any] | None = None,
    tests_passed: int | None = None,
    tests_failed: int | None = None,
    approved: bool | None = None,
    duration_seconds: float | None = None,
) -> Iteration | None:
    """
    Atomically insert or update an Iteration record for a given run and iteration number.

    Commits immediately so that data is visible in real-time to status and results endpoints.
    """
    if not db or not run_id:
        return None

    try:
        it = (
            db.query(Iteration)
            .filter(
                Iteration.run_id == run_id,
                Iteration.iteration_number == iteration_number,
            )
            .first()
        )
        if not it:
            it = Iteration(
                run_id=run_id,
                iteration_number=iteration_number,
            )
            db.add(it)

        if architecture_plan is not None:
            it.architecture_plan = architecture_plan
        if code_changes is not None:
            if isinstance(code_changes, dict):
                code_changes = [code_changes]
            it.code_changes = code_changes
        if test_results is not None:
            it.test_results = test_results
        if review_result is not None:
            it.review_result = review_result
        if tests_passed is not None:
            it.tests_passed = tests_passed
        if tests_failed is not None:
            it.tests_failed = tests_failed
        if approved is not None:
            it.approved = approved
        if duration_seconds is not None:
            it.duration_seconds = duration_seconds

        db.commit()
        db.refresh(it)
        return it

    except Exception as exc:
        logger.warning(
            "Failed to upsert iteration (run_id=%s, iteration=%d): %s",
            run_id, iteration_number, exc,
        )
        try:
            db.rollback()
        except Exception:
            pass
        return None
