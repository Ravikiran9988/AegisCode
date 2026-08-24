"""
AegisCode – centralised configuration.

All settings are read from environment variables (or a .env file).
Import the singleton `settings` object everywhere; do not use os.getenv() directly.
"""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Application
    app_name: str = "AegisCode"
    app_version: str = "0.1.0"
    debug: bool = False
    log_level: str = "INFO"

    # API server
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    api_prefix: str = "/api"

    # Database
    database_url: str = Field(
        default="sqlite:///./aegiscode.db",
        description="SQLAlchemy database URL (sqlite:///... or postgresql+psycopg://...)",
    )

    # LLM provider
    llm_provider: str = Field(
        default="openai_compatible",
        description="LLM provider: 'openai_compatible', 'ollama', or 'mock'",
    )
    ollama_base_url: str = Field(
        default="http://localhost:11434",
        description="Base URL for local Ollama instance (development only)",
    )
    ollama_model: str = Field(
        default="qwen2.5-coder:7b",
        description="Model tag to run on Ollama",
    )
    openai_api_key: str = Field(
        default="your_openai_api_key_here",
        description="API key for OpenAI-compatible hosted provider",
    )
    openai_base_url: str = Field(
        default="https://api.groq.com/openai/v1",
        description="Base URL for OpenAI-compatible REST endpoint (Groq)",
    )
    openai_model: str = Field(
        default="openai/gpt-oss-120b",
        description="Default model name for the OpenAI-compatible provider",
    )
    architect_model: str = Field(
        default="",
        description="Optional model override for Architect Agent (defaults to openai_model)",
    )
    coder_model: str = Field(
        default="",
        description="Optional model override for Coder Agent (defaults to openai_model)",
    )
    reviewer_model: str = Field(
        default="",
        description="Optional model override for Reviewer Agent (defaults to openai_model)",
    )
    targeted_testing_enabled: bool = Field(
        default=True,
        description="Run targeted failing test files first before full test suite",
    )
    anthropic_api_key: str = ""
    anthropic_model: str = "claude-3-5-sonnet-20241022"

    # Security & network
    cors_origins: str = Field(
        default="http://localhost:8501,http://localhost:3000,http://127.0.0.1:8501",
        description="Comma-separated list of allowed CORS origin URLs",
    )

    # LLM context & output bounds
    max_agent_iterations: int = 5
    max_llm_output_tokens: int = 4096
    architect_max_tokens: int = 1600
    coder_max_tokens: int = 2400
    reviewer_max_tokens: int = 600
    max_file_context_size: int = 5000
    max_files_per_agent: int = 3
    llm_timeout_seconds: int = 60

    # Rate-limit policy: fail fast instead of spending minutes sleeping through
    # repeated 429s. A single short retry handles transient TPM/RPM throttling;
    # daily TPD exhaustion is detected separately and never retried.
    llm_rate_limit_retries: int = 1
    llm_rate_limit_max_wait_seconds: int = 30

    # Execution / Sandbox
    workspace_base_dir: str = "./workspaces"
    max_iterations: int = 5
    execution_timeout_seconds: int = 120
    pytest_timeout_seconds: int = 60
    use_docker_sandbox: bool = False
    docker_image: str = "python:3.11-slim"
    execution_backend: Literal["local", "docker"] = "local"

    # Upload / File limits
    max_upload_size_mb: int = 50
    max_file_size_mb: int = 5
    max_output_size_mb: int = 10
    max_workspace_files: int = 500

    @property
    def workspace_path(self) -> Path:
        return Path(self.workspace_base_dir).resolve()

    @property
    def is_debug(self) -> bool:
        return self.debug

    def validate_production_llm_config(self) -> None:
        """Validate production hosted-provider configuration without pinning a model."""
        errors = []
        provider_clean = self.llm_provider.lower()
        if provider_clean not in ("openai_compatible", "openai", "hosted"):
            errors.append(
                f"LLM_PROVIDER must be 'openai_compatible', got {self.llm_provider!r}"
            )

        base_clean = self.openai_base_url.rstrip("/")
        if not base_clean:
            errors.append("OPENAI_BASE_URL must not be empty")

        if not self.openai_model.strip():
            errors.append("OPENAI_MODEL must not be empty")

        if (
            not self.openai_api_key
            or self.openai_api_key == "your_openai_api_key_here"
            or "placeholder" in self.openai_api_key.lower()
        ):
            errors.append(
                "OPENAI_API_KEY is missing or invalid placeholder. "
                "A valid hosted-provider API key is required."
            )

        for field_name, model_name in (
            ("ARCHITECT_MODEL", self.architect_model),
            ("CODER_MODEL", self.coder_model),
            ("REVIEWER_MODEL", self.reviewer_model),
        ):
            if model_name and not model_name.strip():
                errors.append(f"{field_name} must be empty or a non-empty model ID")

        if errors:
            err_str = "\n".join(f" - {e}" for e in errors)
            raise ValueError(f"Production LLM Configuration Errors:\n{err_str}")


settings = Settings()
