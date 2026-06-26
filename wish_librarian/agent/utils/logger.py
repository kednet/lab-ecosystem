"""
Настройка логирования через loguru.

Логи пишутся одновременно:
  - в консоль (цветной вывод, с эмодзи-уровнями)
  - в файл logs/wish_librarian.log (с ротацией)
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Optional

from loguru import logger as _logger

from agent.config import get_settings


_configured = False


def setup_logging(level: Optional[str] = None) -> None:
    """Инициализировать логирование. Безопасно вызывать несколько раз."""
    global _configured
    if _configured:
        return

    settings = get_settings()
    log_level = (level or settings.log_level).upper()

    # Сброс дефолтного хэндлера
    _logger.remove()

    # ── Консоль ────────────────────────────────────────────────
    _logger.add(
        sys.stderr,
        level=log_level,
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

    # ── Файл (с ротацией по 10 МБ) ────────────────────────────
    logs_dir: Path = settings.logs_dir
    logs_dir.mkdir(parents=True, exist_ok=True)
    log_file = logs_dir / "wish_librarian.log"

    _logger.add(
        str(log_file),
        level="DEBUG",
        format=(
            "{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | "
            "{name}:{function}:{line} — {message}"
        ),
        rotation="10 MB",
        retention="14 days",
        compression="zip",
        encoding="utf-8",
        enqueue=True,  # потокобезопасно
        backtrace=True,
        diagnose=False,
    )

    _configured = True
    _logger.info("✅ Логирование инициализировано (уровень={})", log_level)


def get_logger():
    """Вернуть глобальный логгер loguru."""
    if not _configured:
        setup_logging()
    return _logger
