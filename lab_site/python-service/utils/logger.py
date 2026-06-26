"""
Лёгкий логгер для python-service (без зависимости от WL agent.config).
Использует loguru напрямую с минимумом настроек.
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Optional

from loguru import logger as _logger

_configured = False


def setup_logging(level: str = "INFO", logs_dir: Optional[Path] = None) -> None:
    """Инициализировать логирование. Безопасно вызывать несколько раз."""
    global _configured
    if _configured:
        return

    _logger.remove()

    # ── Консоль ────────────────────────────────────────────────
    _logger.add(
        sys.stderr,
        level=level.upper(),
        format=(
            "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
            "<level>{level: <8}</level> | "
            "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> — "
            "<level>{message}</level>"
        ),
        colorize=True,
        backtrace=True,
        diagnose=False,
    )

    # ── Файл (опционально) ─────────────────────────────────────
    if logs_dir:
        logs_dir = Path(logs_dir)
        logs_dir.mkdir(parents=True, exist_ok=True)
        log_file = logs_dir / "publisher.log"
        _logger.add(
            str(log_file),
            level="DEBUG",
            format=(
                "{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | "
                "{name}:{function}:{line} — {message}"
            ),
            rotation="10 MB",
            retention="14 days",
            encoding="utf-8",
            enqueue=True,
            backtrace=True,
            diagnose=False,
        )

    _configured = True
    _logger.info("✅ Publisher logging initialized (level={})", level)


def get_logger():
    """Вернуть глобальный логгер loguru."""
    if not _configured:
        setup_logging()
    return _logger
