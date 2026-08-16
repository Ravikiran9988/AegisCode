"""
Coder Agent — Phase 3.

Receives ArchitecturePlan and current test failure, generates a minimal targeted
CodeChange, and applies the change to the workspace using secure tools.

Policy Enforcement
------------------
Before executing `write_file` or `apply_patch`, Coder evaluates
`check_file_modification_policy()`. Disallowed modifications (e.g. altering test files)
are blocked at tool invocation time and raise a PolicyViolationError.
"""

from __future__ import annotations

import ast

from sqlalchemy.orm import Session

from backend.agents.policies import PolicyViolationError, check_file_modification_policy
from backend.agents.prompts.coder import SYSTEM_PROMPT, TASK_PROMPT_TEMPLATE
from backend.agents.schemas import ArchitecturePlan, CodeChange
from backend.context.builder import build_coder_context
from backend.core.logging import get_logger
from backend.database.models import Event
from backend.execution.workspace import WorkspaceManager
from backend.llm.base import BaseLLMProvider
from backend.tools.filesystem import _clean_patch, apply_patch, write_file
from backend.tools.pytest_runner import TestResult

logger = get_logger(__name__)


class CoderAgent:
    """Coder Agent — generates and applies targeted code repairs."""

    def __init__(self, llm_provider: BaseLLMProvider) -> None:
        self.llm = llm_provider

    def generate_and_apply_fix(
        self,
        workspace: WorkspaceManager,
        plan: ArchitecturePlan,
        test_result: TestResult | None = None,
        run_id: str | None = None,
        db: Session | None = None,
        allow_test_modification: bool = False,
    ) -> CodeChange:
        """
        Generate a CodeChange schema from context, evaluate security policies,
        and apply the modification to the project workspace.
        """
        _emit_agent_event(db, run_id, "coder", "CODER_STARTED")
        logger.info(
            "[CODER START] run_id=%s workspace=%s relevant_files=%s",
            run_id, workspace.workspace_id, plan.relevant_files,
        )

        # Step 1: Build context & generate CodeChange proposal from LLM
        context = build_coder_context(
            workspace=workspace,
            architecture_summary=plan.summary,
            relevant_files=plan.relevant_files,
            test_result=test_result,
        )
        prompt = TASK_PROMPT_TEMPLATE.format(context=context)

        try:
            change: CodeChange = self.llm.generate_structured(
                schema=CodeChange,
                prompt=prompt,
                system_prompt=SYSTEM_PROMPT,
            )
        except Exception as exc:
            _emit_agent_event(db, run_id, "coder", "LLM_ERROR", {"error": str(exc)})
            logger.error("CoderAgent LLM error: %s", exc)
            raise

        # If no change is proposed, finish early
        if change.change_type == "none" or not change.file_path:
            logger.info("CoderAgent proposed no changes.")
            _emit_agent_event(
                db, run_id, "coder", "CODER_COMPLETED",
                {"change_type": "none", "explanation": change.explanation}
            )
            return change

        # Step 2: Security Policy Check BEFORE applying tool call
        try:
            check_file_modification_policy(
                relative_path=change.file_path,
                allow_test_modification=allow_test_modification,
            )
        except PolicyViolationError as exc:
            _emit_agent_event(
                db, run_id, "coder", "TOOL_FAILED",
                {"tool": change.change_type, "path": change.file_path, "error": str(exc)}
            )
            logger.warning("CoderAgent security policy violation blocked: %s", exc)
            raise

        # Step 3: Execute tool modification
        logger.info(
            "[PATCH START] run_id=%s file=%s type=%s",
            run_id, change.file_path, change.change_type,
        )

        if change.change_type == "write":
            _emit_agent_event(
                db, run_id, "coder", "TOOL_CALLED",
                {"tool": "write_file", "path": change.file_path}
            )
            write_res = write_file(workspace, change.file_path, change.patch)
            if not write_res.success:
                _emit_agent_event(
                    db, run_id, "coder", "TOOL_FAILED",
                    {"tool": "write_file", "path": change.file_path, "error": write_res.error}
                )
                raise RuntimeError(f"Failed to write file {change.file_path}: {write_res.error}")

        elif change.change_type == "patch":
            _emit_agent_event(
                db, run_id, "coder", "TOOL_CALLED",
                {"tool": "apply_patch", "path": change.file_path}
            )
            patch_res = apply_patch(workspace, change.file_path, change.patch)
            if not patch_res.success:
                # Robust fallback: if patch has no hunks but is valid complete Python code
                clean_p = _clean_patch(change.patch)
                if "No hunks found in patch" in (patch_res.error or ""):
                    try:
                        ast.parse(clean_p)
                        logger.info(
                            "apply_patch had no hunks but is valid Python code — write_file %s",
                            change.file_path,
                        )
                        write_res = write_file(workspace, change.file_path, clean_p)
                        if write_res.success:
                            change.change_type = "write"
                            patch_res = patch_res.model_copy(
                                update={"success": True, "error": None}
                            )
                    except Exception as parse_err:
                        logger.debug("Patch text is not valid Python syntax: %s", parse_err)

                if not patch_res.success:
                    _emit_agent_event(
                        db, run_id, "coder", "TOOL_FAILED",
                        {"tool": "apply_patch", "path": change.file_path, "error": patch_res.error}
                    )
                    raise RuntimeError(
                        f"Failed to patch file {change.file_path}: {patch_res.error}"
                    )

        logger.info(
            "[PATCH COMPLETE] run_id=%s file=%s type=%s",
            run_id, change.file_path, change.change_type,
        )

        _emit_agent_event(
            db, run_id, "coder", "CODER_COMPLETED",
            {
                "file_path": change.file_path,
                "change_type": change.change_type,
                "explanation": change.explanation,
            }
        )
        logger.info(
            "[CODER COMPLETE] run_id=%s successfully applied %s to %s",
            run_id, change.change_type, change.file_path,
        )
        return change


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
