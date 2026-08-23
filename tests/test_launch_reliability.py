from __future__ import annotations

from unittest.mock import patch

import requests

from backend.agents.schemas import ArchitecturePlan, CodeChange, ReviewResult
from backend.core.config import settings
from backend.graph.graph import initial_entry_router
from backend.llm.openai_strict import StrictGroqLLMProvider
from frontend.utils.api_client import _request_error_message


def _test_result(*, success: bool) -> dict:
    return {
        "passed": 4 if success else 3,
        "failed": 0 if success else 1,
        "errors": 0,
        "skipped": 0,
        "exit_code": 0 if success else 1,
        "success": success,
        "duration": 0.1,
        "stdout": "",
        "stderr": "",
    }


def test_initial_entry_router_reuses_passing_baseline():
    state = {"initial_test_result": _test_result(success=True), "status": "running"}

    assert initial_entry_router(state) == "end"
    assert state["status"] == "already_passing"
    assert state["termination_reason"] == "all_tests_passed"


def test_initial_entry_router_reuses_failing_baseline_without_rerunning_pytest():
    state = {"initial_test_result": _test_result(success=False), "status": "running"}

    assert initial_entry_router(state) == "architect"


def test_initial_entry_router_runs_pytest_when_no_persisted_baseline():
    assert initial_entry_router({"status": "running"}) == "run_initial_test"


def test_backend_transport_errors_are_actionable():
    assert "timed out" in _request_error_message(requests.exceptions.Timeout(), 30)
    assert "BACKEND_URL" in _request_error_message(requests.exceptions.ConnectionError(), 30)
    assert "TLS/SSL" in _request_error_message(requests.exceptions.SSLError(), 30)


def test_strict_groq_routes_structured_roles_to_configured_models(monkeypatch):
    monkeypatch.setattr(settings, "architect_model", "openai/gpt-oss-20b")
    monkeypatch.setattr(settings, "coder_model", "openai/gpt-oss-120b")
    monkeypatch.setattr(settings, "reviewer_model", "openai/gpt-oss-20b")
    monkeypatch.setattr(settings, "max_llm_output_tokens", 128)

    provider = StrictGroqLLMProvider(
        api_key="test-key",
        base_url="https://example.invalid/v1",
        model="openai/gpt-oss-120b",
    )

    observed: list[tuple[str, str]] = []

    def fake_generate(*, prompt, system_prompt=None, temperature=0.1, max_tokens=None, response_format=None, **kwargs):
        observed.append((provider.model, response_format["json_schema"]["name"]))
        schema_name = response_format["json_schema"]["name"]
        if schema_name == "architectureplan":
            return '{"summary":"s","project_type":"library","relevant_files":[],"suspected_issues":[],"dependencies":[],"test_strategy":"pytest","confidence":0.9}'
        if schema_name == "codechange":
            return '{"file_path":"a.py","change_type":"write","explanation":"e","root_cause":"r","patch":"x","confidence":0.9}'
        return '{"approved":true,"root_cause_fixed":true,"regression_risk":"low","issues":[],"reasoning":"ok","recommendation":"approve"}'

    with patch.object(provider, "generate", side_effect=fake_generate):
        provider.generate_structured(ArchitecturePlan, "architect")
        provider.generate_structured(CodeChange, "coder")
        provider.generate_structured(ReviewResult, "reviewer")

    assert observed == [
        ("openai/gpt-oss-20b", "architectureplan"),
        ("openai/gpt-oss-120b", "codechange"),
        ("openai/gpt-oss-20b", "reviewresult"),
    ]
    assert provider.model == "openai/gpt-oss-120b"
