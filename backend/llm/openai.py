"""
OpenAI-Compatible LLM Provider — Phase 5 / Phase 6 (Rate-Limit Hardening).

Implements `BaseLLMProvider` for OpenAI and OpenAI-compatible REST endpoints
(e.g., Groq, Together, vLLM, LocalAI).

Rate-limit handling (Groq 429)
-------------------------------
All HTTP calls go through `_call_with_retry()`, which:
1. Detects HTTP 429 responses before raising.
2. Parses the `Retry-After` header (seconds) or extracts a wait hint from the
   Groq JSON error body (e.g. "Please try again in ~26 seconds").
3. Sleeps the required duration + a small random jitter (±2 s).
4. Retries up to MAX_RETRIES times with exponential back-off as a floor.
5. After all retries are exhausted, raises RateLimitError so callers can
   surface a clear, actionable error rather than a generic "LLM error".

Security note: OPENAI_API_KEY is never logged.
"""

from __future__ import annotations

import json
import random
import re
import time
from typing import TypeVar

import requests
from pydantic import BaseModel

from backend.core.config import settings
from backend.core.logging import get_logger
from backend.llm.base import BaseLLMProvider, LLMProviderError

logger = get_logger(__name__)

T = TypeVar("T", bound=BaseModel)

_MAX_RETRIES: int = 4
_BACKOFF_BASE: float = 5.0
_MAX_WAIT_SECONDS: float = 90.0
_JITTER_SECONDS: float = 2.0

_RETRY_AFTER_PATTERN = re.compile(
    r"(?:try again in\s*~?\s*)(\d+(?:\.\d+)?)\s*(?:seconds?|s\b)",
    re.IGNORECASE,
)


class RateLimitError(LLMProviderError):
    """Raised when a rate limit remains after all retry attempts."""


class OpenAICompatibleLLMProvider(BaseLLMProvider):
    """LLM provider for OpenAI-compatible chat completion APIs."""

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

    def _call_with_retry(
        self,
        url: str,
        headers: dict,
        payload: dict,
    ) -> requests.Response:
        """POST with production-safe 429 retry and exponential backoff."""
        last_exc: Exception | None = None

        for attempt in range(_MAX_RETRIES + 1):
            try:
                resp = requests.post(
                    url,
                    headers=headers,
                    json=payload,
                    timeout=self.timeout,
                )
            except requests.exceptions.Timeout as exc:
                raise LLMProviderError(
                    f"OpenAI API request timed out after {self.timeout}s"
                ) from exc
            except requests.exceptions.RequestException as exc:
                raise LLMProviderError(
                    f"OpenAI API network error: {exc}"
                ) from exc

            if resp.status_code != 429:
                return resp

            if attempt >= _MAX_RETRIES:
                try:
                    err_body = resp.json()
                    err_msg = (
                        err_body.get("error", {}).get("message", "")
                        or str(err_body)[:200]
                    )
                except Exception:
                    err_msg = resp.text[:200]

                raise RateLimitError(
                    f"Groq rate limit (HTTP 429) exhausted after {_MAX_RETRIES} retries. "
                    f"Error: {err_msg}. Please wait a minute and try again."
                )

            wait = _parse_retry_wait(resp, attempt)
            logger.warning(
                "Groq API rate limit hit (attempt %d/%d). Waiting %.1f s before retry. Model: %s",
                attempt + 1,
                _MAX_RETRIES,
                wait,
                self.model,
            )
            last_exc = None
            time.sleep(wait)

        raise RateLimitError(f"Rate limit retries exhausted ({last_exc})")

    def generate(
        self,
        prompt: str,
        system_prompt: str | None = None,
        temperature: float = 0.2,
        max_tokens: int | None = None,
        response_format: dict | None = None,
        reasoning_format: str | None = None,
    ) -> str:
        """Generate text, optionally enforcing an API response format."""
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
        if response_format is not None:
            payload["response_format"] = response_format
        if reasoning_format is not None:
            payload["reasoning_format"] = reasoning_format

        try:
            resp = self._call_with_retry(url, headers, payload)
            resp.raise_for_status()
            data = resp.json()
            return data["choices"][0]["message"]["content"]
        except RateLimitError:
            raise
        except requests.exceptions.HTTPError as exc:
            body_err = ""
            try:
                body_err = f" | Details: {resp.text[:300]}"
            except Exception:
                pass
            logger.error("OpenAI API HTTP error: %s%s", exc, body_err)
            raise LLMProviderError(
                f"OpenAI API request failed: {exc}{body_err}"
            ) from exc
        except LLMProviderError:
            raise
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
        """
        Generate a Pydantic-validated object.

        Groq/OpenAI-compatible JSON Object Mode is enabled for this path so
        model reasoning cannot leak into the JSON payload and malformed JSON
        such as unterminated strings is rejected by the provider itself.
        """
        schema_json = json.dumps(schema.model_json_schema(), indent=2)
        format_instruction = (
            "\n\nCRITICAL OUTPUT MANDATE:\n"
            "You MUST respond ONLY with one valid JSON object matching this schema:\n"
            f"{schema_json}\n"
            "Do NOT include markdown, code fences, reasoning, or commentary outside JSON."
        )

        full_prompt = f"{prompt}{format_instruction}"
        raw_text = self.generate(
            prompt=full_prompt,
            system_prompt=system_prompt,
            temperature=temperature,
            response_format={"type": "json_object"},
            reasoning_format="hidden",
        )

        cleaned = raw_text.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.split("\n", 1)[-1].rsplit("```", 1)[0].strip()

        try:
            parsed = json.loads(cleaned)
            return schema.model_validate(parsed)
        except Exception as exc:
            logger.error(
                "Failed to parse structured JSON from OpenAI-compatible output: %s",
                exc,
            )
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


def _parse_retry_wait(resp: requests.Response, attempt: int) -> float:
    """Determine a safe wait duration after a 429 response."""
    wait: float | None = None

    retry_after_hdr = resp.headers.get("Retry-After", "").strip()
    if retry_after_hdr.isdigit():
        wait = float(retry_after_hdr)

    if wait is None:
        try:
            body = resp.json()
            err_msg = body.get("error", {}).get("message", "") or ""
            m = _RETRY_AFTER_PATTERN.search(err_msg)
            if m:
                wait = float(m.group(1))
        except Exception:
            pass

    backoff_floor = _BACKOFF_BASE * (2 ** attempt)
    effective = max(wait or 0.0, backoff_floor)
    effective = min(effective, _MAX_WAIT_SECONDS)
    jitter = random.uniform(-_JITTER_SECONDS, _JITTER_SECONDS)
    return max(0.0, effective + jitter)
