"""Groq GPT-OSS structured-output provider hardening."""

from __future__ import annotations

import json
import re
from typing import Any, TypeVar

from pydantic import BaseModel

from backend.core.config import settings
from backend.llm.base import LLMProviderError
from backend.llm.openai import OpenAICompatibleLLMProvider

T = TypeVar("T", bound=BaseModel)


class StrictGroqLLMProvider(OpenAICompatibleLLMProvider):
    """OpenAI-compatible provider using Groq strict JSON Schema mode."""

    def generate(self, *args, **kwargs):
        """Use Groq's current max_completion_tokens parameter."""
        return super().generate(*args, **kwargs)

    def _call_with_retry(self, url, headers, payload):
        """Translate deprecated max_tokens to Groq's current parameter."""
        payload = dict(payload)
        if "max_tokens" in payload:
            payload["max_completion_tokens"] = payload.pop("max_tokens")
        payload.setdefault("reasoning_effort", "low")
        return super()._call_with_retry(url, headers, payload)

    def generate_structured(
        self,
        prompt: str,
        schema: type[T],
        system_prompt: str | None = None,
        temperature: float = 0.1,
    ) -> T:
        """Generate schema-conformant JSON with constrained decoding."""
        schema_json = _strict_json_schema(schema.model_json_schema())
        schema_text = json.dumps(schema_json, separators=(",", ":"))
        full_prompt = (
            f"{prompt}\n\nOUTPUT RULES: Return exactly one JSON object matching the schema. "
            "Keep all string fields concise. For code changes, return only the "
            "minimal targeted diff. No markdown, code fences, reasoning, or commentary. "
            f"Schema:{schema_text}"
        )
        raw_text = self.generate(
            prompt=full_prompt,
            system_prompt=system_prompt,
            temperature=temperature,
            max_tokens=settings.max_llm_output_tokens,
            response_format={
                "type": "json_schema",
                "json_schema": {
                    "name": _schema_name(schema),
                    "strict": True,
                    "schema": schema_json,
                },
            },
            reasoning_format="hidden",
            reasoning_effort="low",
        )
        try:
            return schema.model_validate(json.loads(raw_text.strip()))
        except Exception as exc:
            raise LLMProviderError(f"Invalid JSON returned by LLM: {exc}") from exc


def _schema_name(schema: type[BaseModel]) -> str:
    return re.sub(r"[^a-zA-Z0-9_-]", "_", schema.__name__.lower())[:64]


def _strict_json_schema(schema: dict[str, Any]) -> dict[str, Any]:
    """Make a Pydantic schema compliant with Groq strict-mode requirements."""
    normalized = json.loads(json.dumps(schema))

    def visit(node: Any) -> None:
        if isinstance(node, dict):
            if node.get("type") == "object" and "properties" in node:
                node["required"] = list(node["properties"].keys())
                node["additionalProperties"] = False
            for key in ("properties", "$defs", "definitions"):
                value = node.get(key)
                if isinstance(value, dict):
                    for child in value.values():
                        visit(child)
            for key in ("items", "anyOf", "oneOf", "allOf"):
                value = node.get(key)
                if isinstance(value, list):
                    for child in value:
                        visit(child)
                elif isinstance(value, dict):
                    visit(value)
        elif isinstance(node, list):
            for child in node:
                visit(child)

    visit(normalized)
    return normalized
