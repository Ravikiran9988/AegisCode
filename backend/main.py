"""FastAPI application factory."""
from __future__ import annotations
import logging, os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from backend.api.auth import auth_router
from backend.api.guest_run_access import GuestRunAccessMiddleware
from backend.api.guests import router as guests_router
from backend.api.health import router as health_router
from backend.api.projects import router as projects_router
from backend.api.runs import router as runs_router
from backend.core.config import settings
from backend.core.logging import setup_logging
from backend.database.init_db import init_db
logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    setup_logging(); logger.info("Starting %s v%s", settings.app_name, settings.app_version)
    production = os.environ.get("ENV", "").lower() in {"production", "prod"} or os.environ.get("ENVIRONMENT", "").lower() in {"production", "prod"}
    if production or os.environ.get("STRICT_LLM_VALIDATION") == "true" or (not settings.debug and settings.openai_api_key != "your_openai_api_key_here"):
        settings.validate_production_llm_config()
        logger.info("Production Groq LLM config validated successfully (model=%s)", settings.openai_model)
    if production:
        if settings.execution_backend != "docker":
            raise RuntimeError("Production execution_backend must be 'docker'. Uploaded projects must never execute on the host.")
        from backend.execution.docker import DockerExecutionBackend
        DockerExecutionBackend()
        logger.info("Production Docker sandbox validated successfully")
    init_db(); logger.info("Application ready")
    yield
    logger.info("Shutting down %s", settings.app_name)

def create_app() -> FastAPI:
    app = FastAPI(title=settings.app_name, version=settings.app_version, description="AegisCode — Self-Healing Multi-Agent Software Engineering System. Upload a broken Python project and watch autonomous agents repair it.", lifespan=lifespan, docs_url="/docs", redoc_url="/redoc")
    origins = [o.strip() for o in settings.cors_origins.split(",") if o.strip()] or ["http://localhost:8501", "http://127.0.0.1:8501"]
    app.add_middleware(GuestRunAccessMiddleware)
    app.add_middleware(CORSMiddleware, allow_origins=origins, allow_credentials=True, allow_methods=["GET", "POST", "OPTIONS"], allow_headers=["*"])
    app.include_router(health_router)
    app.include_router(auth_router, prefix="/api/auth", tags=["auth"])
    app.include_router(auth_router, prefix="/auth", tags=["auth-alias"], include_in_schema=False)
    app.include_router(guests_router); app.include_router(projects_router); app.include_router(runs_router)
    return app
app = create_app()
