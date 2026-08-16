"""
Database engine and session factory.

Usage
-----
    from backend.database.session import get_db

    # FastAPI dependency
    def some_endpoint(db: Session = Depends(get_db)):
        ...

    # Or as context manager
    with get_db() as db:
        ...
"""

from __future__ import annotations

from collections.abc import Generator
from contextlib import contextmanager

from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from backend.core.config import settings
from backend.core.logging import get_logger

logger = get_logger(__name__)

# ── Engine ────────────────────────────────────────────────────────────────────

def _normalise_db_url(url: str) -> str:
    """
    Render.com / cloud hosts provide DATABASE_URL as 'postgres://' or 'postgresql://'.
    SQLAlchemy 2.x requires an explicit driver. We use psycopg2-binary, so
    rewrite bare 'postgresql://' or 'postgres://' to 'postgresql+psycopg2://'.
    Leave sqlite:// and already-qualified URLs untouched.
    """
    if url.startswith("postgres://"):
        return url.replace("postgres://", "postgresql+psycopg2://", 1)
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+psycopg2://", 1)
    return url


def _create_db_engine():
    db_url = _normalise_db_url(settings.database_url)
    if db_url.startswith("sqlite"):
        engine_args: dict = {"connect_args": {"check_same_thread": False}}
    else:
        # PostgreSQL / Production DB
        engine_args = {
            "pool_pre_ping": True,
            "pool_size": 10,
            "max_overflow": 20,
        }
    return create_engine(db_url, **engine_args, echo=settings.debug)


engine = _create_db_engine()

# Enable WAL mode for SQLite so reads don't block writes
if _normalise_db_url(settings.database_url).startswith("sqlite"):
    @event.listens_for(engine, "connect")
    def _set_sqlite_pragma(dbapi_conn, _connection_record):  # noqa: ANN001
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

# ── Session factory ───────────────────────────────────────────────────────────

SessionLocal = sessionmaker(
    bind=engine,
    autocommit=False,
    autoflush=False,
    expire_on_commit=False,
)


# ── FastAPI dependency ────────────────────────────────────────────────────────

def get_db() -> Generator[Session, None, None]:
    """
    FastAPI dependency that provides a database session per request.

    Closes the session cleanly and rolls back on unhandled exceptions.
    """
    db = SessionLocal()
    try:
        yield db
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


# ── Context manager (non-FastAPI code) ───────────────────────────────────────

@contextmanager
def db_session() -> Generator[Session, None, None]:
    """Context-manager version for use outside FastAPI request handlers."""
    db = SessionLocal()
    try:
        yield db
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
