"""
ExecutionBackend — abstract base class.

All concrete backends (local subprocess, Docker container) implement
this interface so the rest of the system is backend-agnostic.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path

from backend.tools.pytest_runner import TestResult


class ExecutionBackend(ABC):
    """Abstract execution backend."""

    @abstractmethod
    def run_pytest(
        self,
        project_path: Path,
        timeout: int | None = None,
    ) -> TestResult:
        """
        Execute pytest against *project_path* and return structured results.

        Parameters
        ----------
        project_path:
            Absolute path to the project directory (inside the workspace).
        timeout:
            Maximum seconds to allow pytest to run. Backend must enforce
            this limit. ``None`` falls back to the backend's default.

        Returns
        -------
        TestResult
            Structured result with exit code, counts, stdout, stderr, etc.
            The exit code is authoritative — do NOT ask an LLM to interpret it.
        """
        ...

    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable backend identifier."""
        ...
