"""
BaseLLMProvider — Abstract LLM Provider Interface.

Defines the contract for text generation and Pydantic structured output.
All concrete providers (Ollama, OpenAI, Mock) implement this base class.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TypeVar

from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)


class LLMProviderError(Exception):
    """Base exception for LLM provider errors."""


class BaseLLMProvider(ABC):
    """Abstract LLM Provider interface."""

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Name identifier of provider."""
        ...

    @property
    @abstractmethod
    def model_name(self) -> str:
        """Name identifier of configured model."""
        ...

    @abstractmethod
    def generate(self, prompt: str, system_prompt: str | None = None) -> str:
        """
        Generate raw text response given prompt and optional system prompt.
        """
        ...

    @abstractmethod
    def generate_structured(
        self,
        schema: type[T],
        prompt: str,
        system_prompt: str | None = None,
    ) -> T:
        """
        Generate structured output conforming to the Pydantic `schema`.

        Validates the output against the model; raises LLMProviderError if
        validation fails.
        """
        ...

    @abstractmethod
    def is_available(self) -> tuple[bool, str]:
        """
        Check provider health / availability.

        Returns (is_available, status_message).
        """
        ...
