"""
OpenAI-Compatible LLM Provider — Phase 5.

Implements `BaseLLMProvider` for OpenAI and OpenAI-compatible REST endpoints
(e.g., OpenAI API, DeepSeek, Groq, Together, vLLM, LocalAI).
"""

from __future__ import annotations

import json
from typing import TypeVar

import requests
from pydantic import BaseModel

from backend.core.config import settings
from backend.core.logging import get_logger
from backend.llm.base import BaseLLMProvider, LLMProviderError

logger = get_logger(__name__)

T = TypeVar("T", bound=BaseModel)


class OpenAICompatibleLLMProvider(BaseLLMProvider):
    """
    LLM provider calling an OpenAI-compatible REST API (/v1/chat/completions).
    """

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        model: str | None = None,
        timeout: int | None = None,
    ) -> None:
        self.api_key = api_key or settings.openai_api_key
        self.base_url = (base_url or settings.openai_base_url).rstrip("/")
        self.model = model or settings.openai_model
        self.timeout = timeout or settings.llm_timeout_seconds

    @property
    def provider_name(self) -> str:
        return "openai_compatible"

    @property
    def model_name(self) -> str:
        return self.model

    def generate(
        self,
        prompt: str,
        system_prompt: str | None = None,
        temperature: float = 0.2,
        max_tokens: int | None = None,
    ) -> str:
        url = f"{self.base_url}/chat/completions"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens or settings.max_llm_output_tokens,
        }

        try:
            resp = requests.post(url, headers=headers, json=payload, timeout=self.timeout)
            resp.raise_for_status()
            data = resp.json()
            return data["choices"][0]["message"]["content"]
        except requests.exceptions.HTTPError as exc:
            body_err = ""
            try:
                body_err = f" | Details: {resp.text[:300]}"
            except Exception:
                pass
            logger.error("OpenAI API HTTP error: %s%s", exc, body_err)
            raise LLMProviderError(f"OpenAI API request failed: {exc}{body_err}") from exc
        except Exception as exc:
            logger.error("OpenAI API call failed: %s", exc)
            raise LLMProviderError(f"OpenAI API request failed: {exc}") from exc

    def generate_structured(
        self,
        prompt: str,
        schema: type[T],
        system_prompt: str | None = None,
        temperature: float = 0.1,
    ) -> T:
        schema_json = json.dumps(schema.model_json_schema(), indent=2)
        format_instruction = (
            f"\n\nCRITICAL OUTPUT MANDATE:\n"
            f"You MUST respond ONLY with a valid JSON object matching schema:\n"
            f"{schema_json}\n"
            f"Do NOT include markdown formatting or commentary outside JSON."
        )

        full_prompt = f"{prompt}{format_instruction}"
        raw_text = self.generate(
            prompt=full_prompt,
            system_prompt=system_prompt,
            temperature=temperature,
        )

        # Clean potential markdown wrapping
        cleaned = raw_text.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.split("\n", 1)[-1].rsplit("```", 1)[0].strip()

        try:
            parsed = json.loads(cleaned)
            return schema.model_validate(parsed)
        except Exception as exc:
            logger.error("Failed to parse structured JSON from OpenAI output: %s", exc)
            raise LLMProviderError(f"Invalid JSON returned by LLM: {exc}") from exc

    def is_available(self) -> tuple[bool, str]:
        if not self.api_key or self.api_key == "your_openai_api_key_here":
            return False, "OpenAI API key not configured."
        try:
            url = f"{self.base_url}/models"
            headers = {"Authorization": f"Bearer {self.api_key}"}
            resp = requests.get(url, headers=headers, timeout=5)
            if resp.status_code == 200:
                return True, f"OpenAI API reachable (model: {self.model})"
            return False, f"OpenAI API returned status {resp.status_code}"
        except Exception as exc:
            return False, f"OpenAI API connection failed: {exc}"
