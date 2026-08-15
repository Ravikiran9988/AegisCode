"""
OllamaLLMProvider — Local Ollama LLM implementation.

Uses the Ollama REST API / SDK to generate text and structured outputs.
Configured via `OLLAMA_BASE_URL` and `OLLAMA_MODEL`.
"""

from __future__ import annotations

import json
from typing import TypeVar

import requests
from pydantic import BaseModel, ValidationError

from backend.core.config import settings
from backend.core.logging import get_logger
from backend.llm.base import BaseLLMProvider, LLMProviderError

logger = get_logger(__name__)

T = TypeVar("T", bound=BaseModel)


class OllamaLLMProvider(BaseLLMProvider):
    """Local Ollama provider implementation."""

    def __init__(
        self,
        base_url: str | None = None,
        model: str | None = None,
        timeout: int | None = None,
    ) -> None:
        self.base_url = (base_url or settings.ollama_base_url).rstrip("/")
        self.model = model or settings.ollama_model
        self.timeout = timeout or settings.llm_timeout_seconds

    @property
    def provider_name(self) -> str:
        return "ollama"

    @property
    def model_name(self) -> str:
        return self.model

    def is_available(self) -> tuple[bool, str]:
        """Ping Ollama daemon endpoint to verify reachability."""
        try:
            resp = requests.get(f"{self.base_url}/api/tags", timeout=5)
            if resp.status_code == 200:
                models = [m.get("name") for m in resp.json().get("models", [])]
                return True, f"Ollama online at {self.base_url}. Models available: {models}"
            return False, f"Ollama API returned HTTP {resp.status_code}"
        except Exception as exc:
            return False, f"Ollama unreachable at {self.base_url}: {exc}"

    def generate(self, prompt: str, system_prompt: str | None = None) -> str:
        url = f"{self.base_url}/api/generate"
        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
        }
        if system_prompt:
            payload["system"] = system_prompt

        try:
            resp = requests.post(url, json=payload, timeout=self.timeout)
            resp.raise_for_status()
            data = resp.json()
            return data.get("response", "")
        except Exception as exc:
            logger.error("Ollama generate error: %s", exc)
            raise LLMProviderError(f"Ollama generation failed: {exc}") from exc

    def generate_structured(
        self,
        schema: type[T],
        prompt: str,
        system_prompt: str | None = None,
    ) -> T:
        """
        Request JSON format output from Ollama and validate against Pydantic schema.
        """
        json_schema_prompt = (
            f"You MUST return valid JSON conforming to this JSON schema:\n"
            f"{json.dumps(schema.model_json_schema(), indent=2)}\n\n"
            f"Do not include markdown code block formatting in your JSON output if possible."
        )

        full_system = f"{system_prompt or ''}\n\n{json_schema_prompt}".strip()

        url = f"{self.base_url}/api/generate"
        payload = {
            "model": self.model,
            "prompt": prompt,
            "system": full_system,
            "format": "json",  # Enforce JSON mode in Ollama API
            "stream": False,
        }

        try:
            resp = requests.post(url, json=payload, timeout=self.timeout)
            resp.raise_for_status()
            raw_text = resp.json().get("response", "")

            # Clean potential markdown wrapping
            cleaned = _clean_json_str(raw_text)
            parsed_data = json.loads(cleaned)
            return schema.model_validate(parsed_data)

        except json.JSONDecodeError as exc:
            logger.warning("Ollama returned invalid JSON: %s", exc)
            raise LLMProviderError(f"Ollama returned invalid JSON: {exc}") from exc
        except ValidationError as exc:
            logger.warning("Ollama output failed Pydantic validation: %s", exc)
            raise LLMProviderError(f"Ollama output validation failed: {exc}") from exc
        except Exception as exc:
            logger.error("Ollama structured generate error: %s", exc)
            raise LLMProviderError(f"Ollama structured generation failed: {exc}") from exc


def _clean_json_str(text: str) -> str:
    """Remove ```json ... ``` wrapper if model included it."""
    cleaned = text.strip()
    if cleaned.startswith("```"):
        lines = cleaned.splitlines()
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].startswith("```"):
            lines = lines[:-1]
        cleaned = "\n".join(lines).strip()
    return cleaned
