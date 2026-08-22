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
        logger.info("Configured for Local execution backend")
        return LocalExecutionBackend()
