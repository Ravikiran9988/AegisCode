"""
End-to-End Repair Engine Lifecycle & Reviewer Gate Regression Tests.

Tests:
1. String utils vowel repair: reproduces failing scenario, verifies test definitions reach agents,
   validates patch, confirms Reviewer Audit Gate executes and marks status='passed'.
2. No-op patch detection and rewrite recovery.
3. Multi-iteration failure progression: differing assertions continue to next iteration without premature stall.
4. Failed test validation skips Reviewer and reports status cleanly.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

from backend.agents.coder import CoderAgent
from backend.agents.schemas import ArchitecturePlan, CodeChange, ReviewResult
from backend.context.builder import build_architect_context, build_coder_context
from backend.database.models import Base
from backend.database.session import SessionLocal, engine
from backend.execution.workspace import WorkspaceManager
from backend.graph.graph import run_repair_workflow
from backend.llm.mock import MockLLMProvider
from backend.tools.filesystem import read_file
from backend.tools.git_tools import init_repo
from backend.tools.pytest_runner import TestResult


def setup_module():
    Base.metadata.create_all(bind=engine)


def test_vowel_repair_context_contains_test_assertions(tmp_path: Path):
    """Verify Architect and Coder contexts contain the exact test assertions."""
    wm = WorkspaceManager.create(base_dir=tmp_path)
    proj_dir = wm.get_project_path()

    (proj_dir / "string_utils.py").write_text(
        "def count_vowels(s: str) -> int:\n"
        "    vowels = 'aeiouyAEIOUY'\n"
        "    return sum(1 for c in s if c in vowels)\n",
        encoding="utf-8",
    )
    (proj_dir / "test_string_utils.py").write_text(
        "from string_utils import count_vowels\n\n"
        "def test_lowercase():\n"
        "    assert count_vowels('hello') == 2\n\n"
        "def test_aegiscode():\n"
        "    # Only lowercase vowels are counted in this spec\n"
        "    assert count_vowels('AegisCode') == 4\n",
        encoding="utf-8",
    )
    init_repo(proj_dir)

    t_res = TestResult(
        exit_code=1,
        passed=1,
        failed=1,
        success=False,
        stdout="FAILED test_string_utils.py::test_aegiscode - AssertionError: assert 5 == 4\nE   AssertionError: assert 5 == 4",
    )

    arch_ctx = build_architect_context(wm, test_result=t_res)
    assert "assert count_vowels('AegisCode') == 4" in arch_ctx
    assert "<untrusted_test_code>" in arch_ctx

    coder_ctx = build_coder_context(
        wm,
        architecture_summary="Adjust vowel set to count only lowercase vowels 'aeiou'",
        relevant_files=["string_utils.py"],
        test_result=t_res,
    )
    assert "assert count_vowels('AegisCode') == 4" in coder_ctx
    assert "<untrusted_test_code>" in coder_ctx


def test_coder_no_op_patch_detection_and_recovery(tmp_path: Path):
    """Verify that a patch producing no net change is detected and recovered with full-write."""
    wm = WorkspaceManager.create(base_dir=tmp_path)
    proj_dir = wm.get_project_path()

    orig_content = "def add(a, b):\n    return a + b\n"
    (proj_dir / "calc.py").write_text(orig_content, encoding="utf-8")
    init_repo(proj_dir)

    # Mock provider returning a no-op patch first, then a valid rewrite upon recovery
    mock_llm = MagicMock()
    # First response: identical to original
    mock_llm.generate_structured.side_effect = [
        CodeChange(
            file_path="calc.py",
            change_type="write",
            patch=orig_content,
            explanation="No change",
            root_cause="None",
            confidence=0.5,
        ),
        # Recovery response: actual fix
        CodeChange(
            file_path="calc.py",
            change_type="write",
            patch="def add(a, b):\n    return int(a) + int(b)\n",
            explanation="Cast to int",
            root_cause="Type mismatch",
            confidence=0.9,
        ),
    ]

    agent = CoderAgent(mock_llm)
    plan = ArchitecturePlan(
        summary="Fix add() to support string digits",
        relevant_files=["calc.py"],
        suspected_issues=["Types"],
        dependencies=[],
        test_strategy="Cast parameters",
    )

    change = agent.generate_and_apply_fix(workspace=wm, plan=plan)
    final = read_file(wm, "calc.py")

    assert final.content.strip() == "def add(a, b):\n    return int(a) + int(b)"
    assert change.patch.strip() == "def add(a, b):\n    return int(a) + int(b)"



def test_end_to_end_repair_workflow_with_reviewer_completion(tmp_path: Path):
    """
    Test full LangGraph repair workflow:
    Initial failure -> Architect -> Coder -> Test Validation -> Reviewer Audit Gate -> Passed.
    """
    wm = WorkspaceManager.create(base_dir=tmp_path)
    proj_dir = wm.get_project_path()

    (proj_dir / "string_utils.py").write_text(
        "def count_vowels(s: str) -> int:\n"
        "    return sum(1 for c in s if c in 'aeiouyAEIOUY')\n",
        encoding="utf-8",
    )
    (proj_dir / "test_string_utils.py").write_text(
        "from string_utils import count_vowels\n\n"
        "def test_count():\n"
        "    assert count_vowels('AegisCode') == 4\n",
        encoding="utf-8",
    )
    init_repo(proj_dir)

    mock_plan = ArchitecturePlan(
        summary="Change vowel set to 'aeiou' to count only lowercase vowels as expected by test",
        relevant_files=["string_utils.py"],
        suspected_issues=["Includes uppercase and y"],
        dependencies=[],
        test_strategy="Update count_vowels",
    )
    mock_change = CodeChange(
        file_path="string_utils.py",
        change_type="write",
        patch=(
            "def count_vowels(s: str) -> int:\n"
            "    return sum(1 for c in s if c in 'aeiou')\n"
        ),
        explanation="Count only lowercase vowels a, e, i, o, u",
        root_cause="Uppercase and y were counted",
        confidence=0.95,
    )
    mock_review = ReviewResult(
        approved=True,
        root_cause_fixed=True,
        regression_risk="low",
        reasoning="Fix correctly counts lowercase vowels satisfying test assertions",
        recommendation="Approve change and complete run",
    )

    mock_provider = MockLLMProvider(
        mock_plan=mock_plan,
        mock_change=mock_change,
        mock_review=mock_review,
    )


    db = SessionLocal()
    try:
        final_state = run_repair_workflow(
            run_id="test_run_e2e_vowel",
            workspace_id=wm.workspace_id,
            project_path=str(proj_dir),
            llm_provider=mock_provider,
            db=db,
            max_iterations=3,
        )
    finally:
        db.close()

    assert final_state["status"] == "passed"
    assert final_state["termination_reason"] == "all_tests_passed"
    assert final_state["review_result"]["approved"] is True
    assert final_state["final_failed_count"] == 0


def test_same_failure_no_effective_change_stalls(tmp_path: Path):
    """When a failure is repeated and the workspace was NOT changed, repair stalls immediately."""
    from backend.graph.nodes import test_node

    dummy_fail = TestResult(
        exit_code=1,
        passed=2,
        failed=1,
        success=False,
        stdout="FAILED test_calc.py::test_sub - AssertionError: assert -1 == 5\nE   AssertionError: assert -1 == 5",
    )
    fp = "abc123hash"

    state = {
        "run_id": "test_stall_no_change",
        "iteration": 1,
        "max_iterations": 5,
        "status": "running",
        "project_path": str(tmp_path),
        "previous_failures": [fp],
        "git_diff": {"has_changes": False, "changed_files": []},
    }

    with MagicMock() as mock_backend:
        mock_backend.run_pytest.return_value = dummy_fail
        from unittest.mock import patch
        with patch("backend.graph.nodes.get_execution_backend", return_value=mock_backend):
            with patch("backend.graph.nodes.compute_failure_fingerprint", return_value=fp):
                updates = test_node(state, db=None)

    assert updates["status"] == "stalled"
    assert updates["termination_reason"] == "no_effective_code_change"


def test_same_failure_with_code_changes_allows_retry(tmp_path: Path):
    """When a failure is repeated but the Coder actually modified files, retry is allowed."""
    from backend.graph.nodes import test_node

    dummy_fail = TestResult(
        exit_code=1,
        passed=2,
        failed=1,
        success=False,
        stdout="FAILED test_calc.py::test_sub - AssertionError: assert -1 == 5\nE   AssertionError: assert -1 == 5",
    )
    fp = "abc123hash"

    state = {
        "run_id": "test_allow_retry_with_change",
        "iteration": 1,
        "max_iterations": 5,
        "status": "running",
        "project_path": str(tmp_path),
        "previous_failures": [fp],
        "git_diff": {"has_changes": True, "changed_files": ["calc.py"]},
    }

    with MagicMock() as mock_backend:
        mock_backend.run_pytest.return_value = dummy_fail
        from unittest.mock import patch
        with patch("backend.graph.nodes.get_execution_backend", return_value=mock_backend):
            with patch("backend.graph.nodes.compute_failure_fingerprint", return_value=fp):
                updates = test_node(state, db=None)

    # Iteration should advance rather than stalling on iteration 1
    assert updates.get("status") is None or updates.get("status") == "running"
    assert updates["iteration"] == 2
    assert fp in updates["previous_failures"]

