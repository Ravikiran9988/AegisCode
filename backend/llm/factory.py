"""
LLM Provider Factory & Health Check — Phase 3.

Factory function `get_llm_provider()` reads `settings.llm_provider` to
instantiate the configured provider.

`check_llm_health()` returns structured availability status.
"""

from __future__ import annotations

from backend.core.config import settings
from backend.core.logging import get_logger
from backend.llm.base import BaseLLMProvider
from backend.llm.mock import MockLLMProvider
from backend.llm.ollama import OllamaLLMProvider
from backend.llm.openai import OpenAICompatibleLLMProvider

logger = get_logger(__name__)


def get_llm_provider(
    provider_name: str | None = None,
    provider_type: str | None = None,
    override_instance: BaseLLMProvider | None = None,
) -> BaseLLMProvider:
    """
    Factory function returning the configured LLM provider instance.

    Parameters
    ----------
    provider_name / provider_type:
        Override configured provider ('ollama', 'openai_compatible', 'mock', etc.)
    override_instance:
        Directly supply a provider instance (useful in unit tests).
    """
    if override_instance:
        return override_instance

    pname = provider_name or provider_type or settings.llm_provider
    name = (pname).lower()

    if name == "mock":
        logger.info("Using Mock LLM Provider")
        return MockLLMProvider()
    elif name == "ollama":
        logger.info(
            "Using Ollama LLM Provider (url=%s, model=%s)",
            settings.ollama_base_url, settings.ollama_model,
        )
        return OllamaLLMProvider()
    elif name in ("openai", "openai_compatible", "hosted"):
        logger.info(
            "Using OpenAICompatibleLLMProvider (url=%s, model=%s)",
            settings.openai_base_url, settings.openai_model,
        )
        return OpenAICompatibleLLMProvider()
    else:
        raise ValueError(
            f"Unsupported LLM provider {name!r}. Production AegisCode requires "
            f"'openai_compatible' with Groq model 'openai/gpt-oss-120b'."
        )


def check_llm_health(provider_name: str | None = None) -> dict[str, str | bool]:
    """
    Check availability of the configured LLM provider.

    Returns structured status dictionary.
    """
    provider = get_llm_provider(provider_name)
    available, msg = provider.is_available()
    return {
        "provider": provider.provider_name,
        "model": provider.model_name,
        "available": available,
        "status_message": msg,
    }
