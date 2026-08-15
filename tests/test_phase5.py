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
        assert provider.provider_name == "openai_compatible"

    def test_groq_production_model_configuration(self):
        provider = OpenAICompatibleLLMProvider(
            api_key="gsk-test-key",
            base_url="https://api.groq.com/openai/v1",
            model="openai/gpt-oss-120b",
        )
        assert provider.model_name == "openai/gpt-oss-120b"
        assert provider.provider_name == "openai_compatible"
        assert provider.base_url == "https://api.groq.com/openai/v1"

    def test_factory_unknown_provider_raises_value_error(self):
        with pytest.raises(ValueError, match="Unsupported LLM provider"):
            get_llm_provider(provider_name="unknown_unsupported_llm")

    def test_production_startup_validation_passes_valid_config(self):
        with patch.object(settings, "llm_provider", "openai_compatible"), \
             patch.object(settings, "openai_base_url", "https://api.groq.com/openai/v1"), \
             patch.object(settings, "openai_model", "openai/gpt-oss-120b"), \
             patch.object(settings, "openai_api_key", "gsk_real_key_123"):
            settings.validate_production_llm_config()

    def test_production_startup_validation_fails_invalid_model(self):
        with patch.object(settings, "llm_provider", "openai_compatible"), \
             patch.object(settings, "openai_base_url", "https://api.groq.com/openai/v1"), \
             patch.object(settings, "openai_model", "wrong-model"), \
             patch.object(settings, "openai_api_key", "gsk_real_key_123"):
            with pytest.raises(
                ValueError, match="OPENAI_MODEL must be exactly 'openai/gpt-oss-120b'"
            ):
                settings.validate_production_llm_config()

    def test_production_startup_validation_fails_missing_key(self):
        with patch.object(settings, "llm_provider", "openai_compatible"), \
             patch.object(settings, "openai_base_url", "https://api.groq.com/openai/v1"), \
             patch.object(settings, "openai_model", "openai/gpt-oss-120b"), \
             patch.object(settings, "openai_api_key", "your_openai_api_key_here"):
            with pytest.raises(
                ValueError, match="OPENAI_API_KEY is missing or invalid placeholder"
            ):
                settings.validate_production_llm_config()

    def test_all_agents_use_same_groq_provider(self):
        from backend.agents.architect import ArchitectAgent
        from backend.agents.coder import CoderAgent
        from backend.agents.reviewer import ReviewerAgent

        provider = OpenAICompatibleLLMProvider(
            api_key="gsk-test-key",
            base_url="https://api.groq.com/openai/v1",
            model="openai/gpt-oss-120b",
        )
        arch = ArchitectAgent(provider)
        coder = CoderAgent(provider)
        rev = ReviewerAgent(provider)

        assert arch.llm.model_name == "openai/gpt-oss-120b"
        assert coder.llm.model_name == "openai/gpt-oss-120b"
        assert rev.llm.model_name == "openai/gpt-oss-120b"

    def test_api_key_never_leaked_in_health_response(self, api_client):
        resp = api_client.get("/health")
        assert resp.status_code == 200
        text = resp.text
        assert "sk-test-key" not in text
        assert "gsk_" not in text

    @patch("requests.post")
    def test_openai_generate(self, mock_post):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "choices": [{"message": {"content": "Hello from Groq"}}]
        }
        mock_post.return_value = mock_response

        provider = OpenAICompatibleLLMProvider(api_key="gsk-test-key")
        result = provider.generate("Test prompt")
        assert result == "Hello from Groq"

    @patch("requests.get")
    def test_openai_is_available(self, mock_get):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_get.return_value = mock_response

        provider = OpenAICompatibleLLMProvider(api_key="gsk-test-key")
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
