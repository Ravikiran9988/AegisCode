"""
LocalExecutionBackend — Phase 2.

Runs pytest directly in the host Python environment using subprocess.

SECURITY WARNING
----------------
This backend executes the uploaded project's test suite in the same
OS process-group as the AegisCode server.  It should only be used:

  * During local development on trusted code.
  * For the AegisCode benchmark suite (known projects).
  * When USE_DOCKER_SANDBOX=false is explicitly set.

For public-facing deployments, use DockerExecutionBackend instead.

Mitigations applied even in local mode
---------------------------------------
* Hard timeout — pytest is killed if it exceeds the limit.
* Only pytest is invoked via an argument list (no shell=True).
* Working directory is the isolated project path, not the repo root.
* stdout/stderr are bounded.
"""

from __future__ import annotations

from pathlib import Path

from backend.core.config import settings
from backend.core.logging import get_logger
from backend.execution.base import ExecutionBackend
from backend.tools.pytest_runner import TestResult, run_pytest

logger = get_logger(__name__)


class LocalExecutionBackend(ExecutionBackend):
    """Execute pytest in a subprocess on the local host."""

    @property
    def name(self) -> str:
        return "local"

    def run_pytest(
        self,
        project_path: Path,
        timeout: int | None = None,
    ) -> TestResult:
        logger.info("[LocalBackend] Running pytest at %s", project_path)
        return run_pytest(
            project_path=project_path,
            timeout=timeout or settings.pytest_timeout_seconds,
        )
