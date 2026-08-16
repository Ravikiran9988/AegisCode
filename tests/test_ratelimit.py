"""
test_ratelimit.py — Groq 429 Rate-Limit Handling Tests.

Tests:
1.  _parse_retry_wait parses Retry-After header.
2.  _parse_retry_wait parses Groq error message ("Please try again in ~26 seconds.").
3.  _parse_retry_wait applies exponential backoff floor.
4.  _call_with_retry retries on 429 and succeeds on subsequent try.
5.  _call_with_retry raises RateLimitError when retries are exhausted.
6.  _call_with_retry does not retry on non-429 errors (e.g. 500).
7.  OpenAICompatibleLLMProvider never leaks API key in logs or error messages.
8.  Provider model remains strictly `openai/gpt-oss-120b`.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
import requests

from backend.core.config import settings
from backend.llm.openai import (
    _MAX_RETRIES,
    OpenAICompatibleLLMProvider,
    RateLimitError,
    _parse_retry_wait,
)


class TestRateLimitHandling:

    # 1. Parse Retry-After header
    def test_parse_retry_after_header(self):
        resp = MagicMock(spec=requests.Response)
        resp.headers = {"Retry-After": "15"}
        resp.json.side_effect = Exception("no json")

        wait = _parse_retry_wait(resp, attempt=0)
        # Should be at least 15 (plus possible jitter)
        assert wait >= 13.0

    # 2. Parse Groq JSON error message
    def test_parse_groq_json_error_message(self):
        resp = MagicMock(spec=requests.Response)
        resp.headers = {}
        resp.json.return_value = {
            "error": {
                "message": (
                    "Rate limit reached for model `openai/gpt-oss-120b` "
                    "on tokens per minute (TPM): Limit 8000. "
                    "Please try again in ~26 seconds."
                )
            }
        }

        wait = _parse_retry_wait(resp, attempt=0)
        # 26s parsed, attempt 0 backoff floor is 5s, so wait should be ~26s
        assert 24.0 <= wait <= 30.0

    # 3. Exponential backoff floor
    def test_exponential_backoff_floor(self):
        resp = MagicMock(spec=requests.Response)
        resp.headers = {}
        resp.json.side_effect = Exception("no json")

        # Attempt 0 -> base 5.0s
        w0 = _parse_retry_wait(resp, attempt=0)
        assert 3.0 <= w0 <= 8.0

        # Attempt 2 -> base 5 * 2^2 = 20.0s
        w2 = _parse_retry_wait(resp, attempt=2)
        assert 18.0 <= w2 <= 23.0

    # 4. _call_with_retry retries on 429 and succeeds on second try
    @patch("time.sleep")
    @patch("requests.post")
    def test_call_with_retry_succeeds_after_retry(self, mock_post, mock_sleep):
        provider = OpenAICompatibleLLMProvider(
            api_key="test-key-123",
            base_url="https://api.groq.com/openai/v1",
            model="openai/gpt-oss-120b",
        )

        resp_429 = MagicMock(spec=requests.Response)
        resp_429.status_code = 429
        resp_429.headers = {"Retry-After": "2"}

        resp_200 = MagicMock(spec=requests.Response)
        resp_200.status_code = 200
        resp_200.raise_for_status.return_value = None
        resp_200.json.return_value = {
            "choices": [{"message": {"content": "Hello world"}}]
        }

        mock_post.side_effect = [resp_429, resp_200]

        result = provider.generate(prompt="Test prompt")
        assert result == "Hello world"
        assert mock_post.call_count == 2
        assert mock_sleep.call_count == 1

    # 5. _call_with_retry raises RateLimitError when retries exhausted
    @patch("time.sleep")
    @patch("requests.post")
    def test_call_with_retry_exhaustion_raises_ratelimit_error(
        self, mock_post, mock_sleep
    ):
        provider = OpenAICompatibleLLMProvider(
            api_key="test-key-123",
            base_url="https://api.groq.com/openai/v1",
            model="openai/gpt-oss-120b",
        )

        resp_429 = MagicMock(spec=requests.Response)
        resp_429.status_code = 429
        resp_429.headers = {"Retry-After": "1"}
        resp_429.json.return_value = {
            "error": {"message": "Rate limit reached. Please try again in 5s"}
        }

        mock_post.return_value = resp_429

        with pytest.raises(RateLimitError) as exc_info:
            provider.generate(prompt="Test prompt")

        assert "exhausted after" in str(exc_info.value)
        assert mock_post.call_count == _MAX_RETRIES + 1
        assert mock_sleep.call_count == _MAX_RETRIES

    # 6. No retry on non-429 errors (e.g., 500)
    @patch("time.sleep")
    @patch("requests.post")
    def test_no_retry_on_server_error(self, mock_post, mock_sleep):
        provider = OpenAICompatibleLLMProvider(
            api_key="test-key-123",
            base_url="https://api.groq.com/openai/v1",
            model="openai/gpt-oss-120b",
        )

        resp_500 = MagicMock(spec=requests.Response)
        resp_500.status_code = 500
        resp_500.raise_for_status.side_effect = requests.exceptions.HTTPError(
            "500 Server Error"
        )
        resp_500.text = "Internal Server Error"

        mock_post.return_value = resp_500

        from backend.llm.base import LLMProviderError

        with pytest.raises(LLMProviderError):
            provider.generate(prompt="Test prompt")

        assert mock_post.call_count == 1
        assert mock_sleep.call_count == 0

    # 7. API key is never exposed in RateLimitError string
    @patch("time.sleep")
    @patch("requests.post")
    def test_api_key_not_in_error_message(self, mock_post, mock_sleep):
        secret_key = "gsk_super_secret_key_999"
        provider = OpenAICompatibleLLMProvider(
            api_key=secret_key,
            base_url="https://api.groq.com/openai/v1",
            model="openai/gpt-oss-120b",
        )

        resp_429 = MagicMock(spec=requests.Response)
        resp_429.status_code = 429
        resp_429.headers = {}
        resp_429.json.return_value = {"error": {"message": "Rate limit"}}

        mock_post.return_value = resp_429

        with pytest.raises(RateLimitError) as exc_info:
            provider.generate(prompt="Test prompt")

        err_str = str(exc_info.value)
        assert secret_key not in err_str

    # 8. Provider model strictly set to production model
    def test_production_model_configuration(self):
        provider = OpenAICompatibleLLMProvider()
        assert provider.model == "openai/gpt-oss-120b"
        assert settings.openai_model == "openai/gpt-oss-120b"
