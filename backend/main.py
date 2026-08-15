"""
FastAPI application factory.

All API routers are registered here.
Later phases will add /projects, /runs, etc.
"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Import routers
from backend.api.health import router as health_router
from backend.api.projects import router as projects_router
from backend.api.runs import router as runs_router
from backend.core.config import settings
from backend.core.logging import setup_logging
from backend.database.init_db import init_db

logger = logging.getLogger(__name__)


# ── Lifespan ──────────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Startup / shutdown hooks."""
    setup_logging()
    logger.info("Starting %s v%s", settings.app_name, settings.app_version)
    init_db()
    logger.info("Application ready")
    yield
    logger.info("Shutting down %s", settings.app_name)


# ── App factory ───────────────────────────────────────────────────────────────

def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description=(
            "AegisCode — Self-Healing Multi-Agent Software Engineering System. "
            "Upload a broken Python project and watch autonomous agents repair it."
        ),
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url="/redoc",
    )

    # ── CORS configuration ───────────────────────────────────────────────────
    origins = [o.strip() for o in settings.cors_origins.split(",") if o.strip()]
    if not origins:
        origins = ["http://localhost:8501", "http://127.0.0.1:8501"]

    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["*"],
    )

    # ── Routers ───────────────────────────────────────────────────────────────
    app.include_router(health_router)
    app.include_router(projects_router)
    app.include_router(runs_router)

    return app


app = create_app()
