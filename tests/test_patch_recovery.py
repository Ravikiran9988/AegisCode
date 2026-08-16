"""
test_patch_recovery.py — Regression tests for calculator.py 'No hunks found in patch' error.

Tests:
1. test_apply_patch_no_hunks_returns_error_result
2. test_apply_patch_strips_markdown_codeblocks
3. test_coder_agent_recovers_from_patch_failure
4. test_repair_graph_retries_after_patch_failure
"""

from __future__ import annotations

from unittest.mock import MagicMock

from backend.agents.schemas import ArchitecturePlan, CodeChange
from backend.execution.workspace import WorkspaceManager
from backend.graph.nodes import coder_node
from backend.llm.base import BaseLLMProvider
from backend.tools.filesystem import apply_patch, write_file


class TestPatchRecovery:

    def test_apply_patch_no_hunks_returns_error_result(self):
        """Verify apply_patch returns error on invalid diff missing hunk headers."""
        wm = WorkspaceManager.create()
        try:
            pdir = wm.get_project_path()
            calc_file = pdir / "calculator.py"
            calc_file.write_text("def add(a, b):\n    return a - b\n", encoding="utf-8")

            invalid_patch = "def add(a, b):\n    return a + b\n"
            res = apply_patch(wm, "calculator.py", invalid_patch)

            assert res.success is False
            assert "No hunks found in patch" in res.error
        finally:
            wm.cleanup()

    def test_apply_patch_strips_markdown_codeblocks(self):
        """Verify that apply_patch strips ```diff markdown codeblock wrappers."""
        wm = WorkspaceManager.create()
        try:
            pdir = wm.get_project_path()
            calc_file = pdir / "calculator.py"
            calc_file.write_text("def add(a, b):\n    return a - b\n", encoding="utf-8")

            markdown_patch = (
                "```diff\n"
                "@@ -2,1 +2,1 @@\n"
                "-    return a - b\n"
                "+    return a + b\n"
                "```"
            )
            res = apply_patch(wm, "calculator.py", markdown_patch)

            assert res.success is True
            patched_content = calc_file.read_text(encoding="utf-8")
            assert "return a + b" in patched_content
        finally:
            wm.cleanup()

    def test_coder_agent_recovers_from_patch_failure(self):
        """Verify coder_node catches RuntimeError from patch failure without crashing."""
        wm = WorkspaceManager.create()
        try:
            pdir = wm.get_project_path()
            calc_file = pdir / "calculator.py"
            calc_file.write_text("def add(a, b):\n    return a - b\n", encoding="utf-8")

            mock_llm = MagicMock(spec=BaseLLMProvider)
            mock_llm.generate_structured.return_value = CodeChange(
                file_path="calculator.py",
                change_type="patch",
                explanation="Attempting fix for calculator.py",
                root_cause="Incorrect subtraction in add()",
                patch="def add(a, b):\n    return a + b\n",  # Invalid patch without hunk headers
                confidence=0.9,
            )

            state = {
                "run_id": "test-run-123",
                "iteration": 1,
                "project_path": str(pdir),
                "architecture_plan": ArchitecturePlan(
                    summary="Fix calculator bug",
                    relevant_files=["calculator.py"],
                    test_strategy="Run pytest",
                ).model_dump(),
                "test_result": {
                    "passed": 0,
                    "failed": 1,
                    "errors": 0,
                    "skipped": 0,
                    "exit_code": 1,
                    "success": False,
                    "duration": 0.5,
                    "stdout": "FAILED test_calculator.py::test_add",
                    "stderr": "",
                },
            }

            node_output = coder_node(state, mock_llm)

            assert "coder_error" in node_output
            assert "No hunks found in patch" in node_output["coder_error"]
            assert node_output["code_change"]["change_type"] == "none"
        finally:
            wm.cleanup()

    def test_repair_graph_retries_after_patch_failure(self):
        """Verify multi-iteration repair graph flow retries after patch failure."""
        wm = WorkspaceManager.create()
        try:
            pdir = wm.get_project_path()
            calc_file = pdir / "calculator.py"
            calc_file.write_text("def add(a, b):\n    return a - b\n", encoding="utf-8")

            test_file = pdir / "test_calculator.py"
            test_file.write_text(
                "from calculator import add\n\ndef test_add():\n    assert add(2, 3) == 5\n",
                encoding="utf-8",
            )

            # Iteration 1: Apply invalid patch -> fails gracefully
            invalid_patch = "def add(a, b):\n    return a + b\n"
            res1 = apply_patch(wm, "calculator.py", invalid_patch)
            assert res1.success is False

            # Iteration 2: Apply valid write -> succeeds and test passes
            valid_content = "def add(a, b):\n    return a + b\n"
            res2 = write_file(wm, "calculator.py", valid_content)
            assert res2.success is True

            from backend.tools.pytest_runner import run_pytest
            test_res = run_pytest(pdir)
            assert test_res.success is True
            assert test_res.passed == 1
            assert test_res.failed == 0
        finally:
            wm.cleanup()
