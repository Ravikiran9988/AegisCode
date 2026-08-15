"""
Architect Agent — Phase 3.

Inspects project structure and failing test outputs, then uses an LLM to produce
a structured ArchitecturePlan.

Read-only agent: cannot modify files.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from backend.agents.prompts.architect import SYSTEM_PROMPT, TASK_PROMPT_TEMPLATE
from backend.agents.schemas import ArchitecturePlan
from backend.context.builder import build_architect_context
from backend.core.logging import get_logger
from backend.database.models import Event
from backend.execution.workspace import WorkspaceManager
from backend.llm.base import BaseLLMProvider
from backend.tools.filesystem import get_project_structure, list_files
from backend.tools.pytest_runner import TestResult

logger = get_logger(__name__)


class ArchitectAgent:
    """Architect Agent — analyzes structure & failure logs to create a repair plan."""

    def __init__(self, llm_provider: BaseLLMProvider) -> None:
        self.llm = llm_provider

    def analyze(
        self,
        workspace: WorkspaceManager,
        test_result: TestResult | None = None,
        run_id: str | None = None,
        db: Session | None = None,
    ) -> ArchitecturePlan:
        """
        Analyze the project workspace and return a validated ArchitecturePlan.
        """
        _emit_agent_event(db, run_id, "architect", "ARCHITECT_STARTED")
        logger.info("ArchitectAgent starting analysis for workspace %s", workspace.workspace_id)

        # Step 1: Read-only tool calls for inspection
        _emit_agent_event(
            db, run_id, "architect", "TOOL_CALLED",
            {"tool": "get_project_structure"}
        )
        get_project_structure(workspace)

        _emit_agent_event(
            db, run_id, "architect", "TOOL_CALLED",
            {"tool": "list_files", "pattern": "**/*.py"}
        )
        file_list = list_files(workspace, "**/*.py")

        logger.debug(
            "Architect inspected structure: %d files found", file_list.files.__len__()
        )

        # Step 2: Build context & call LLM for structured output
        context = build_architect_context(workspace, test_result=test_result)
        prompt = TASK_PROMPT_TEMPLATE.format(context=context)

        try:
            plan: ArchitecturePlan = self.llm.generate_structured(
                schema=ArchitecturePlan,
                prompt=prompt,
                system_prompt=SYSTEM_PROMPT,
            )
            _emit_agent_event(
                db, run_id, "architect", "ARCHITECT_COMPLETED",
                {"summary": plan.summary, "relevant_files": plan.relevant_files}
            )
            logger.info("ArchitectAgent analysis complete. Relevant files: %s", plan.relevant_files)
            return plan

        except Exception as exc:
            _emit_agent_event(
                db, run_id, "architect", "LLM_ERROR",
                {"error": str(exc)}
            )
            logger.error("ArchitectAgent LLM error: %s", exc)
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
