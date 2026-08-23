"""
Context Builder — Phase 3 / Phase 6 (Token Budget Hardening).

Assembles bounded project context (file tree, file snippets, pytest failure output,
git diffs) into clean prompts.

Security & Safety
-----------------
All project source code, test stdout, file names, and diffs are wrapped in
explicit `<untrusted_data>` blocks and tagged so the LLM treats them strictly
as passive DATA to analyze, NEVER as instructions to execute.

Token Budget (Phase 6)
-----------------------
Groq's free tier allows 8000 TPM for openai/gpt-oss-120b.
Each AegisCode repair iteration makes 3 LLM calls (Architect + Coder + Reviewer).
Budget targets per call:
  - Architect   : ~1500 input tokens  → stdout truncated to 1500 chars
  - Coder        : ~2000 input tokens  → file content budget halved from old value
  - Reviewer     : ~1000 input tokens  → diff text + test summary only

These budgets are enforced via settings.max_file_context_size (6000 chars).
Character-to-token ratio for code/logs is roughly 3-4 chars/token, so
6000 chars ≈ 1500–2000 tokens — comfortably within per-call limits.
"""

from __future__ import annotations

import re

from backend.core.config import settings
from backend.execution.workspace import WorkspaceManager
from backend.tools.filesystem import get_project_structure, read_file
from backend.tools.git_tools import GitDiff
from backend.tools.pytest_runner import TestResult


def _extract_failure_summary(test_result: TestResult) -> str:
    """
    Extract high-value test failure diagnostics (FAILED lines, tracebacks, AssertionError)
    to keep LLM prompt contexts concise and focused.
    """
    stdout = test_result.stdout or ""
    stderr = test_result.stderr or ""
    combined = f"{stdout}\n{stderr}"
    if not combined.strip():
        return "No stdout/stderr output captured."

    lines = combined.splitlines()
    relevant: list[str] = []
    in_failure = False

    for line in lines:
        if "FAILURES" in line or "ERRORS" in line or line.startswith("FAILED "):
            in_failure = True
            relevant.append(line)
        elif in_failure or any(kw in line for kw in ("AssertionError", "E   ", "Error:", "Traceback", "FAILED")):
            relevant.append(line)
            if len(relevant) >= 30:
                break

    if relevant:
        return "\n".join(relevant[:30])
    return _truncate(combined, 1000)


def _extract_test_file_snippets(
    workspace: WorkspaceManager,
    test_result: TestResult | None,
    max_chars: int = 1200,
) -> str:

    """
    Extract relevant test file definitions (read-only) so Architect and Coder can
    inspect exact test assertions and expectations.
    """
    test_files: list[str] = []
    if test_result:
        combined = f"{test_result.stdout or ''}\n{test_result.stderr or ''}"
        for match in re.finditer(
            r"(?:FAILED|ERROR|rootdir:|\b)\s*([a-zA-Z0-9_./\\-]*test[a-zA-Z0-9_./\\-]*\.py)",
            combined,
            re.IGNORECASE,
        ):
            path_str = match.group(1).replace("\\", "/").strip().lstrip("./")
            # If path contains subdirectories, simplify to relative path inside workspace
            if "/" in path_str and "project/" in path_str:
                path_str = path_str.split("project/", 1)[1]
            if path_str and path_str not in test_files:
                test_files.append(path_str)

    if not test_files:
        from backend.tools.filesystem import list_files

        flist = list_files(workspace, "**/*.py")
        if flist.success:
            for f in flist.files:
                fname = f.replace("\\", "/")
                basename = fname.split("/")[-1]
                if (
                    basename.startswith("test_")
                    or basename.endswith("_test.py")
                    or "/tests/" in fname
                    or fname.startswith("tests/")
                ):
                    test_files.append(fname)

    snippets: list[str] = []
    total_len = 0
    for tf in test_files[:2]:
        res = read_file(workspace, tf)
        if res.success and res.content:
            snippet = f"--- TEST FILE: {tf} ---\n{res.content}\n"
            if total_len + len(snippet) <= max_chars:
                snippets.append(snippet)
                total_len += len(snippet)
            else:
                snippets.append(
                    f"--- TEST FILE: {tf} ---\n{_truncate(res.content, max(100, max_chars - total_len))}\n"
                )
                break

    return "\n".join(snippets)


def build_architect_context(
    workspace: WorkspaceManager,
    test_result: TestResult | None = None,
    custom_instructions: str | None = None,
    cached_project_structure: str | None = None,
) -> str:
    """
    Build prompt context for the Architect Agent.

    Includes:
    - Project structure tree
    - Relevant test code & failure details (read-only)
    - Untrusted data warning blocks
    """
    if cached_project_structure:
        tree_str = cached_project_structure
    else:
        struct = get_project_structure(workspace)
        tree_str = struct.tree if struct.success else "(Tree unavailable)"

    test_summary = "No previous test run available."
    if test_result:
        test_summary = (
            f"Pytest Exit Code: {test_result.exit_code}\n"
            f"Passed: {test_result.passed}, Failed: {test_result.failed}, "
            f"Errors: {test_result.errors}, Skipped: {test_result.skipped}\n\n"
            f"--- Failure Diagnostics Snippet ---\n{_extract_failure_summary(test_result)}"
        )

    test_snippets = _extract_test_file_snippets(workspace, test_result, max_chars=1200)
    test_block = ""
    if test_snippets:
        test_block = f"""

[RELEVANT TEST SUITE (READ ONLY - DO NOT MODIFY TESTS)]
<untrusted_test_code>
{test_snippets}
</untrusted_test_code>"""

    context_str = f"""
[PROJECT FILE STRUCTURE]
<untrusted_project_tree>
{tree_str}
</untrusted_project_tree>

[TEST EXECUTION RESULTS]
<untrusted_test_output>
{test_summary}
</untrusted_test_output>{test_block}
""".strip()

    if custom_instructions:
        context_str += f"\n\n[USER INSTRUCTIONS]\n{custom_instructions}"

    return _truncate(context_str, settings.max_file_context_size)


