"""
backend.execution package.

Provides execution backend abstractions and isolated sandbox implementations.
"""

from backend.execution.base import ExecutionBackend
from backend.execution.docker import DockerExecutionBackend, DockerNotAvailable
from backend.execution.factory import get_execution_backend
from backend.execution.local import LocalExecutionBackend

__all__ = [
    "ExecutionBackend",
    "LocalExecutionBackend",
    "DockerExecutionBackend",
    "DockerNotAvailable",
    "get_execution_backend",
]
