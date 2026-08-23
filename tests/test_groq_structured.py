"""Regression tests for Groq GPT-OSS structured output hardening."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from pydantic import BaseModel

from backend.core.config import settings
from backend.llm.openai_strict import StrictGroqLLMProvider


class RepairResult(BaseModel):
    file_path: str
    change_type: str
    explanation: str = ""
    patch: str = ""


@patch("requests.post")
def test_strict_provider_uses_current_completion_parameter(mock_post):
    response = MagicMock()
    response.status_code = 200
    response.json.return_value = {
        "choices": [
            {
                "message": {
                    "content": (
                        '{"file_path":"app.py","change_type":"patch",'
                        '"explanation":"fix","patch":"@@ -1 +1 @@\\n-x\\n+y"}'
                    )
                }
            }
        ]
    }
    mock_post.return_value = response

    provider = StrictGroqLLMProvider(api_key="gsk-test-key")
    result = provider.generate_structured(
        "Repair the failing file.",
        RepairResult,
    )

    assert result.file_path == "app.py"
    payload = mock_post.call_args.kwargs["json"]
    assert payload["max_completion_tokens"] == settings.max_llm_output_tokens
    assert "max_tokens" not in payload
    assert payload["reasoning_effort"] == "low"
    response_format = payload["response_format"]
    assert response_format["type"] == "json_schema"
    assert response_format["json_schema"]["strict"] is True

    schema = response_format["json_schema"]["schema"]
    assert schema["additionalProperties"] is False
    assert set(schema["required"]) == set(schema["properties"])


@patch("requests.post")
def test_strict_provider_keeps_code_change_output_compact(mock_post):
    response = MagicMock()
    response.status_code = 200
    response.json.return_value = {
        "choices": [
            {
                "message": {
                    "content": (
                        '{"file_path":"x.py","change_type":"patch",'
                        '"explanation":"small fix","patch":"@@ -1 +1 @@\\n-a\\n+b"}'
                    )
                }
            }
        ]
    }
    mock_post.return_value = response

    provider = StrictGroqLLMProvider(api_key="gsk-test-key")
    result = provider.generate_structured("Apply the minimal fix.", RepairResult)

    assert result.change_type == "patch"
    assert result.patch.startswith("@@")


@patch("requests.post")
def test_strict_provider_accepts_max_tokens_keyword_argument(mock_post):
    response = MagicMock()
    response.status_code = 200
    response.json.return_value = {
        "choices": [
            {
                "message": {
                    "content": (
                        '{"file_path":"app.py","change_type":"write",'
                        '"explanation":"fix","patch":"print(1)"}'
                    )
                }
            }
        ]
    }
    mock_post.return_value = response

    provider = StrictGroqLLMProvider(api_key="gsk-test-key")
    result = provider.generate_structured(
        schema=RepairResult,
        prompt="Fix app.py",
        system_prompt="You are a coder.",
        max_tokens=1500,
    )

    assert result.file_path == "app.py"
    payload = mock_post.call_args.kwargs["json"]
    assert payload["max_completion_tokens"] == 1500
    assert "max_tokens" not in payload


@patch("requests.post")
def test_strict_provider_flexible_argument_ordering(mock_post):
    response = MagicMock()
    response.status_code = 200
    response.json.return_value = {
        "choices": [
            {
                "message": {
                    "content": (
                        '{"file_path":"b.py","change_type":"write",'
                        '"explanation":"fix","patch":"print(2)"}'
                    )
                }
            }
        ]
    }
    mock_post.return_value = response

    provider = StrictGroqLLMProvider(api_key="gsk-test-key")
    # Call with schema first (positional)
    res1 = provider.generate_structured(RepairResult, "Fix b.py", max_tokens=800)
    assert res1.file_path == "b.py"
    assert mock_post.call_args.kwargs["json"]["max_completion_tokens"] == 800

    # Call with prompt first (positional)
    res2 = provider.generate_structured("Fix b.py", RepairResult, max_tokens=1200)
    assert res2.file_path == "b.py"
    assert mock_post.call_args.kwargs["json"]["max_completion_tokens"] == 1200

