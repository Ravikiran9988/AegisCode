"""
Execution backend factory.

Determines and returns the authoritative ExecutionBackend implementation based on configuration.
"""

from __future__ import annotations

from backend.core.config import settings
from backend.core.logging import get_logger
from backend.execution.base import ExecutionBackend
from backend.execution.local import LocalExecutionBackend

logger = get_logger(__name__)


class UnsafeLocalExecutionError(RuntimeError):
    """Raised when untrusted uploaded code would run without an isolation boundary."""


def get_execution_backend() -> ExecutionBackend:
    """
    Return the configured execution backend.

    Reads ``settings.execution_backend`` or ``settings.use_docker_sandbox``:
      * ``"docker"`` or ``use_docker_sandbox=True`` -> DockerExecutionBackend
      * ``"local"`` -> LocalExecutionBackend

    Security Enforcement
    --------------------
    If Docker sandbox execution is configured but the Docker CLI or daemon
    is unavailable, this function raises ``DockerNotAvailable``.
    It does NOT silently fall back to local host execution in production.
    """
    use_docker = (
        settings.execution_backend == "docker"
        or settings.use_docker_sandbox
    )

    if use_docker:
        from backend.execution.docker import DockerExecutionBackend
        logger.info(
            "Configured for Docker execution backend (image=%s)", settings.docker_image
        )
        return DockerExecutionBackend()
    else:
        if settings.is_production:
            raise UnsafeLocalExecutionError(
                "Repair execution is disabled: production is configured with the "
                "local runner, which executes uploaded Python code inside the API "
                "service. Configure a separately isolated Docker or remote sandbox "
                "worker before enabling public project repairs."
            )
        logger.info("Configured for Local execution backend (development/test only)")
        return LocalExecutionBackend()
