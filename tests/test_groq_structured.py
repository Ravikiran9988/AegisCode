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
