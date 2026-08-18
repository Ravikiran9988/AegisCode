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
        description="Model name for OpenAI-compatible provider (Groq)",
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
    # 6144 remains the safe completion ceiling after earlier GPT-OSS truncation failures.
    max_llm_output_tokens: int = 6144
    # Tighter input context reduces Groq latency while retaining enough repair context.
    max_file_context_size: int = 5000
    max_files_per_agent: int = 3
    llm_timeout_seconds: int = 60

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
        """Validate the required production Groq configuration."""
        errors = []
        provider_clean = self.llm_provider.lower()
        if provider_clean not in ("openai_compatible", "openai", "hosted"):
            errors.append(
                f"LLM_PROVIDER must be 'openai_compatible', got {self.llm_provider!r}"
            )

        base_clean = self.openai_base_url.rstrip("/")
        if base_clean != "https://api.groq.com/openai/v1":
            errors.append(
                f"OPENAI_BASE_URL must be 'https://api.groq.com/openai/v1', got {base_clean!r}"
            )

        if self.openai_model != "openai/gpt-oss-120b":
            errors.append(
                f"OPENAI_MODEL must be exactly 'openai/gpt-oss-120b', got {self.openai_model!r}"
            )

        if (
            not self.openai_api_key
            or self.openai_api_key == "your_openai_api_key_here"
            or "placeholder" in self.openai_api_key.lower()
        ):
            errors.append(
                "OPENAI_API_KEY is missing or invalid placeholder. "
                "A valid Groq API key is required."
            )

        if errors:
            err_str = "\n".join(f" - {e}" for e in errors)
            raise ValueError(f"Production LLM Configuration Errors:\n{err_str}")


settings = Settings()
