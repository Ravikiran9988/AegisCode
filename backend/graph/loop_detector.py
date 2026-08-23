"""
Loop Detector & Failure Fingerprinting — Phase 4.

Computes a deterministic fingerprint of test failure outputs to identify
repeated identical failures across iterations and terminate stalled repair loops.
"""

from __future__ import annotations

import hashlib
import re

from backend.tools.pytest_runner import TestResult


def _normalize_diagnostic_text(text: str) -> str:
    """Normalize unstable runtime values like timestamps, durations, and machine-specific paths."""
    if not text:
        return ""

    # 1. Normalize path separators to forward slash
    s = text.replace("\\", "/")

    # 2. Normalize workspace paths (e.g. /app/workspaces/run_xxx/project/ or C:/Users/.../run_xxx/project/)
    s = re.sub(
        r"(?:[A-Za-z]:)?[^\s:\"']*[/\\]run_[0-9a-fA-F-]+[/\\](?:project[/\\])?",
        "project/",
        s,
    )
    s = re.sub(
        r"(?:[A-Za-z]:)?/(?:Users|home|app|tmp|var|private)/[^\s:\"']*[/\\]project[/\\]?",
        "project/",
        s,
    )
    s = re.sub(
        r"(?:[A-Za-z]:)?/(?:Users|home|app|tmp|var|private)/[^\s:\"']+",
        "<path>",
        s,
    )

    # 3. Normalize memory addresses (e.g. at 0x7f8b9c0d1e2f, 0x102938475)
    s = re.sub(r"\b0x[0-9a-fA-F]+\b", "<hex_addr>", s)

    # 4. Normalize timestamps (e.g. 2026-08-23 07:16:53, 2026-08-23T07:16:53.123456Z)
    s = re.sub(
        r"\b\d{4}-\d{2}-\d{2}[T\s]\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})?\b",
        "<timestamp>",
        s,
    )
    s = re.sub(r"\b\d{2}:\d{2}:\d{2}\b", "<time>", s)

    # 5. Normalize durations (e.g. 13.96s, in 0.12s, 120ms)
    s = re.sub(r"\b\d+\.\d+s\b", "<duration>", s)
    s = re.sub(r"\b\d+ms\b", "<duration>", s)
    s = re.sub(r"\bin \d+\.\d+s\b", "<duration>", s)

    # 6. Normalize whitespace
    s = re.sub(r"[ \t]+", " ", s).strip()

    return s


def compute_failure_fingerprint(test_result: TestResult | None) -> str:
    """
    Compute a deterministic SHA256 fingerprint for a test result.

    Extracts:
    1. Failed test identifiers (e.g., `FAILED test_calc.py::test_sub`)
    2. Assertion details, error messages, and exception types from both stdout and stderr
    3. Normalizes unstable values (timestamps, durations, machine paths)

    Guarantees:
    - Same test + same failure reason -> identical fingerprint
    - Same test + materially different assertion/error reason -> different fingerprint
    """
    if not test_result or test_result.success:
        return "PASS"

    stdout = test_result.stdout or ""
    stderr = test_result.stderr or ""
    combined = f"{stdout}\n{stderr}"

    if not combined.strip():
        return hashlib.sha256(f"FAILED_EXIT_{test_result.exit_code}".encode()).hexdigest()[:16]

    diagnostic_tokens: list[str] = []

    # Extract failure lines and error/assertion messages
    for line in combined.splitlines():
        line_clean = line.strip()
        if not line_clean:
            continue

        if line_clean.startswith("FAILED ") or line_clean.startswith("ERROR "):
            norm = _normalize_diagnostic_text(line_clean)
            if norm:
                diagnostic_tokens.append(norm)
        elif line_clean.startswith("E   ") or line_clean.startswith("E       "):
            norm = _normalize_diagnostic_text(line_clean)
            if norm:
                diagnostic_tokens.append(norm)
        elif re.match(r"^[a-zA-Z_]\w*(?:Error|Exception|Warning):\s*.+", line_clean):
            norm = _normalize_diagnostic_text(line_clean)
            if norm:
                diagnostic_tokens.append(norm)

    if diagnostic_tokens:
        unique_sorted = sorted(set(diagnostic_tokens))
        key = "::".join(unique_sorted)
    else:
        normalized_combined = _normalize_diagnostic_text(combined)
        key = normalized_combined[:2000]

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

    return (consecutive_count + 1) >= threshold
