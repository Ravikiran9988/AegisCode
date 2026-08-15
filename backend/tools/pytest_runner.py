"""
Pytest runner — Phase 2.

Executes pytest against an isolated project workspace using subprocess
and returns a fully structured TestResult.

IMPORTANT
---------
* The exit code returned by pytest is the authoritative pass/fail signal.
* LLM agents must NOT be asked to determine whether tests passed.
* stdout/stderr are captured and stored verbatim (truncated if huge).
"""

from __future__ import annotations

import re
import subprocess
import sys
import time
from pathlib import Path

from pydantic import BaseModel, Field

from backend.core.config import settings
from backend.core.logging import get_logger

logger = get_logger(__name__)

# Pytest exit codes (from pytest docs)
_EXIT_OK = 0            # All tests passed
_EXIT_TESTSFAILED = 1   # Some tests failed
_EXIT_INTERRUPTED = 2   # Execution interrupted
_EXIT_INTERNALERROR = 3 # Internal error
_EXIT_USAGEERROR = 4    # Command-line usage error
_EXIT_NOTESTSCOLLECTED = 5  # No tests were found


class TestResult(BaseModel):
    """Structured result from a pytest execution."""

    __test__ = False

    passed: int = Field(default=0, description="Number of tests that passed")
    failed: int = Field(default=0, description="Number of tests that failed")
    errors: int = Field(default=0, description="Number of collection / runtime errors")
    skipped: int = Field(default=0, description="Number of skipped tests")
    exit_code: int = Field(description="Raw pytest exit code (authoritative)")
    stdout: str = Field(default="", description="Full captured stdout")
    stderr: str = Field(default="", description="Full captured stderr")
    duration: float = Field(default=0.0, description="Wall-clock seconds")
    command: list[str] = Field(default_factory=list, description="Command that was run")
    success: bool = Field(description="True only when exit_code == 0")
    error_message: str | None = Field(
        default=None, description="High-level error if runner itself failed"
    )

    @property
    def total(self) -> int:
        return self.passed + self.failed + self.errors + self.skipped


def run_pytest(
    project_path: Path,
    timeout: int | None = None,
    extra_args: list[str] | None = None,
) -> TestResult:
    """
    Run pytest inside *project_path* and return a structured TestResult.

    Parameters
    ----------
    project_path:
        Directory to run pytest against. Must be an absolute path inside
        the active workspace.
    timeout:
        Maximum seconds before pytest is killed. Defaults to
        ``settings.pytest_timeout_seconds``.
    extra_args:
        Additional pytest CLI arguments (e.g. ``["-k", "test_add"]``).
        Arbitrary shell injection is NOT possible because we use a list,
        never a shell string.

    Security
    --------
    * Uses ``subprocess.run`` with a list — no shell=True.
    * Execution is bounded by a hard timeout.
    * Only pytest is invoked; no arbitrary shell commands are possible.
    """
    effective_timeout = timeout or settings.pytest_timeout_seconds
    max_output = settings.max_output_size_mb * 1024 * 1024

    if not project_path.exists() or not project_path.is_dir():
        logger.warning("run_pytest directory not found: %s", project_path)
        return TestResult(
            exit_code=_EXIT_INTERNALERROR,
            success=False,
            error_message=f"Directory does not exist or is not a directory: {project_path}",
            duration=0.0,
            command=[],
        )

    command = [
        sys.executable,   # same Python that runs the app
        "-m", "pytest",
        "--tb=short",
        "-v",
        "--no-header",
    ]
    if extra_args:
        command.extend(extra_args)

    logger.info("Running pytest in %s (timeout=%ds)", project_path, effective_timeout)
    logger.debug("Command: %s", " ".join(command))

    start = time.monotonic()
    timed_out = False

    try:
        proc = subprocess.run(
            command,
            cwd=str(project_path),
            capture_output=True,
            text=True,
            timeout=effective_timeout,
        )
        duration = time.monotonic() - start
        stdout = proc.stdout
        stderr = proc.stderr
        exit_code = proc.returncode

    except subprocess.TimeoutExpired as exc:
        duration = time.monotonic() - start
        timed_out = True
        out_raw = exc.stdout or b""
        err_raw = exc.stderr or b""
        if isinstance(out_raw, bytes):
            stdout = out_raw.decode("utf-8", errors="replace")
        else:
            stdout = str(out_raw)

        if isinstance(err_raw, bytes):
            stderr = err_raw.decode("utf-8", errors="replace")
        else:
            stderr = str(err_raw)
        exit_code = _EXIT_INTERRUPTED
        logger.warning("pytest timed out after %ds", effective_timeout)

    except FileNotFoundError as exc:
        duration = time.monotonic() - start
        return TestResult(
            exit_code=_EXIT_INTERNALERROR,
            success=False,
            error_message=f"Python/pytest not found: {exc}",
            duration=duration,
            command=command,
        )

    # Truncate very large output to avoid memory issues
    if len(stdout) > max_output:
        stdout = stdout[:max_output] + "\n... [OUTPUT TRUNCATED] ..."
    if len(stderr) > max_output:
        stderr = stderr[:max_output] + "\n... [OUTPUT TRUNCATED] ..."

    passed, failed, errors, skipped = _parse_counts(stdout)

    result = TestResult(
        passed=passed,
        failed=failed,
        errors=errors,
        skipped=skipped,
        exit_code=exit_code,
        stdout=stdout,
        stderr=stderr,
        duration=round(duration, 3),
        command=command,
        success=(exit_code == _EXIT_OK),
        error_message="Execution timed out" if timed_out else None,
    )

    logger.info(
        "pytest finished: exit=%d passed=%d failed=%d errors=%d skipped=%d (%.2fs)",
        exit_code, passed, failed, errors, skipped, duration,
    )
    return result


# ── Output parser ─────────────────────────────────────────────────────────────

def _parse_counts(stdout: str) -> tuple[int, int, int, int]:
    """
    Parse pytest summary line for test counts.

    Handles forms like:
        "3 passed"
        "2 failed, 1 passed"
        "1 error"
        "1 passed, 2 warnings"
        "no tests ran"
    """
    # Match the final summary line: == N passed, M failed ... ==
    summary_pattern = re.compile(
        r"=+\s*(.*?)\s*=+\s*$", re.MULTILINE
    )
    matches = summary_pattern.findall(stdout)
    summary = matches[-1] if matches else stdout

    def _extract(label: str) -> int:
        m = re.search(rf"(\d+)\s+{label}", summary)
        return int(m.group(1)) if m else 0

    return (
        _extract("passed"),
        _extract("failed"),
        _extract("error(?:s)?"),
        _extract("skipped"),
    )
