"""
Loop Detector & Failure Fingerprinting — Phase 4.

Computes a deterministic fingerprint of test failure outputs to identify
repeated identical failures across iterations and terminate stalled repair loops.
"""

from __future__ import annotations

import hashlib
import re

from backend.tools.pytest_runner import TestResult


def compute_failure_fingerprint(test_result: TestResult | None) -> str:
    """
    Compute a deterministic SHA256 fingerprint for a test result.

    Extracts test failure lines (e.g., `FAILED test_calculator.py::test_subtract`)
    and error messages to produce a stable hash invariant to timestamps or durations.
    """
    if not test_result or test_result.success:
        return "PASS"

    stdout = test_result.stdout or ""
    stderr = test_result.stderr or ""
    combined = f"{stdout}\n{stderr}"

    # Extract lines matching failed tests (e.g. FAILED test_foo.py::test_bar)
    failed_lines = re.findall(r"FAILED\s+([^\s]+)", combined)
    error_lines = re.findall(r"ERROR\s+([^\s]+)", combined)

    if failed_lines or error_lines:
        key = "::".join(sorted(set(failed_lines + error_lines)))
    else:
        # Fallback: clean out timestamps/durations and hash raw output
        cleaned = re.sub(r"\d+\.\d+s", "", combined)
        cleaned = re.sub(r"\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2}", "", cleaned)
        key = cleaned.strip()[:2000]

    return hashlib.sha256(key.encode("utf-8")).hexdigest()[:16]


def is_repeated_failure(
    current_fingerprint: str,
    previous_fingerprints: list[str],
    threshold: int = 2,
) -> bool:
    """
    Return True if `current_fingerprint` has appeared consecutively `threshold` times.
    """
    if not previous_fingerprints or current_fingerprint == "PASS":
        return False

    consecutive_count = 0
    for fp in reversed(previous_fingerprints):
        if fp == current_fingerprint:
            consecutive_count += 1
        else:
            break

    return consecutive_count >= (threshold - 1)
