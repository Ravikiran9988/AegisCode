"""
Security Policy Engine — Phase 3.

Enforces tool permissions and file protection rules for AegisCode agents.

Policy Rules
------------
1. Coder cannot modify test files (tests/*, test_*.py, *_test.py, conftest.py).
2. Coder cannot modify system/security files (.git/*, .env*, Dockerfile*, etc.).
3. Path traversal attempts are blocked at policy evaluation time.
"""

from __future__ import annotations

import re

# ── Protected patterns ────────────────────────────────────────────────────────

_TEST_FILE_PATTERNS = (
    re.compile(r"^tests/"),
    re.compile(r"^test_.*\.py$"),
    re.compile(r".*/test_.*\.py$"),
    re.compile(r"^.*_test\.py$"),
    re.compile(r".*/.*_test\.py$"),
    re.compile(r".*conftest\.py$"),
)

_PROTECTED_SYSTEM_PATTERNS = (
    re.compile(r"^\.git/"),
    re.compile(r"^\.env.*"),
    re.compile(r".*/\.env.*"),
    re.compile(r".*credentials.*"),
    re.compile(r".*secrets.*"),
    re.compile(r"^Dockerfile.*"),
    re.compile(r"^docker-compose.*"),
)


class PolicyViolationError(Exception):
    """Raised when an agent attempts a forbidden operation."""


def check_file_modification_policy(
    relative_path: str,
    allow_test_modification: bool = False,
) -> None:
    """
    Verify whether modifying `relative_path` is permitted under AegisCode security policy.

    Raises PolicyViolationError if forbidden.
    """
    clean_path = relative_path.lstrip("/\\").replace("\\", "/")

    # Path traversal check
    parts = clean_path.split("/")
    if ".." in parts or clean_path.startswith("/"):
        raise PolicyViolationError(
            f"SECURITY POLICY VIOLATION: Path traversal in target path: {relative_path!r}"
        )

    # Protected system files
    for pat in _PROTECTED_SYSTEM_PATTERNS:
        if pat.search(clean_path):
            raise PolicyViolationError(
                f"SECURITY POLICY VIOLATION: Protected file {relative_path!r} modification "
                "is forbidden."
            )

    # Test file protection (unless explicitly overridden for benchmark harness)
    if not allow_test_modification:
        for pat in _TEST_FILE_PATTERNS:
            if pat.search(clean_path):
                raise PolicyViolationError(
                    f"SECURITY POLICY VIOLATION: Cannot modify test file {relative_path!r}. "
                    "Tests represent the contract and cannot be altered to bypass failures."
                )