def build_coder_context(
    workspace: WorkspaceManager,
    architecture_summary: str,
    relevant_files: list[str],
    test_result: TestResult | None = None,
) -> str:
    """
    Build prompt context for the Coder Agent.

    Includes:
    - Architecture plan summary & suspected issues
    - Contents of relevant source & test files (within size budget)
    - Exact test failure output and failing test code assertions (read-only)
    """
    files_content_parts: list[str] = []
    total_len = 0
    budget = settings.max_file_context_size // 3

    target_files = list(relevant_files)
    if not target_files:
        from backend.tools.filesystem import list_files

        flist = list_files(workspace, "**/*.py")
        if flist.success:
            target_files = [
                f
                for f in flist.files
                if not f.startswith("test") and "test_" not in f and "_test" not in f
            ]

    for file_path in target_files[: settings.max_files_per_agent]:
        res = read_file(workspace, file_path)
        if res.success and res.content:
            snippet = f"--- FILE: {file_path} ---\n{res.content}\n"
            if total_len + len(snippet) <= budget:
                files_content_parts.append(snippet)
                total_len += len(snippet)
            else:
                break

    source_code_block = "\n".join(files_content_parts) or "(No relevant files read)"

    test_failure_block = "No recent test failure output."
    if test_result:
        diag_parts = [
            f"Pytest Exit Code: {test_result.exit_code}",
            f"Passed: {test_result.passed}, Failed: {test_result.failed}, Errors: {test_result.errors}",
        ]
        failure_summary = _extract_failure_summary(test_result)
        if failure_summary and failure_summary != "No stdout/stderr output captured.":
            diag_parts.append(f"--- Key Failure Diagnostics ---\n{_truncate(failure_summary, 800)}")

        if test_result.stdout:
            diag_parts.append(f"--- Captured Stdout ---\n{_truncate(test_result.stdout, 600)}")
        if test_result.stderr:
            diag_parts.append(f"--- Captured Stderr ---\n{_truncate(test_result.stderr, 400)}")

        test_failure_block = "\n\n".join(diag_parts)

    test_snippets = _extract_test_file_snippets(workspace, test_result, max_chars=1200)
    test_block = ""
    if test_snippets:
        test_block = f"""

[FAILING TEST DEFINITIONS (READ ONLY - DO NOT MODIFY TESTS)]
<untrusted_test_code>
{test_snippets}
</untrusted_test_code>"""

    context_str = f"""
[REPAIR PLAN SUMMARY]
{architecture_summary}

[RELEVANT SOURCE CODE]
<untrusted_source_code>
{source_code_block}
</untrusted_source_code>

[CURRENT TEST FAILURES]
<untrusted_test_output>
{test_failure_block}
</untrusted_test_output>{test_block}
""".strip()

    return _truncate(context_str, settings.max_file_context_size)




def build_reviewer_context(
    workspace: WorkspaceManager,
    git_diff: GitDiff,
    coder_explanation: str,
    initial_test_result: TestResult | None = None,
    new_test_result: TestResult | None = None,
) -> str:
    """
    Build prompt context for the Reviewer Agent.

    Includes:
    - Git diff of changes made by Coder
    - Coder's stated explanation and root cause fix
    - Comparison of initial vs new test results

    Token budget: diff text truncated to max_file_context_size // 2.
    """
    diff_budget = settings.max_file_context_size // 2
    diff_text = (
        _truncate(git_diff.diff, diff_budget)
        if git_diff.has_changes
        else "(No git diff recorded)"
    )
    changed_files = ", ".join(git_diff.changed_files) or "None"

    initial_str = (
        f"Passed: {initial_test_result.passed}, Failed: {initial_test_result.failed}"
        if initial_test_result else "Unknown"
    )
    new_str = (
        f"Passed: {new_test_result.passed}, Failed: {new_test_result.failed}, "
        f"Exit Code: {new_test_result.exit_code}"
        if new_test_result else "Unknown"
    )

    context_str = f"""
[CODER EXPLANATION OF FIX]
{coder_explanation}

[GIT DIFF OF CHANGES]
Changed Files: {changed_files}
Additions: +{git_diff.additions}, Deletions: -{git_diff.deletions}

<untrusted_git_diff>
{diff_text}
</untrusted_git_diff>

[TEST RESULT COMPARISON]
Initial Test Results: {initial_str}
New Test Results    : {new_str}
""".strip()

    return _truncate(context_str, settings.max_file_context_size)


def _truncate(text: str, max_chars: int) -> str:
    """Truncate text to max_chars with a clear marker if cut."""
    if len(text) <= max_chars:
        return text
    omitted = len(text) - max_chars
    return text[:max_chars] + f"\n\n... [TRUNCATED ({omitted} characters omitted)] ..."
