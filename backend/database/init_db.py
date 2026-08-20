"""Database initialisation and safe backward-compatible migrations."""
from __future__ import annotations

from sqlalchemy import inspect, text

from backend.core.logging import get_logger
from backend.database.guest import Guest  # noqa: F401
from backend.database.models import Base
from backend.database.session import engine

logger = get_logger(__name__)


def _add_column_if_missing(conn, table: str, column: str, ddl: str, inspector) -> None:
    cols = [c["name"] for c in inspector.get_columns(table)]
    if column not in cols:
        logger.info("Adding %s.%s", table, column)
        conn.execute(text(ddl))


def init_db() -> None:
    logger.info("Initialising database schema at %s", engine.url)
    Base.metadata.create_all(bind=engine)
    inspector = inspect(engine)
    tables = inspector.get_table_names()

    with engine.begin() as conn:
        if "projects" in tables:
            _add_column_if_missing(
                conn, "projects", "user_id", "ALTER TABLE projects ADD COLUMN user_id VARCHAR(255)", inspector
            )
            _add_column_if_missing(
                conn, "projects", "guest_id", "ALTER TABLE projects ADD COLUMN guest_id VARCHAR(36)", inspector
            )
        if "runs" in tables:
            _add_column_if_missing(
                conn, "runs", "user_id", "ALTER TABLE runs ADD COLUMN user_id VARCHAR(255)", inspector
            )
            _add_column_if_missing(
                conn, "runs", "guest_id", "ALTER TABLE runs ADD COLUMN guest_id VARCHAR(36)", inspector
            )
        if "users" in tables:
            for column, ddl in (
                ("name", "ALTER TABLE users ADD COLUMN name VARCHAR(255) DEFAULT ''"),
                ("full_name", "ALTER TABLE users ADD COLUMN full_name VARCHAR(255) DEFAULT ''"),
                ("is_active", "ALTER TABLE users ADD COLUMN is_active BOOLEAN DEFAULT TRUE"),
                ("is_superuser", "ALTER TABLE users ADD COLUMN is_superuser BOOLEAN DEFAULT FALSE"),
            ):
                _add_column_if_missing(conn, "users", column, ddl, inspector)

    logger.info("Database tables ready")


if __name__ == "__main__":
    from backend.core.logging import setup_logging
    setup_logging()
    init_db()
