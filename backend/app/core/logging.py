from __future__ import annotations

import logging
import sys

import structlog

from backend.app.core.config import get_settings


def configure_logging() -> None:
    settings = get_settings()
    timestamper = structlog.processors.TimeStamper(fmt="iso", utc=True)
    shared_processors = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        timestamper,
    ]

    structlog.configure(
        processors=shared_processors
        + [
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer() if settings.log_json else structlog.dev.ConsoleRenderer(),
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    logging.basicConfig(
        format="%(message)s",
        level=getattr(logging, settings.log_level.upper(), logging.INFO),
        stream=sys.stdout,
        force=True,
    )


def get_logger(name: str | None = None) -> structlog.stdlib.BoundLogger:
    return structlog.get_logger(name)
