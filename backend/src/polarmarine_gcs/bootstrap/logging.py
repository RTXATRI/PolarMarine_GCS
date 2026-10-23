from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler

from .settings import Settings


def configure_logging(settings: Settings) -> None:
    """Configure bounded console and UTF-8 file logging for the local service."""

    level = getattr(logging, settings.log_level.upper(), logging.INFO)
    formatter = logging.Formatter(
        "%(asctime)s %(levelname)s %(name)s %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S%z",
    )
    console = logging.StreamHandler()
    console.setFormatter(formatter)
    settings.resolved_log_dir.mkdir(parents=True, exist_ok=True)
    file_handler = RotatingFileHandler(
        settings.resolved_log_dir / "polarmarine-gcs.log",
        maxBytes=settings.log_max_bytes,
        backupCount=settings.log_backup_count,
        encoding="utf-8",
    )
    file_handler.setFormatter(formatter)
    logging.basicConfig(level=level, handlers=[console, file_handler], force=True)
    for logger_name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        logger = logging.getLogger(logger_name)
        logger.handlers.clear()
        logger.propagate = True
        logger.setLevel(level)
