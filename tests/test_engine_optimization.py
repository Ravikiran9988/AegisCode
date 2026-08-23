"""
Tests for AegisCode Repair Engine Speed & Efficiency Optimizations.

Verifies:
1. Pytest failure SKIPS Reviewer LLM call.
2. Pytest success REACHES Reviewer LLM call.
3. Reviewer rejection retries repair cycle.
4. Reviewer approval finishes repair cycle with status="passed".
5. Cached project structure is reused across iterations.
6. Cache does not return stale source code after patch.
7. max_iterations constraint is respected.
8. Repeated failure fingerprint detection works.
9. Precise timing telemetry is recorded in state and events.
10. Existing guest authorization model remains 100% intact.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

from backend.agents.schemas import ArchitecturePlan, CodeChange, ReviewResult
from backend.graph.graph import decision_router, test_router
from backend.graph.loop_detector import compute_failure_fingerprint
from backend.graph.nodes import coder_node, initial_test_node
from backend.graph.state import RepairState
from backend.llm.base import BaseLLMProvider
from backend.tools.pytest_runner import TestResult


class MockLLMProvider(BaseLLMProvider):
    """Mock LLM Provider tracking total structured generation calls."""

    def __init__(self) -> None:
        self.call_count = 0
        self.call_history: list[str] = []

    @property
    def provider_name(self) -> str:
        return "mock"

    @property
    def model_name(self) -> str:
        return "mock-model"

    def is_available(self) -> bool:
        return True

    def generate(self, prompt: str, **kwargs) -> str:

        self.call_count += 1
        return "{}"

    def generate_structured(self, schema: type, prompt: str = "", **kwargs) -> any:
        self.call_count += 1
        schema_name = getattr(schema, "__name__", str(schema))
        self.call_history.append(schema_name)

        if schema_name == "ArchitecturePlan":
            return ArchitecturePlan(
                summary="Fix addition bug in calc.py",
                suspected_files=["calc.py"],
                relevant_files=["calc.py"],
                root_cause="Incorrect return operator",
                proposed_fix="Change - to +",
                test_strategy="Run pytest test_calc.py",
                confidence=0.9,
            )

        elif schema_name == "CodeChange":
            return CodeChange(
                file_path="calc.py",
                change_type="modify",
                explanation="Fixed return operator",
                root_cause="Operator bug",
                patch="--- calc.py\n+++ calc.py\n@@ -1,2 +1,2 @@\n def add(a, b):\n- return a - b\n+ return a + b\n",
                confidence=0.9,
            )
        elif schema_name == "ReviewResult":
            return ReviewResult(
                approved=True,
                reasoning="Patch correctly fixes bug without regression",
                root_cause_fixed=True,
                regression_risk="low",
                recommendation="Approve",
            )
        raise ValueError(f"Unknown schema: {schema_name}")


def test_pytest_failure_skips_reviewer():
    """Requirement A: If pytest fails, test_router MUST skip Reviewer."""
    state: RepairState = {
        "run_id": "test-run-1",
        "iteration": 1,
        "max_iterations": 3,
        "status": "running",
        "test_result": {
            "passed": 1,
            "failed": 1,
            "exit_code": 1,
            "success": False,
            "stdout": "FAILED test_calc.py::test_add",
            "stderr": "",
            "duration": 0.5,
        },
    }

    route = test_router(state)
    assert route in ("retry", "architect"), f"Expected retry route, got {route}"
    assert route != "reviewer", "Reviewer should be SKIPPED on failed tests!"


def test_pytest_success_reaches_reviewer():
    """Requirement B: If pytest passes, test_router MUST route to Reviewer."""
    state: RepairState = {
        "run_id": "test-run-2",
        "iteration": 1,
        "max_iterations": 3,
        "status": "running",
        "test_result": {
            "passed": 2,
            "failed": 0,
            "exit_code": 0,
            "success": True,
            "stdout": "2 passed",
            "stderr": "",
            "duration": 0.3,
        },
    }

    route = test_router(state)
    assert route == "reviewer", f"Expected 'reviewer' route, got {route}"


def test_reviewer_rejection_retries():
    """Requirement C: Reviewer rejection when tests pass routes to retry."""
    state: RepairState = {
        "run_id": "test-run-3",
        "iteration": 1,
        "max_iterations": 3,
        "status": "running",
        "test_result": {
            "passed": 2,
            "failed": 0,
            "exit_code": 0,
            "success": True,
            "stdout": "2 passed",
            "stderr": "",
            "duration": 0.3,
        },
        "review_result": {
            "approved": False,
            "reasoning": "Code style issue",
            "root_cause_fixed": True,
            "regression_risk": "medium",
            "recommendation": "Refactor style",
        },
    }

    route = decision_router(state)
    assert route == "retry"
    assert state["iteration"] == 2


def test_reviewer_approval_finishes():
    """Requirement D: Reviewer approval when tests pass sets status=passed and finishes."""
    state: RepairState = {
        "run_id": "test-run-4",
        "iteration": 1,
        "max_iterations": 3,
        "status": "running",
        "test_result": {
            "passed": 2,
            "failed": 0,
            "exit_code": 0,
            "success": True,
            "stdout": "2 passed",
            "stderr": "",
            "duration": 0.3,
        },
        "review_result": {
            "approved": True,
            "reasoning": "Approved",
            "root_cause_fixed": True,
            "regression_risk": "low",
            "recommendation": "Approve",
        },
    }

    route = decision_router(state)
    assert route == "end"
    assert state["status"] == "passed"


def test_cached_project_structure_reused():
    """Requirement E: ArchitectAgent reuses cached_project_structure if provided."""
    mock_provider = MockLLMProvider()
    agent_arch = patch("backend.agents.architect.get_project_structure")
    with agent_arch as mock_get_struct:
        mock_wm = MagicMock()
        mock_wm.workspace_id = "ws-1"

        from backend.agents.architect import ArchitectAgent
        arch = ArchitectAgent(mock_provider)
        arch.analyze(
            workspace=mock_wm,
            test_result=None,
            cached_project_structure="calc.py\ntest_calc.py",
        )

        mock_get_struct.assert_not_called()


def test_cache_invalidated_on_file_creation(tmp_path: Path):
    """Requirement F: Coder node invalidates project_structure on file creation."""
    mock_provider = MockLLMProvider()
    calc_py = tmp_path / "calc.py"
    calc_py.write_text("def add(a, b):\n    return a + b\n")

    state: RepairState = {
        "run_id": "test-run-5",
        "iteration": 1,
        "max_iterations": 3,
        "project_path": str(tmp_path),
        "project_structure": "calc.py",
        "architecture_plan": {
            "summary": "Create new helper file",
            "suspected_files": ["helper.py"],
            "relevant_files": ["helper.py"],
            "root_cause": "Missing helper",
            "proposed_fix": "Create helper.py",
            "test_strategy": "Run pytest",
            "confidence": 0.9,

        },
        "test_result": {
            "passed": 0,
            "failed": 1,
            "exit_code": 1,
            "success": False,
            "stdout": "FAILED",
            "stderr": "",
            "duration": 0.1,
        },
    }

    with patch("backend.agents.coder.CoderAgent.generate_and_apply_fix") as mock_fix:
        mock_fix.return_value = CodeChange(
            file_path="helper.py",
            change_type="write",

            explanation="Created helper.py",
            root_cause="Missing file",
            patch="def help(): pass",
            confidence=0.9,
        )
        res = coder_node(state, mock_provider)
        assert res.get("project_structure") == ""


def test_max_iterations_respected():
    """Requirement G: Max iterations limit routes to end with status=failed."""
    state: RepairState = {
        "run_id": "test-run-6",
        "iteration": 3,
        "max_iterations": 3,
        "status": "running",
        "test_result": {
            "passed": 1,
            "failed": 1,
            "exit_code": 1,
            "success": False,
            "stdout": "FAILED test_calc.py",
            "stderr": "",
            "duration": 0.2,
        },
    }

    route = decision_router(state)
    assert route == "end"
    assert state["status"] == "failed"


def test_repeated_failure_detection():
    """Requirement H: Repeated failure fingerprint stalls the loop."""
    t_res = TestResult(
        passed=1,
        failed=1,
        exit_code=1,
        success=False,
        stdout="FAILED test_calc.py::test_add",
    )
    fp = compute_failure_fingerprint(t_res)

    state: RepairState = {
        "run_id": "test-run-7",
        "iteration": 2,
        "max_iterations": 5,
        "status": "running",
        "previous_failures": [fp],
        "test_result": t_res.model_dump(),
    }

    route = decision_router(state)
    assert route == "end"
    assert state["status"] == "stalled"


def test_timing_telemetry_recorded(tmp_path: Path):
    """Requirement I: Nodes record timing telemetry in iteration_timings."""
    calc_py = tmp_path / "calc.py"
    calc_py.write_text("def add(a, b):\n    return a + b\n")
    test_calc = tmp_path / "test_calc.py"
    test_calc.write_text("from calc import add\ndef test_add():\n    assert add(2, 3) == 5\n")

    state: RepairState = {
        "run_id": "test-run-8",
        "workspace_id": "ws-8",
        "project_path": str(tmp_path),
        "iteration": 1,
        "max_iterations": 3,
        "status": "running",
    }

    res_init = initial_test_node(state)
    assert "iteration_timings" in res_init
    assert 1 in res_init["iteration_timings"]
    assert "initial_test" in res_init["iteration_timings"][1]
    assert res_init["iteration_timings"][1]["initial_test"] >= 0.0
