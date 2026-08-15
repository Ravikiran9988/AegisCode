"""
/health  – liveness + readiness probe.

Returns application version, current UTC timestamp, and database
connectivity status so infrastructure (and the Streamlit frontend) can
confirm all three tiers are up.
"""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.orm import Session

from backend.core.config import settings
from backend.database.session import get_db

router = APIRouter(tags=["health"])


class HealthResponse(BaseModel):
    status: str
    app_name: str
    version: str
    timestamp: str
    database: str
    llm_provider: str


@router.get("/health", response_model=HealthResponse, summary="Health check")
def health_check(db: Session = Depends(get_db)) -> HealthResponse:
    """
    Liveness and readiness probe.

    - **status**: ``ok`` when all subsystems are healthy.
    - **database**: ``connected`` or an error message.
    """
    db_status = "connected"
    try:
        db.execute(text("SELECT 1"))
    except Exception as exc:  # noqa: BLE001
        db_status = f"error: {exc}"

    overall = "ok" if db_status == "connected" else "degraded"

    return HealthResponse(
        status=overall,
        app_name=settings.app_name,
        version=settings.app_version,
        timestamp=datetime.now(timezone.utc).isoformat(),
        database=db_status,
        llm_provider=settings.llm_provider,
    )
