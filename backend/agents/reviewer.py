"""
Reviewer Agent — Phase 3.

Independent code reviewer agent. Inspects git diff, coder explanation, and initial vs new
test results to produce a validated ReviewResult.

Read-only agent: cannot modify files.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from backend.agents.prompts.reviewer import SYSTEM_PROMPT, TASK_PROMPT_TEMPLATE
from backend.agents.schemas import ReviewResult
from backend.context.builder import build_reviewer_context
from backend.core.logging import get_logger
from backend.database.models import Event
from backend.execution.workspace import WorkspaceManager
from backend.llm.base import BaseLLMProvider
from backend.tools.git_tools import get_git_diff
from backend.tools.pytest_runner import TestResult

logger = get_logger(__name__)


class ReviewerAgent:
    """Reviewer Agent — evaluates code diffs and test results independently."""

    def __init__(self, llm_provider: BaseLLMProvider) -> None:
        self.llm = llm_provider

    def review(
        self,
        workspace: WorkspaceManager,
        coder_explanation: str,
        initial_test_result: TestResult | None = None,
        new_test_result: TestResult | None = None,
        run_id: str | None = None,
        db: Session | None = None,
    ) -> ReviewResult:
        """
        Inspect git diff and test results, returning a validated ReviewResult.
        """
        _emit_agent_event(db, run_id, "reviewer", "REVIEWER_STARTED")
        logger.info("ReviewerAgent starting review for workspace %s", workspace.workspace_id)

        # Step 1: Read-only tool call to get Git diff
        _emit_agent_event(
            db, run_id, "reviewer", "TOOL_CALLED",
            {"tool": "get_git_diff"}
        )
        git_diff = get_git_diff(workspace)

        # Step 2: Build context & call LLM for ReviewResult
        context = build_reviewer_context(
            workspace=workspace,
            git_diff=git_diff,
            coder_explanation=coder_explanation,
            initial_test_result=initial_test_result,
            new_test_result=new_test_result,
        )
        prompt = TASK_PROMPT_TEMPLATE.format(context=context)

        try:
            review_res: ReviewResult = self.llm.generate_structured(
                schema=ReviewResult,
                prompt=prompt,
                system_prompt=SYSTEM_PROMPT,
            )
            _emit_agent_event(
                db, run_id, "reviewer", "REVIEWER_COMPLETED",
                {
                    "approved": review_res.approved,
                    "root_cause_fixed": review_res.root_cause_fixed,
                    "regression_risk": review_res.regression_risk,
                }
            )
            logger.info("ReviewerAgent completed. Approved: %s", review_res.approved)
            return review_res

        except Exception as exc:
            _emit_agent_event(db, run_id, "reviewer", "LLM_ERROR", {"error": str(exc)})
            logger.error("ReviewerAgent LLM error: %s", exc)
            raise


def _emit_agent_event(
    db: Session | None,
    run_id: str | None,
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
        )
        db.add(ev)
        db.flush()
    except Exception as exc:
        logger.warning("Failed to emit agent event: %s", exc)
