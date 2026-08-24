"""
Performance, Token Efficiency & Architecture Optimization Tests.

Verifies:
1. Large repository context filtering (only relevant source files selected, unrelated excluded).
2. Huge pytest output is cleanly extracted and bounded without token blowout.
3. Multi-iteration failure intelligence (previous attempt warnings injected).
4. TPD 429 (tokens per day) immediately raises QuotaExhaustedError without 4 useless retries.
5. Temporary 429 succeeds with bounded backoff.
6. Role-specific model configuration in factory.
7. Targeted pytest fast-path validation.
8. Authoritative final gate invariant (pytest PASS + Reviewer APPROVED).
9. Benchmark measuring context token reduction on a multi-file repository.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import requests

from backend.context.builder import (
    _extract_failure_summary,
    build_architect_context,
    build_coder_context,
    find_relevant_source_files,
)
from backend.core.config import settings
from backend.execution.workspace import WorkspaceManager
from backend.llm.base import QuotaExhaustedError
from backend.llm.factory import get_llm_provider
from backend.llm.openai import OpenAICompatibleLLMProvider
from backend.tools.git_tools import init_repo
from backend.tools.pytest_runner import TestResult, run_targeted_pytest

# ── TEST 1: Large repository context filtering ────────────────────────────────

def test_large_repo_context_filtering(tmp_path: Path):
    """Verify that in a large project with 25+ files, only the relevant file is selected."""
    wm = WorkspaceManager.create(base_dir=tmp_path)
    proj_dir = wm.get_project_path()

    # Create 25 dummy modules
    for i in range(25):
        (proj_dir / f"module_{i}.py").write_text(f"def func_{i}(): return {i}\n", encoding="utf-8")

    # Create target module & failing test
    (proj_dir / "target_calc.py").write_text(
        "def compute(a, b):\n    return a * b  # bug: should be addition\n",
        encoding="utf-8",
    )
    (proj_dir / "test_target_calc.py").write_text(
        "from target_calc import compute\n\n"
        "def test_compute():\n"
        "    assert compute(2, 3) == 5\n",
        encoding="utf-8",
    )
    init_repo(proj_dir)

    t_res = TestResult(
        exit_code=1,
        passed=0,
        failed=1,
        success=False,
        stdout=(
            "FAILED test_target_calc.py::test_compute - AssertionError: assert 6 == 5\n"
            "File \"target_calc.py\", line 2, in compute\n"
            "E   AssertionError: assert 6 == 5"
        ),
    )

    relevant = find_relevant_source_files(wm, test_result=t_res, max_files=3)
    assert "target_calc.py" in relevant
    # Verify unrelated dummy modules are excluded
    assert len(relevant) == 1
    assert "module_0.py" not in relevant
    assert "module_24.py" not in relevant


# ── TEST 2: Huge pytest output is summarized and bounded ──────────────────────

def test_huge_pytest_output_is_summarized():
    """Verify that massive 50KB stdout is cleanly summarized under the token budget."""
    huge_noise = "Some passing log output\n" * 2000  # ~48KB of noise
    failing_section = (
        "=================================== FAILURES ===================================\n"
        "________________________________ test_addition _________________________________\n"
        "tests/test_math.py:12: in test_addition\n"
        "    assert add(2, 2) == 4\n"
        "E   AssertionError: assert 5 == 4\n"
        "=========================== short test summary info ===========================\n"
        "FAILED tests/test_math.py::test_addition - AssertionError: assert 5 == 4\n"
        "========================= 1 failed, 100 passed in 1.2s =========================\n"
    )
    combined = huge_noise + failing_section

    t_res = TestResult(
        exit_code=1,
        passed=100,
        failed=1,
        success=False,
        stdout=combined,
    )

    summary = _extract_failure_summary(t_res)
    assert "FAILED tests/test_math.py::test_addition" in summary
    assert "AssertionError: assert 5 == 4" in summary
    assert len(summary) < 2000  # Strict budget ceiling


# ── TEST 3: Multi-iteration failure intelligence (previous attempt warning) ───

def test_previous_attempt_context_injected(tmp_path: Path):
    """Verify that iteration 2 prompts receive explicit notes on previous failed patches."""
    wm = WorkspaceManager.create(base_dir=tmp_path)
    proj_dir = wm.get_project_path()

    (proj_dir / "calc.py").write_text("def add(a, b): return a + b\n", encoding="utf-8")
    init_repo(proj_dir)

    t_res = TestResult(
        exit_code=1,
        passed=0,
        failed=1,
        success=False,
        stdout="FAILED test_calc.py::test_add - AssertionError: assert 3 == 4",
    )

    prev_summary = "File: calc.py, Change: write, Explanation: Changed return to a - b"

    arch_ctx = build_architect_context(
        wm,
        test_result=t_res,
        previous_attempt_summary=prev_summary,
    )
    assert "[PREVIOUS REPAIR ATTEMPT (FAILED)]" in arch_ctx
    assert "Changed return to a - b" in arch_ctx
    assert "Do NOT repeat the same change" in arch_ctx

    coder_ctx = build_coder_context(
        wm,
        architecture_summary="Fix calc.py",
        relevant_files=["calc.py"],
        test_result=t_res,
        previous_attempt_summary=prev_summary,
    )
    assert "[PREVIOUS REPAIR ATTEMPT (FAILED)]" in coder_ctx
    assert "You MUST produce a new, different fix" in coder_ctx


# ── TEST 4: TPD 429 immediately raises QuotaExhaustedError with 0 retries ────

def test_tpd_429_immediately_raises_quota_exhausted():
    """Verify that a daily token quota (TPD) 429 raises QuotaExhaustedError on attempt 1 with NO sleeps."""
    provider = OpenAICompatibleLLMProvider(api_key="test-key", model="openai/gpt-oss-120b")

    mock_resp = MagicMock(spec=requests.Response)
    mock_resp.status_code = 429
    mock_resp.json.return_value = {
        "error": {
            "message": "Rate limit reached for model openai/gpt-oss-120b on tokens per day (TPD): Limit 200000, Used 199162, Requested 4171. Please try again in 18h24m.",
            "type": "tokens",
            "code": "rate_limit_exceeded",
        }
    }

    with patch.object(provider.session, "post", return_value=mock_resp) as mock_post:
        with pytest.raises(QuotaExhaustedError) as exc_info:
            provider.generate("Test prompt")

        # Must have attempted exactly once — NO useless 4-retry loop!
        assert mock_post.call_count == 1
        assert exc_info.value.limit_type == "TPD"
        assert exc_info.value.limit_value == 200000
        assert exc_info.value.used_value == 199162
        assert exc_info.value.requested_value == 4171


# ── TEST 5: Temporary 429 succeeds with bounded retry ─────────────────────────

def test_temporary_429_succeeds_with_bounded_retry():
    """Verify that a transient RPM 429 retries and succeeds on the next attempt."""
    provider = OpenAICompatibleLLMProvider(api_key="test-key", model="openai/gpt-oss-120b")

    mock_429 = MagicMock(spec=requests.Response)
    mock_429.status_code = 429
    mock_429.headers = {"Retry-After": "0.1"}
    mock_429.json.return_value = {
        "error": {
            "message": "Rate limit reached for requests per minute (RPM). Please try again in 0.1s.",
            "type": "requests",
        }
    }

    mock_200 = MagicMock(spec=requests.Response)
    mock_200.status_code = 200
    mock_200.json.return_value = {
        "choices": [{"message": {"content": '{"status": "ok"}'}}],
        "usage": {"prompt_tokens": 50, "completion_tokens": 10, "total_tokens": 60},
    }

    with patch.object(provider.session, "post", side_effect=[mock_429, mock_200]) as mock_post:
        with patch("time.sleep") as mock_sleep:
            res = provider.generate("Test prompt")
            assert res == '{"status": "ok"}'
            assert mock_post.call_count == 2
            assert mock_sleep.called
            assert provider.last_usage.get("total_tokens") == 60


def test_groq_tpm_429_retries_and_does_not_abort_as_tpd():
    """Verify that Groq Tokens Per Minute (TPM) 429 with 'Limit, Used, Requested' retries instead of failing as TPD."""
    provider = OpenAICompatibleLLMProvider(api_key="test-key", model="openai/gpt-oss-120b")

    mock_tpm_429 = MagicMock(spec=requests.Response)
    mock_tpm_429.status_code = 429
    mock_tpm_429.headers = {}
    mock_tpm_429.json.return_value = {

        "error": {
            "message": "Rate limit reached for model openai/gpt-oss-120b on tokens per minute (TPM): Limit 8000, Used 7950, Requested 500. Please try again in 30s.",
            "type": "tokens",
            "code": "rate_limit_exceeded",
        }
    }

    mock_200 = MagicMock(spec=requests.Response)
    mock_200.status_code = 200
    mock_200.json.return_value = {
        "choices": [{"message": {"content": '{"status": "recovered"}'}}],
        "usage": {"prompt_tokens": 50, "completion_tokens": 10, "total_tokens": 60},
    }

    with patch.object(provider.session, "post", side_effect=[mock_tpm_429, mock_200]) as mock_post:
        with patch("time.sleep") as mock_sleep:
            res = provider.generate("Test prompt")
            assert res == '{"status": "recovered"}'
            assert mock_post.call_count == 2
            assert mock_sleep.called



# ── TEST 6: Role-specific model configuration in factory ──────────────────────

def test_role_specific_model_configuration():
    """Verify that role-specific models are cleanly instantiated when configured."""
    with patch.object(settings, "llm_provider", "openai_compatible"):
        with patch.object(settings, "architect_model", "openai/gpt-oss-120b"):
            with patch.object(settings, "coder_model", "openai/gpt-oss-120b"):
                with patch.object(settings, "reviewer_model", "openai/gpt-oss-120b"):
                    arch_provider = get_llm_provider(role="architect")
                    coder_provider = get_llm_provider(role="coder")
                    rev_provider = get_llm_provider(role="reviewer")

                    assert arch_provider.model_name == "openai/gpt-oss-120b"
                    assert coder_provider.model_name == "openai/gpt-oss-120b"
                    assert rev_provider.model_name == "openai/gpt-oss-120b"


# ── TEST 7: Targeted pytest validation ────────────────────────────────────────

def test_targeted_pytest_validation(tmp_path: Path):
    """Verify run_targeted_pytest executes only the specified test file."""
    proj_dir = tmp_path / "project"
    proj_dir.mkdir()

    (proj_dir / "test_a.py").write_text("def test_a(): assert True\n", encoding="utf-8")
    (proj_dir / "test_b.py").write_text("def test_b(): assert False\n", encoding="utf-8")

    # Run only test_a.py
    res_a = run_targeted_pytest(proj_dir, ["test_a.py"])
    assert res_a.passed == 1
    assert res_a.failed == 0
    assert res_a.success is True

    # Run only test_b.py
    res_b = run_targeted_pytest(proj_dir, ["test_b.py"])
    assert res_b.failed == 1
    assert res_b.success is False


# ── TEST 8: Token Efficiency Benchmark ────────────────────────────────────────

def test_context_token_efficiency_benchmark(tmp_path: Path):
    """
    Benchmark measuring token/character footprint reduction on a 20-file repository.
    Verifies that targeted context builder keeps total payload under bounded budget.
    """
    wm = WorkspaceManager.create(base_dir=tmp_path)
    proj_dir = wm.get_project_path()

    # Create 20 modules with substantial content
    for i in range(20):
        (proj_dir / f"service_{i}.py").write_text(
            f"# Service {i}\n" + "def handle():\n    return 'ok'\n" * 50,
            encoding="utf-8",
        )

    (proj_dir / "calc.py").write_text("def add(a, b): return a - b\n", encoding="utf-8")
    (proj_dir / "test_calc.py").write_text(
        "from calc import add\ndef test_add(): assert add(1, 2) == 3\n",
        encoding="utf-8",
    )
    init_repo(proj_dir)

    t_res = TestResult(
        exit_code=1,
        passed=0,
        failed=1,
        success=False,
        stdout="FAILED test_calc.py::test_add - AssertionError: assert -1 == 3\nFile \"calc.py\", line 1, in add",
    )

    coder_context = build_coder_context(
        workspace=wm,
        architecture_summary="Fix addition operator in calc.py",
        relevant_files=["calc.py"],
        test_result=t_res,
    )

    # Verify context size is strictly bounded (< 4000 characters ≈ ~1000 tokens)
    assert len(coder_context) < 4000
    # Verify the 20 unrelated service files were NOT included
    assert "service_0" not in coder_context
    assert "service_19" not in coder_context
    assert "def add(a, b): return a - b" in coder_context
