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

# ── Retry / back-off constants ─────────────────────────────────────────────────
# Total attempts = 1 initial + MAX_RETRIES retries
_MAX_RETRIES: int = 4
# Minimum wait between retries (seconds) when no Retry-After header is present
_BACKOFF_BASE: float = 5.0
# Hard cap: never wait more than this many seconds regardless of Retry-After
_MAX_WAIT_SECONDS: float = 90.0
# ±jitter added to every wait to avoid thundering-herd on shared rate limits
_JITTER_SECONDS: float = 2.0

# Regex to extract seconds from Groq's error text
# e.g. "Please try again in ~26 seconds." or "try again in 10s"
_RETRY_AFTER_PATTERN = re.compile(
    r"(?:try again in\s*~?\s*)(\d+(?:\.\d+)?)\s*(?:seconds?|s\b)",
    re.IGNORECASE,
)


class RateLimitError(LLMProviderError):
    """
    Raised when the Groq / OpenAI-compatible API returns HTTP 429 and all
    retry attempts have been exhausted.
    """


class OpenAICompatibleLLMProvider(BaseLLMProvider):
    """
    LLM provider calling an OpenAI-compatible REST API (/v1/chat/completions).

    Production target: openai/gpt-oss-120b via https://api.groq.com/openai/v1
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

    # ── Internal: rate-limit-aware HTTP POST ───────────────────────────────────

    def _call_with_retry(
        self,
        url: str,
        headers: dict,
        payload: dict,
    ) -> requests.Response:
        """
        POST to *url* with automatic 429 retry + exponential back-off.

        Retry logic
        -----------
        * On HTTP 429: parse Retry-After header or body hint; sleep; retry.
        * Back-off floor: max(parsed_wait, backoff_base * 2^attempt).
        * Hard cap: _MAX_WAIT_SECONDS.
        * Jitter: ±_JITTER_SECONDS.
        * After _MAX_RETRIES retries: raise RateLimitError.

        Never logs the Authorization header value.
        """
        last_exc: Exception | None = None

        for attempt in range(_MAX_RETRIES + 1):  # attempt 0 = first try
            try:
                resp = requests.post(
                    url,
                    headers=headers,
                    json=payload,
                    timeout=self.timeout,
                )
            except requests.exceptions.Timeout as exc:
                # Network-level timeout — not a rate-limit; re-raise immediately
                raise LLMProviderError(
                    f"OpenAI API request timed out after {self.timeout}s"
                ) from exc
            except requests.exceptions.RequestException as exc:
                raise LLMProviderError(
                    f"OpenAI API network error: {exc}"
                ) from exc

            if resp.status_code != 429:
                # Success or a non-rate-limit error — return as-is
                return resp

            # ── HTTP 429 handling ─────────────────────────────────────────────
            if attempt >= _MAX_RETRIES:
                # All retries exhausted
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
                    f"Error: {err_msg}. "
                    "Please wait a minute and try again."
                )

            wait = _parse_retry_wait(resp, attempt)
            logger.warning(
                "Groq API rate limit hit (attempt %d/%d). "
                "Waiting %.1f s before retry. Model: %s",
                attempt + 1,
                _MAX_RETRIES,
                wait,
                self.model,
            )
            last_exc = None  # reset — we'll retry
            time.sleep(wait)

        # Should not reach here but satisfy mypy
        raise RateLimitError(
            f"Rate limit retries exhausted ({last_exc})"
        )

    # ── Public API ─────────────────────────────────────────────────────────────

    def generate(
        self,
        prompt: str,
        system_prompt: str | None = None,
        temperature: float = 0.2,
        max_tokens: int | None = None,
    ) -> str:
        url = f"{self.base_url}/chat/completions"
        # Never log the raw Authorization header value
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
            resp = self._call_with_retry(url, headers, payload)
            resp.raise_for_status()
            data = resp.json()
            return data["choices"][0]["message"]["content"]
        except RateLimitError:
            raise  # preserve specific type
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


# ── Helpers ────────────────────────────────────────────────────────────────────

def _parse_retry_wait(resp: requests.Response, attempt: int) -> float:
    """
    Determine how long to wait after receiving a 429 response.

    Priority order:
    1. ``Retry-After`` HTTP header (standard, in seconds).
    2. Groq JSON error body text (e.g. "try again in ~26 seconds").
    3. Exponential back-off floor: ``_BACKOFF_BASE * 2^attempt``.

    The result is clamped to [_BACKOFF_BASE, _MAX_WAIT_SECONDS] and
    a random jitter of ±_JITTER_SECONDS is added.
    """
    wait: float | None = None

    # 1. Standard Retry-After header
    retry_after_hdr = resp.headers.get("Retry-After", "").strip()
    if retry_after_hdr.isdigit():
        wait = float(retry_after_hdr)

    # 2. Groq JSON body hint
    if wait is None:
        try:
            body = resp.json()
            err_msg = body.get("error", {}).get("message", "") or ""
            m = _RETRY_AFTER_PATTERN.search(err_msg)
            if m:
                wait = float(m.group(1))
        except Exception:
            pass

    # 3. Exponential back-off floor
    backoff_floor = _BACKOFF_BASE * (2 ** attempt)
    effective = max(wait or 0.0, backoff_floor)
    effective = min(effective, _MAX_WAIT_SECONDS)

    # Add jitter
    jitter = random.uniform(-_JITTER_SECONDS, _JITTER_SECONDS)
    return max(0.0, effective + jitter)
