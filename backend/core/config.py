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

    # ------------------------------------------------------------------ #
    # Application
    # ------------------------------------------------------------------ #
    app_name: str = "AegisCode"
    app_version: str = "0.1.0"
    debug: bool = False
    log_level: str = "INFO"

    # ------------------------------------------------------------------ #
    # API server
    # ------------------------------------------------------------------ #
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    api_prefix: str = "/api"

    # ------------------------------------------------------------------ #
    # Database
    # ------------------------------------------------------------------ #
    database_url: str = Field(
        default="sqlite:///./aegiscode.db",
        description="SQLAlchemy database URL (sqlite:///... or postgresql+psycopg://...)",
    )

    # ------------------------------------------------------------------ #
    # LLM provider
    # ------------------------------------------------------------------ #
    llm_provider: str = Field(
        default="ollama",
        description="LLM provider: 'ollama', 'openai_compatible', or 'mock'",
    )
    ollama_base_url: str = Field(
        default="http://localhost:11434",
        description="Base URL for local Ollama instance",
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
        default="https://api.openai.com/v1",
        description="Base URL for OpenAI-compatible REST endpoint",
    )
    openai_model: str = Field(
        default="gpt-4o-mini",
        description="Model name for OpenAI-compatible provider",
    )
    anthropic_api_key: str = ""
    anthropic_model: str = "claude-3-5-sonnet-20241022"

    # ------------------------------------------------------------------ #
    # Security & Network
    # ------------------------------------------------------------------ #
    cors_origins: str = Field(
        default="http://localhost:8501,http://localhost:3000,http://127.0.0.1:8501",
        description="Comma-separated list of allowed CORS origin URLs",
    )

    # LLM context & output bounds
    max_agent_iterations: int = 5
    max_llm_output_tokens: int = 4096
    max_file_context_size: int = 16000
    max_files_per_agent: int = 10
    llm_timeout_seconds: int = 60

    # ------------------------------------------------------------------ #
    # Execution / Sandbox
    # ------------------------------------------------------------------ #
    workspace_base_dir: str = "./workspaces"
    max_iterations: int = 5
    execution_timeout_seconds: int = 120
    pytest_timeout_seconds: int = 60
    use_docker_sandbox: bool = False
    docker_image: str = "python:3.11-slim"
    execution_backend: Literal["local", "docker"] = "local"

    # ------------------------------------------------------------------ #
    # Upload / File limits
    # ------------------------------------------------------------------ #
    max_upload_size_mb: int = 50
    max_file_size_mb: int = 5
    max_output_size_mb: int = 10
    max_workspace_files: int = 500

    # ------------------------------------------------------------------ #
    # Derived helpers
    # ------------------------------------------------------------------ #
    @property
    def workspace_path(self) -> Path:
        return Path(self.workspace_base_dir).resolve()

    @property
    def is_debug(self) -> bool:
        return self.debug


# Module-level singleton — import this everywhere
settings = Settings()
