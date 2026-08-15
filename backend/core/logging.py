"""
Structured logging configuration for AegisCode.

Call `setup_logging()` once at application startup.
Everywhere else just use `logging.getLogger(__name__)`.
"""

from __future__ import annotations

import logging
import sys

from backend.core.config import settings


def setup_logging(level: str | None = None) -> None:
    """Configure root logger with a consistent format."""
    log_level = (level or settings.log_level).upper()

    fmt = (
        "%(asctime)s | %(levelname)-8s | %(name)s:%(lineno)d | %(message)s"
    )
    date_fmt = "%Y-%m-%d %H:%M:%S"

    logging.basicConfig(
        level=log_level,
        format=fmt,
        datefmt=date_fmt,
        handlers=[logging.StreamHandler(sys.stdout)],
        force=True,
    )

    # Silence overly chatty third-party libs
    for noisy in ("httpx", "httpcore", "uvicorn.access"):
        logging.getLogger(noisy).setLevel(logging.WARNING)

    logging.getLogger(__name__).info(
        "Logging initialised at level=%s", log_level
    )


def get_logger(name: str) -> logging.Logger:
    """Convenience wrapper — identical to logging.getLogger but importable from one place."""
    return logging.getLogger(name)
