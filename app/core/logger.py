"""
Centralized logging configuration using loguru.

Two formats are available:
  - human  (default): coloured single-line text for terminals
  - json:             one JSON object per line for log shippers

Pick via LOG_FORMAT=json in the environment.
"""
import os
import sys
from pathlib import Path

from loguru import logger

from app.core.config import settings


_LOG_DIR = Path("logs")
_FORMAT = os.environ.get("LOG_FORMAT", "human").lower()


_HUMAN_FMT = (
    "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
    "<level>{level: <8}</level> | "
    "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - "
    "<level>{message}</level>"
)
_PLAIN_FMT = (
    "{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | "
    "{name}:{function}:{line} - {message}"
)


def setup_logging():
    """Configure application logging."""
    _LOG_DIR.mkdir(parents=True, exist_ok=True)

    # Remove default logger
    logger.remove()

    json_mode = _FORMAT == "json"

    # Console
    if json_mode:
        logger.add(sys.stdout, serialize=True, level=settings.log_level)
    else:
        logger.add(
            sys.stdout,
            format=_HUMAN_FMT,
            level=settings.log_level,
            colorize=True,
        )

    # Daily rotating file (all levels)
    logger.add(
        str(_LOG_DIR / "app_{time:YYYY-MM-DD}.log"),
        rotation="00:00",
        retention="30 days",
        compression="zip",
        format=_PLAIN_FMT,
        level=settings.log_level,
        serialize=json_mode,
        enqueue=True,
    )

    # Error-only file (longer retention for incident review)
    logger.add(
        str(_LOG_DIR / "error_{time:YYYY-MM-DD}.log"),
        rotation="00:00",
        retention="90 days",
        compression="zip",
        format=_PLAIN_FMT,
        level="ERROR",
        serialize=json_mode,
        enqueue=True,
    )

    return logger


# Initialize logger
app_logger = setup_logging()
