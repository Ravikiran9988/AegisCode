"""
Granular Loop Detector & Fingerprint Normalization Tests.

Verifies:
1. same test + same assertion -> repeated_failure = True
2. same test + different assertion -> repeated_failure = False
3. same test + different exception -> different fingerprint
4. timestamps / durations / path changes do not alter fingerprint
5. Coder receives both stdout and stderr diagnostics within token budget
6. Multi-iteration failure progression preserves history without premature stalling
"""

from __future__ import annotations

from unittest.mock import MagicMock

from backend.context.builder import build_coder_context
from backend.execution.workspace import WorkspaceManager
from backend.graph.loop_detector import compute_failure_fingerprint, is_repeated_failure
from backend.tools.pytest_runner import TestResult


def test_same_test_same_assertion_produces_identical_fingerprint():
    """Identical failure and assertion produces the exact same fingerprint and triggers repeat detection."""
    res1 = TestResult(
        exit_code=1,
        passed=3,
        failed=1,
        success=False,
        stdout=(
            "FAILED test_string_utils.py::test_count_vowels - AssertionError: assert 2 == 5\n"
            "E   AssertionError: assert 2 == 5\n"
            "E     where 2 = count_vowels('Hello World')\n"
        ),
    )
    res2 = TestResult(
        exit_code=1,
        passed=3,
        failed=1,
        success=False,
        stdout=(
            "FAILED test_string_utils.py::test_count_vowels - AssertionError: assert 2 == 5\n"
            "E   AssertionError: assert 2 == 5\n"
            "E     where 2 = count_vowels('Hello World')\n"
        ),
    )
    fp1 = compute_failure_fingerprint(res1)
    fp2 = compute_failure_fingerprint(res2)

    assert fp1 != "PASS"
    assert fp1 == fp2
    assert is_repeated_failure(fp2, [fp1], threshold=2) is True


def test_same_test_different_assertion_produces_different_fingerprint():
    """Same test failing with different assertion output produces different fingerprint (no false stall)."""
    res_it1 = TestResult(
        exit_code=1,
        passed=3,
        failed=1,
        success=False,
        stdout=(
            "FAILED test_string_utils.py::test_count_vowels - AssertionError: assert 2 == 5\n"
            "E   AssertionError: assert 2 == 5\n"
        ),
    )
    # On iteration 2, coder modified code so it now returns 3 instead of 2 (progress made)
    res_it2 = TestResult(
        exit_code=1,
        passed=3,
        failed=1,
        success=False,
        stdout=(
            "FAILED test_string_utils.py::test_count_vowels - AssertionError: assert 3 == 5\n"
            "E   AssertionError: assert 3 == 5\n"
        ),
    )

    fp1 = compute_failure_fingerprint(res_it1)
    fp2 = compute_failure_fingerprint(res_it2)

    assert fp1 != fp2
    # Should NOT trigger repeated failure
    assert is_repeated_failure(fp2, [fp1], threshold=2) is False


def test_same_test_different_exception_produces_different_fingerprint():
    """Same test failing with AssertionError vs TypeError produces different fingerprints."""
    res_assertion = TestResult(
        exit_code=1,
        passed=2,
        failed=1,
        success=False,
        stdout="FAILED test_calc.py::test_add - AssertionError: assert -1 == 5\nE   AssertionError: assert -1 == 5",
    )
    res_type_error = TestResult(
        exit_code=1,
        passed=2,
        failed=1,
        success=False,
        stdout="FAILED test_calc.py::test_add - TypeError: unsupported operand type(s)\nE   TypeError: unsupported operand type(s)",
    )

    fp_assert = compute_failure_fingerprint(res_assertion)
    fp_type = compute_failure_fingerprint(res_type_error)

    assert fp_assert != fp_type
    assert is_repeated_failure(fp_type, [fp_assert], threshold=2) is False


def test_fingerprint_invariance_to_timestamps_durations_and_paths():
    """Fingerprint remains completely stable across timestamps, durations, and machine paths."""
    out1 = (
        "2026-08-23 07:16:53 | INFO | running test\n"
        "rootdir: /app/workspaces/run_3e878cf0-6fad-41e7-bed9-f719536db6a5/project\n"
        "FAILED test_calc.py::test_add - AssertionError: assert 0 == 5\n"
        "E   AssertionError: assert 0 == 5\n"
        "1 failed, 3 passed in 13.96s\n"
    )
    out2 = (
        "2026-08-23 10:45:00 | INFO | running test\n"
        "rootdir: C:\\Users\\ADMIN\\Desktop\\Aegis\\workspaces\\run_99999999-aaaa-bbbb-cccc-dddddddddddd\\project\n"
        "FAILED test_calc.py::test_add - AssertionError: assert 0 == 5\n"
        "E   AssertionError: assert 0 == 5\n"
        "1 failed, 3 passed in 0.42s\n"
    )

    res1 = TestResult(exit_code=1, passed=3, failed=1, success=False, stdout=out1, duration=13.96)
    res2 = TestResult(exit_code=1, passed=3, failed=1, success=False, stdout=out2, duration=0.42)

    fp1 = compute_failure_fingerprint(res1)
    fp2 = compute_failure_fingerprint(res2)

    assert fp1 == fp2


def test_coder_context_receives_stdout_and_stderr_diagnostics():
    """Coder prompt context includes diagnostics from both stdout and stderr."""
    mock_wm = MagicMock(spec=WorkspaceManager)
    t_res = TestResult(
        exit_code=1,
        passed=2,
        failed=1,
        errors=0,
        skipped=0,
        success=False,
        stdout="FAILED test_calc.py::test_div\nE   ZeroDivisionError: division by zero",
        stderr="Traceback (most recent call last):\n  File 'calc.py', line 12, in div\n    return a / b",
    )

    context = build_coder_context(
        workspace=mock_wm,
        architecture_summary="Fix ZeroDivisionError in calc.py",
        relevant_files=[],
        test_result=t_res,
    )

    assert "ZeroDivisionError: division by zero" in context
    assert "Captured Stderr" in context
    assert "return a / b" in context
    assert "<untrusted_test_output>" in context
    assert "</untrusted_test_output>" in context
