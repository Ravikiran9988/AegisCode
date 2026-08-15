"""
Pydantic Schemas for Agent Outputs — Phase 3.

Defines strongly typed, validated output structures for:
- ArchitectAgent -> ArchitecturePlan
- CoderAgent     -> CodeChange
- ReviewerAgent  -> ReviewResult

All LLM agents produce outputs validating against these models.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class ArchitecturePlan(BaseModel):
    """Structured output produced by the Architect Agent."""

    summary: str = Field(
        description="High-level architectural summary of the problem and repair strategy."
    )
    project_type: str = Field(
        default="python",
        description="Identified project domain / pattern (e.g., CLI, library, API, package)."
    )
    relevant_files: list[str] = Field(
        default_factory=list,
        description="List of relative file paths relevant to the failure or repair."
    )
    suspected_issues: list[str] = Field(
        default_factory=list,
        description="List of suspected root causes or bug locations."
    )
    dependencies: list[str] = Field(
        default_factory=list,
        description="Key internal or external dependencies involved in the bug."
    )
    test_strategy: str = Field(
        description="Specific testing approach to verify the fix."
    )
    confidence: float = Field(
        default=0.8,
        ge=0.0,
        le=1.0,
        description="Confidence score (0.0 to 1.0) in the proposed repair plan."
    )


class CodeChange(BaseModel):
    """Structured output produced by the Coder Agent."""

    file_path: str = Field(
        description="Relative file path within the project to modify."
    )
    change_type: Literal["patch", "write", "none"] = Field(
        description="Type of modification: unified diff patch, full file write, or none."
    )
    explanation: str = Field(
        description="Clear explanation of the changes made and why."
    )
    root_cause: str = Field(
        description="Identified root cause that this code change fixes."
    )
    patch: str = Field(
        default="",
        description="The unified diff patch or full file content to apply."
    )
    confidence: float = Field(
        default=0.8,
        ge=0.0,
        le=1.0,
        description="Confidence score (0.0 to 1.0) that this change fixes the bug."
    )


class ReviewResult(BaseModel):
    """Structured output produced by the Reviewer Agent."""

    approved: bool = Field(
        description="True if the changes fix the root cause cleanly without regressions."
    )
    root_cause_fixed: bool = Field(
        description="True if the reviewer confirmed the core bug was addressed."
    )
    regression_risk: Literal["low", "medium", "high"] = Field(
        default="low",
        description="Estimated risk of regressions introduced by this patch."
    )
    issues: list[str] = Field(
        default_factory=list,
        description="List of remaining or introduced issues/flaws identified during review."
    )
    reasoning: str = Field(
        description="Detailed review reasoning and assessment."
    )
    recommendation: str = Field(
        description=(
            "Actionable recommendation (e.g. 'Approve fix', "
            "'Retry with alternative approach')."
        )
    )
