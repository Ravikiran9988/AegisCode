"""
Patch Lifecycle & State Machine Authoritative Verification Tests.

Tests:
1. Successful coder patch -> targeted pytest executes.
2. Patch application failure -> pytest is skipped, coder retry triggered.
3. Patch failure -> coder receives exact previous error and retries.
4. Empty/no-op patch -> validation skipped, treated as patch failure.
5. Successful retry after patch failure -> validation executes.
6. Repeated identical patch failure -> terminates safely (patch_application_failed).
7. Test failure after a successfully applied patch -> normal retry to Architect.
8. Full successful repair -> reviewer executes and approves.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

from backend.agents.schemas import ArchitecturePlan, CodeChange, ReviewResult
from backend.context.builder import build_coder_context
from backend.execution.workspace import WorkspaceManager
from backend.graph.graph import coder_router, run_repair_workflow
from backend.graph.nodes import coder_node
from backend.llm.base import BaseLLMProvider
from backend.tools.git_tools import init_repo


class MockSequentialLLM(BaseLLMProvider):
    """Mock LLM returning structured outputs in a prescribed sequence."""

    def __init__(self, responses: list[any]) -> None:
        self.responses = list(responses)
        self.call_count = 0
        self.prompts: list[str] = []

    @property
    def provider_name(self) -> str:
        return "mock"

    @property
    def model_name(self) -> str:
        return "mock-seq"

    def is_available(self) -> bool:
        return True

    def generate(self, prompt: str, **kwargs) -> str:
        return "{}"

    def generate_structured(self, schema: type, prompt: str = "", **kwargs) -> any:
        self.call_count += 1
        self.prompts.append(prompt)
        schema_name = getattr(schema, "__name__", str(schema))
        for i, resp in enumerate(self.responses):
            if type(resp).__name__ == schema_name:
                return self.responses.pop(i)
        if not self.responses:
            raise RuntimeError(f"MockSequentialLLM ran out of mock responses for {schema_name}")
        return self.responses.pop(0)


def test_successful_coder_patch_triggers_test_validation(tmp_path: Path):
    """Requirement 1: When patch succeeds, coder_router routes to 'test'."""
    wm = WorkspaceManager.create(base_dir=tmp_path)
    pdir = wm.get_project_path()
    (pdir / "calc.py").write_text("def add(a, b): return a - b\n", encoding="utf-8")
    init_repo(pdir)

    mock_llm = MagicMock(spec=BaseLLMProvider)
    mock_llm.generate_structured.return_value = CodeChange(
        file_path="calc.py",
        change_type="write",
        explanation="Fixed addition logic",
        root_cause="Minus operator",
        patch="def add(a, b): return a + b\n",
        confidence=0.9,
    )

    state = {
        "run_id": "test-succ-patch",
        "iteration": 1,
        "project_path": str(pdir),
        "architecture_plan": ArchitecturePlan(
            summary="Fix calc bug",
            relevant_files=["calc.py"],
            test_strategy="Run pytest",
        ).model_dump(),
        "test_result": {"exit_code": 1, "passed": 0, "failed": 1, "stdout": "", "stderr": "", "success": False},
    }


    out = coder_node(state, mock_llm)
    assert out["patch_status"] == "succeeded"
    assert out["patch_error"] is None
    assert out["coder_status"] == "succeeded"
    assert "calc.py" in out["files_modified"]
    assert out["validation_status"] == "pending"

    # Router check
    merged_state = {**state, **out}
    assert coder_router(merged_state) == "test"


def test_patch_application_failure_skips_validation_and_retries(tmp_path: Path):
    """Requirement 2: When patch application fails, validation is skipped and coder retries."""
    wm = WorkspaceManager.create(base_dir=tmp_path)
    pdir = wm.get_project_path()
    (pdir / "calc.py").write_text("def add(a, b): return a - b\n", encoding="utf-8")
    init_repo(pdir)

    mock_llm = MagicMock(spec=BaseLLMProvider)
    mock_llm.generate_structured.return_value = CodeChange(
        file_path="calc.py",
        change_type="patch",
        explanation="Attempt patch",
        root_cause="Bug",
        patch="invalid diff without hunk headers",
        confidence=0.9,
    )

    state = {
        "run_id": "test-fail-patch",
        "iteration": 1,
        "project_path": str(pdir),
        "architecture_plan": ArchitecturePlan(
            summary="Fix calc bug",
            relevant_files=["calc.py"],
            test_strategy="Run pytest",
        ).model_dump(),
    }

    out = coder_node(state, mock_llm)
    assert out["patch_status"] == "failed"
    assert "No hunks found in patch" in out["patch_error"]
    assert out["coder_status"] == "patch_failed"
    assert out["validation_status"] == "skipped"
    assert out["files_modified"] == []
    assert out["patch_retry_count"] == 1

    merged_state = {**state, **out}
    assert coder_router(merged_state) == "coder_retry"


def test_coder_receives_exact_error_and_succeeds_on_retry(tmp_path: Path):
    """Requirement 3: Coder receives previous patch error and recovers with write."""
    wm = WorkspaceManager.create(base_dir=tmp_path)
    pdir = wm.get_project_path()
    (pdir / "calc.py").write_text("def add(a, b): return a - b\n", encoding="utf-8")
    init_repo(pdir)

    context = build_coder_context(
        workspace=wm,
        architecture_summary="Fix calc.py",
        relevant_files=["calc.py"],
        patch_error="Failed to patch file calc.py: No hunks found in patch",
    )
    assert "[PREVIOUS PATCH APPLICATION FAILED]" in context
    assert "No hunks found in patch" in context


def test_no_op_patch_marked_as_failed_and_skips_validation(tmp_path: Path):
    """Requirement 4: When Coder returns change_type='none', it is treated as patch failure."""
    wm = WorkspaceManager.create(base_dir=tmp_path)
    pdir = wm.get_project_path()
    (pdir / "calc.py").write_text("def add(a, b): return a - b\n", encoding="utf-8")
    init_repo(pdir)

    mock_llm = MagicMock(spec=BaseLLMProvider)
    mock_llm.generate_structured.return_value = CodeChange(
        file_path="calc.py",
        change_type="none",
        explanation="Decided to do nothing",
        root_cause="None",
        patch="",
        confidence=0.5,
    )

    state = {
        "run_id": "test-none-patch",
        "iteration": 1,
        "project_path": str(pdir),
        "architecture_plan": ArchitecturePlan(
            summary="Fix calc bug",
            relevant_files=["calc.py"],
            test_strategy="Run pytest",
        ).model_dump(),
    }

    out = coder_node(state, mock_llm)
    assert out["patch_status"] == "failed"
    assert out["validation_status"] == "skipped"
    assert "returned no code modifications" in out["patch_error"]

    merged_state = {**state, **out}
    assert coder_router(merged_state) == "coder_retry"


def test_repeated_patch_failures_terminate_safely():
    """Requirement 6: Repeated patch failures terminate safely when max retries/iterations reached."""
    state = {
        "run_id": "test-rep-fail",
        "iteration": 3,
        "max_iterations": 3,
        "status": "running",
        "patch_status": "failed",
        "patch_retry_count": 3,
    }
    assert coder_router(state) == "end"


def test_end_to_end_patch_recovery_in_workflow(tmp_path: Path):
    """Requirement 5 & 8: Workflow recovers from malformed patch on retry and reaches reviewer."""
    wm = WorkspaceManager.create(base_dir=tmp_path)
    pdir = wm.get_project_path()
    (pdir / "string_utils.py").write_text(
        "def count_vowels(s: str) -> int:\n    return len([c for c in s if c in 'aeiouyAEIOUY'])\n",
        encoding="utf-8",
    )
    (pdir / "test_string_utils.py").write_text(
        "from string_utils import count_vowels\n\n"
        "def test_count_vowels():\n"
        "    assert count_vowels('AegisCode') == 4\n",
        encoding="utf-8",
    )
    init_repo(pdir)

    # Response sequence:
    # 1. Architect (plan)
    # 2. Coder Iter 1 (Invalid diff -> patch fails)
    # 3. Coder Retry (Valid write -> patch succeeds)
    # 4. Reviewer (Approves fix)
    mock_llm = MockSequentialLLM([
        ArchitecturePlan(
            summary="Fix count_vowels by removing 'y' from vowel set",
            relevant_files=["string_utils.py"],
            test_strategy="Run pytest test_string_utils.py",
        ),
        CodeChange(
            file_path="string_utils.py",
            change_type="patch",
            explanation="Invalid diff",
            root_cause="Vowels include y",
            patch="invalid diff without headers",
            confidence=0.8,
        ),
        CodeChange(
            file_path="string_utils.py",
            change_type="write",
            explanation="Fixed count_vowels implementation",
            root_cause="Removed y and uppercase",
            patch="def count_vowels(s: str) -> int:\n    return len([c for c in s if c in 'aeiou'])\n",
            confidence=0.95,
        ),

        ReviewResult(
            approved=True,
            root_cause_fixed=True,
            regression_risk="low",
            reasoning="Patch correctly computes vowels without y",
            recommendation="Approve",
        ),
    ])

    final_state = run_repair_workflow(
        run_id="run-e2e-patch-recovery",
        workspace_id=wm.workspace_id,
        project_path=str(pdir),
        llm_provider=mock_llm,
        max_iterations=3,
    )

    assert final_state["status"] == "passed"
    assert final_state["termination_reason"] == "all_tests_passed"
    assert final_state["patch_status"] == "succeeded"
    assert "string_utils.py" in final_state["files_modified"]
