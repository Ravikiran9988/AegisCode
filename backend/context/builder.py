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

from backend.core.config import settings
from backend.execution.workspace import WorkspaceManager
from backend.tools.filesystem import get_project_structure, read_file
from backend.tools.git_tools import GitDiff
from backend.tools.pytest_runner import TestResult


def build_architect_context(
    workspace: WorkspaceManager,
    test_result: TestResult | None = None,
    custom_instructions: str | None = None,
) -> str:
    """
    Build prompt context for the Architect Agent.

    Includes:
    - Project structure tree
    - Key test failure details (if available)
    - Untrusted data warning blocks

    Token budget: stdout truncated to 1500 chars, stderr to 800 chars.
    """
    struct = get_project_structure(workspace)
    tree_str = struct.tree if struct.success else "(Tree unavailable)"

    test_summary = "No previous test run available."
    if test_result:
        test_summary = (
            f"Pytest Exit Code: {test_result.exit_code}\n"
            f"Passed: {test_result.passed}, Failed: {test_result.failed}, "
            f"Errors: {test_result.errors}, Skipped: {test_result.skipped}\n\n"
            f"--- Captured Stdout Snippet ---\n{_truncate(test_result.stdout, 1500)}\n"
            f"--- Captured Stderr Snippet ---\n{_truncate(test_result.stderr, 800)}"
        )

    context_str = f"""
[PROJECT FILE STRUCTURE]
<untrusted_project_tree>
{tree_str}
</untrusted_project_tree>

[TEST EXECUTION RESULTS]
<untrusted_test_output>
{test_summary}
</untrusted_test_output>
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
    - Exact test failure output

    Token budget: file content budget = max_file_context_size // 3 (was // 2).
    Stdout truncated to 1200 chars (was 2500).
    """
    files_content_parts: list[str] = []
    total_len = 0
    # Tighter file content budget to reduce input tokens per call
    budget = settings.max_file_context_size // 3

    for file_path in relevant_files[: settings.max_files_per_agent]:
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
        test_failure_block = (
            f"Exit code: {test_result.exit_code}\n"
            f"Passed: {test_result.passed}, Failed: {test_result.failed}\n"
            f"Captured Output:\n{_truncate(test_result.stdout, 1200)}"
        )

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
</untrusted_test_output>
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
