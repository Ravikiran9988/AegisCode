"""
MockLLMProvider — Offline mock provider for testing.

Provides deterministic responses without requiring an Ollama daemon.
"""

from __future__ import annotations

from typing import Any, TypeVar

from pydantic import BaseModel

from backend.agents.schemas import ArchitecturePlan, CodeChange, ReviewResult
from backend.llm.base import BaseLLMProvider, LLMProviderError

T = TypeVar("T", bound=BaseModel)


class MockLLMProvider(BaseLLMProvider):
    """Deterministic mock provider for unit & agent testing."""

    def __init__(
        self,
        mock_plan: ArchitecturePlan | None = None,
        mock_change: CodeChange | None = None,
        mock_review: ReviewResult | None = None,
        should_fail: bool = False,
    ) -> None:
        self.mock_plan = mock_plan or ArchitecturePlan(
            summary="Mock architecture plan for testing",
            project_type="python",
            relevant_files=["calculator.py"],
            suspected_issues=["Incorrect operator in subtract"],
            dependencies=[],
            test_strategy="Run pytest after targeted fix",
            confidence=0.9,
        )
        self.mock_change = mock_change or CodeChange(
            file_path="calculator.py",
            change_type="write",
            explanation="Fixed operator in subtract function",
            root_cause="subtract function used + instead of -",
            patch="def subtract(a, b):\n    return a - b\n",
            confidence=0.95,
        )
        self.mock_review = mock_review or ReviewResult(
            approved=True,
            root_cause_fixed=True,
            regression_risk="low",
            issues=[],
            reasoning="Fix replaces incorrect addition operator with subtraction.",
            recommendation="Approve change and complete run",
        )
        self.should_fail = should_fail
        self.last_prompt: str | None = None
        self.last_system_prompt: str | None = None

    @property
    def provider_name(self) -> str:
        return "mock"

    @property
    def model_name(self) -> str:
        return "mock-model-v1"

    def is_available(self) -> tuple[bool, str]:
        if self.should_fail:
            return False, "Mock provider forced failure mode"
        return True, "Mock provider online (offline mode)"

    def generate(
        self,
        prompt: str,
        system_prompt: str | None = None,
        **kwargs: Any,
    ) -> str:
        self.last_prompt = prompt
        self.last_system_prompt = system_prompt
        if self.should_fail:
            raise LLMProviderError("Mock provider simulated failure")
        return "Mock generated text response"

    def generate_structured(
        self,
        schema: Any,
        prompt: Any = "",
        system_prompt: str | None = None,
        **kwargs: Any,
    ) -> Any:
        if isinstance(schema, str) and isinstance(prompt, type) and issubclass(prompt, BaseModel):
            target_schema: type[BaseModel] = prompt
            actual_prompt: str = schema
        elif isinstance(schema, type) and issubclass(schema, BaseModel):
            target_schema = schema
            actual_prompt = str(prompt)
        else:
            target_schema = schema
            actual_prompt = str(prompt)

        self.last_prompt = actual_prompt
        self.last_system_prompt = system_prompt

        if self.should_fail:
            raise LLMProviderError("Mock provider simulated failure")

        if target_schema == ArchitecturePlan:
            return self.mock_plan  # type: ignore[return-value]
        elif target_schema == CodeChange:
            return self.mock_change  # type: ignore[return-value]
        elif target_schema == ReviewResult:
            return self.mock_review  # type: ignore[return-value]

        # Generic fallback
        try:
            return target_schema()  # type: ignore[call-arg]
        except Exception as exc:
            msg = f"Mock provider cannot construct schema {target_schema}: {exc}"
            raise LLMProviderError(msg) from exc
