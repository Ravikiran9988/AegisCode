"""
Phase 5 Tests — Production Hardening, OpenAI Provider, Database & Deployment.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from backend.core.config import settings
from backend.database.session import _create_db_engine
from backend.execution.docker import DockerExecutionBackend
from backend.llm.factory import get_llm_provider
from backend.llm.openai import OpenAICompatibleLLMProvider
from backend.main import create_app

# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture()
def api_client():
    app = create_app()
    with TestClient(app) as client:
        yield client


# ══════════════════════════════════════════════════════════════════════════════
# 1. OPENAI-COMPATIBLE PROVIDER TESTS
# ══════════════════════════════════════════════════════════════════════════════

class TestOpenAIProvider:
    def test_factory_instantiates_openai_provider(self):
        provider = get_llm_provider(provider_type="openai_compatible")
        assert isinstance(provider, OpenAICompatibleLLMProvider)

    def test_openai_provider_model_configuration(self):
        provider = OpenAICompatibleLLMProvider(
            api_key="sk-test-key",
            base_url="https://api.groq.com/openai/v1",
            model="openai/gpt-oss-120b",
        )
        assert provider.model_name == "openai/gpt-oss-120b"
        assert provider.provider_name == "openai_compatible"
        assert provider.base_url == "https://api.groq.com/openai/v1"

    @patch("requests.post")
    def test_openai_generate(self, mock_post):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "choices": [{"message": {"content": "Hello from OpenAI"}}]
        }
        mock_post.return_value = mock_response

        provider = OpenAICompatibleLLMProvider(api_key="sk-test-key")
        result = provider.generate("Test prompt")
        assert result == "Hello from OpenAI"

    @patch("requests.get")
    def test_openai_is_available(self, mock_get):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_get.return_value = mock_response

        provider = OpenAICompatibleLLMProvider(api_key="sk-test-key")
        avail, msg = provider.is_available()
        assert avail is True
        assert "reachable" in msg


# ══════════════════════════════════════════════════════════════════════════════
# 2. DATABASE & CONFIGURATION TESTS
# ══════════════════════════════════════════════════════════════════════════════

class TestDatabaseAndConfig:
    def test_sqlite_engine_creation(self):
        with patch.object(settings, "database_url", "sqlite:///./test.db"):
            eng = _create_db_engine()
            assert eng.name == "sqlite"

    def test_cors_origins_parsing(self, api_client):
        response = api_client.options(
            "/health",
            headers={
                "Origin": "http://localhost:8501",
                "Access-Control-Request-Method": "GET",
            },
        )
        assert response.status_code == 200
        assert "access-control-allow-origin" in response.headers


# ══════════════════════════════════════════════════════════════════════════════
# 3. DOCKER EXECUTION BACKEND SAFETY
# ══════════════════════════════════════════════════════════════════════════════

class TestDockerBackendSafety:
    def test_docker_backend_configuration(self):
        try:
            backend = DockerExecutionBackend(image="python:3.11-slim")
            assert backend.image == "python:3.11-slim"
        except Exception as exc:
            assert "Docker" in str(exc) or "PATH" in str(exc)

    def test_docker_is_available_graceful_check(self):
        try:
            backend = DockerExecutionBackend()
            avail, msg = backend.is_available()
            assert isinstance(avail, bool)
            assert isinstance(msg, str)
        except Exception as exc:
            assert "Docker" in str(exc) or "PATH" in str(exc)


# ══════════════════════════════════════════════════════════════════════════════
# 4. DEPLOYMENT & ENVIRONMENT FILE INTEGRITY
# ══════════════════════════════════════════════════════════════════════════════

class TestDeploymentIntegrity:
    def test_env_example_exists_and_contains_placeholders(self):
        env_example = Path(__file__).parent.parent / ".env.example"
        assert env_example.exists()
        content = env_example.read_text(encoding="utf-8")

        assert "DATABASE_URL=" in content
        assert "LLM_PROVIDER=" in content
        assert "OPENAI_API_KEY=" in content
        assert "CORS_ORIGINS=" in content
