"""
Database initialisation — run once at startup.

Creates all tables if they don't already exist and applies safe migrations.
Safe to call repeatedly (idempotent).
"""

from __future__ import annotations

from sqlalchemy import inspect, text

from backend.core.logging import get_logger
from backend.database.models import Base
from backend.database.session import engine

logger = get_logger(__name__)


def init_db() -> None:
    """Create all ORM tables and apply safe backward-compatible schema migrations."""
    logger.info("Initialising database schema at %s", engine.url)
    Base.metadata.create_all(bind=engine)

    try:
        inspector = inspect(engine)
        tables = inspector.get_table_names()

        with engine.begin() as conn:
            # 1. Ensure projects table has user_id
            if "projects" in tables:
                proj_cols = [c["name"] for c in inspector.get_columns("projects")]
                if "user_id" not in proj_cols:
                    logger.info("Adding user_id column to projects table")
                    conn.execute(text("ALTER TABLE projects ADD COLUMN user_id VARCHAR(255)"))

            # 2. Ensure runs table has user_id
            if "runs" in tables:
                run_cols = [c["name"] for c in inspector.get_columns("runs")]
                if "user_id" not in run_cols:
                    logger.info("Adding user_id column to runs table")
                    conn.execute(text("ALTER TABLE runs ADD COLUMN user_id VARCHAR(255)"))

            # 3. Ensure users table exists with standard columns
            if "users" in tables:
                user_cols = [c["name"] for c in inspector.get_columns("users")]
                if "name" not in user_cols:
                    logger.info("Adding name column to users table")
                    conn.execute(
                        text("ALTER TABLE users ADD COLUMN name VARCHAR(255) DEFAULT ''")
                    )
                if "is_active" not in user_cols:
                    conn.execute(
                        text("ALTER TABLE users ADD COLUMN is_active BOOLEAN DEFAULT TRUE")
                    )
                if "is_superuser" not in user_cols:
                    conn.execute(
                        text("ALTER TABLE users ADD COLUMN is_superuser BOOLEAN DEFAULT FALSE")
                    )
    except Exception as exc:
        logger.warning("Database schema migration notice: %s", exc)

    logger.info("Database tables ready")


if __name__ == "__main__":
    # Allow running directly:  python -m backend.database.init_db
    from backend.core.logging import setup_logging
    setup_logging()
    init_db()
