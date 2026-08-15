"""
Database initialisation — run once at startup.

Creates all tables if they don't already exist.
Safe to call repeatedly (idempotent).
"""

from __future__ import annotations

from backend.core.logging import get_logger
from backend.database.models import Base
from backend.database.session import engine

logger = get_logger(__name__)


def init_db() -> None:
    """Create all ORM tables. Call at FastAPI lifespan startup."""
    logger.info("Initialising database at %s", engine.url)
    Base.metadata.create_all(bind=engine)
    logger.info("Database tables ready")


if __name__ == "__main__":
    # Allow running directly:  python -m backend.database.init_db
    from backend.core.logging import setup_logging
    setup_logging()
    init_db()
