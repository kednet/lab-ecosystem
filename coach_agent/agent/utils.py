"""
Структурированный логгер на structlog.

Phase 0: вывод в stdout JSON-строками (для Render logs) + читаемый dev-режим.
"""

from __future__ import annotations

import logging
import sys

import structlog

from agent.config import settings


def setup_logging() -> None:
    """Инициализация structlog. Вызывается в lifespan FastAPI."""
    level = getattr(logging, settings.log_level)

    # На Windows stdout по умолчанию cp1252 — переключаем на utf-8,
    # иначе structlog упадёт при попытке писать кириллицу.
    try:
        sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
    except (AttributeError, OSError):
        pass

    # Общий logging (для uvicorn, httpx и пр.)
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=level,
    )

    # structlog
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.dev.set_exc_info,
            (
                structlog.dev.ConsoleRenderer(colors=False)
                if settings.app_env == "development"
                else structlog.processors.JSONRenderer()
            ),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(level),
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str = "wishcoach") -> structlog.stdlib.BoundLogger:
    return structlog.get_logger(name)


__all__ = ["setup_logging", "get_logger"]
