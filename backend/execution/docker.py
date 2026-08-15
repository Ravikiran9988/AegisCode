"""
DockerExecutionBackend — Phase 2.

Runs pytest inside an ephemeral Docker container, providing strong
isolation from the host system.

Requirements
------------
* Docker must be installed and the Docker daemon must be running.
* The ``docker`` CLI must be on PATH.
* The current user must have permission to run Docker commands
  (typically membership of the ``docker`` group on Linux).

Security properties
-------------------
* Network disabled (``--network none``).
* Read-only root filesystem with only the project mount writable.
* Non-root user inside the container (``--user nobody``).
* CPU and memory limits enforced.
* Hard time limit via ``--stop-timeout``.
* Container is removed after execution (``--rm``).
* Only the isolated project directory is mounted.
* Only pytest is executed — no shell or arbitrary command access.

Limitations
-----------
* Docker must be available; the backend raises ``DockerNotAvailable``
  if the daemon cannot be reached.
* On Windows, ``--user nobody`` may not apply depending on the Docker
  backend (WSL2 / Hyper-V). The ``--network none`` and ``--memory`` flags
  still apply.
* The Docker image must have Python and pytest installed.
"""

from __future__ import annotations

import subprocess
import time
import uuid
from pathlib import Path

from backend.core.config import settings
from backend.core.logging import get_logger
from backend.execution.base import ExecutionBackend
from backend.tools.pytest_runner import (
    _EXIT_INTERNALERROR,
    _EXIT_INTERRUPTED,
    TestResult,
    _parse_counts,
)

logger = get_logger(__name__)


class DockerNotAvailable(Exception):
    """Raised when Docker cannot be reached."""


class DockerExecutionBackend(ExecutionBackend):
    """
    Execute pytest inside an ephemeral Docker container.

    Parameters
    ----------
    image:
        Docker image to use (must have Python + pytest).
    memory_limit:
        Container memory limit (Docker format, e.g. ``"256m"``).
    cpu_quota:
        CPU quota in microseconds per 100ms period (e.g. ``50000`` = 50 % of one core).
    """

    def __init__(
        self,
        image: str | None = None,
        memory_limit: str = "256m",
        cpu_quota: int = 50000,
    ) -> None:
        self._image = image or settings.docker_image
        self._memory_limit = memory_limit
        self._cpu_quota = cpu_quota
        self._check_docker()

    @property
    def name(self) -> str:
        return "docker"

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    def _check_docker(self) -> None:
        """Verify Docker is reachable; raise DockerNotAvailable if not."""
        try:
            result = subprocess.run(
                ["docker", "info"],
                capture_output=True,
                timeout=10,
            )
            if result.returncode != 0:
                raise DockerNotAvailable(
                    "docker info returned non-zero exit code. "
                    "Is the Docker daemon running?"
                )
        except FileNotFoundError as exc:
            raise DockerNotAvailable(
                "'docker' CLI not found on PATH. "
                "Install Docker Desktop or Docker Engine."
            ) from exc
        except subprocess.TimeoutExpired as exc:
            raise DockerNotAvailable(
                "docker info timed out — daemon may be unresponsive."
            ) from exc

    # ── Execution ─────────────────────────────────────────────────────────────

    def run_pytest(
        self,
        project_path: Path,
        timeout: int | None = None,
    ) -> TestResult:
        effective_timeout = timeout or settings.pytest_timeout_seconds
        container_name = f"aegiscode-{uuid.uuid4().hex[:12]}"

        command = [
            "docker", "run",
            "--rm",
            "--name", container_name,
            "--network", "none",                      # no internet access
            "--memory", self._memory_limit,            # memory cap
            "--memory-swap", self._memory_limit,       # disable swap
            "--cpu-quota", str(self._cpu_quota),       # CPU cap
            "--read-only",                             # immutable root FS
            "--tmpfs", "/tmp:size=64m",                # writable tmp
            "--user", "nobody",                        # non-root
            "--volume", f"{project_path.resolve()}:/project:ro",  # read-only mount
            "--workdir", "/project",
            "--stop-timeout", str(effective_timeout),
            self._image,
            "python", "-m", "pytest",
            "--tb=short", "-v", "--no-header",
        ]

        logger.info(
            "[DockerBackend] Running pytest in container %s (image=%s, timeout=%ds)",
            container_name, self._image, effective_timeout,
        )

        start = time.monotonic()
        timed_out = False

        try:
            proc = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=effective_timeout + 15,  # grace period for Docker overhead
            )
            duration = time.monotonic() - start
            stdout = proc.stdout
            stderr = proc.stderr
            exit_code = proc.returncode

        except subprocess.TimeoutExpired:
            duration = time.monotonic() - start
            timed_out = True
            stdout = ""
            stderr = "Container execution timed out"
            exit_code = _EXIT_INTERRUPTED
            # Best-effort container cleanup
            subprocess.run(
                ["docker", "stop", container_name],
                capture_output=True, timeout=10,
            )
            logger.warning("[DockerBackend] Container timed out: %s", container_name)

        except FileNotFoundError as exc:
            return TestResult(
                exit_code=_EXIT_INTERNALERROR,
                success=False,
                error_message=f"Docker not found: {exc}",
                duration=time.monotonic() - start,
                command=command,
            )

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
            success=(exit_code == 0),
            error_message="Execution timed out" if timed_out else None,
        )

        logger.info(
            "[DockerBackend] Result: exit=%d passed=%d failed=%d (%.2fs)",
            exit_code, passed, failed, duration,
        )
        return result


# ── Factory helper ────────────────────────────────────────────────────────────

def get_execution_backend() -> ExecutionBackend:  # type: ignore[name-defined]
    """
    Return the configured execution backend.

    Reads ``settings.execution_backend``:
      * ``"local"``  → LocalExecutionBackend
      * ``"docker"`` → DockerExecutionBackend (raises if Docker unavailable)
    """
    from backend.execution.local import LocalExecutionBackend

    backend = settings.execution_backend
    if backend == "docker":
        logger.info("Using Docker execution backend (image=%s)", settings.docker_image)
        return DockerExecutionBackend()
    else:
        logger.info("Using local execution backend")
        return LocalExecutionBackend()
