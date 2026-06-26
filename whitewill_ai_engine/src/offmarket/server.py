"""Крон-скрипт для off-market матчинга: сканирует кадастровые номера и шлёт алерты в Telegram."""

import asyncio
import logging
import sys
from datetime import datetime, timedelta

from ..shared.config import settings
from ..shared.db import init_db, get_session
from .notifier import get_notifier
from .scanner import get_scanner
from .scorer import get_scorer

logger = logging.getLogger(__name__)


async def run_scan() -> dict:
    """Запустить один цикл сканирования. Возвращает статистику."""

    started = datetime.utcnow()
    await init_db()

    scanner = get_scanner()
    scorer = get_scorer()
    notifier = get_notifier()

    logger.info("Starting off-market scan...")

    # 1. Получаем список кадастровых номеров (в demo — из mock-данных)
    cadastral_numbers = await scanner.get_watch_list()
    logger.info(f"Watch list: {len(cadastral_numbers)} cadastral numbers")

    # 2. Сканируем каждый
    new_signals = []
    async for session in get_session():
        for cn in cadastral_numbers:
            try:
                # Собираем сигналы из всех источников
                signals = await scanner.scan_one(cn)

                # Скорим
                scored = scorer.score(cn, signals)

                # Сохраняем в БД и шлём в Telegram (если high priority)
                if scored["score"] > 0:
                    from ..shared.models import OffMarketSignal

                    signal = OffMarketSignal(
                        cadastral_number=cn,
                        address=signals.get("address", ""),
                        district=signals.get("district", ""),
                        estimated_value_rub=signals.get("estimated_value_rub", 0),
                        egrn_change_type=signals.get("egrn_change_type", ""),
                        egrn_change_date=signals.get("egrn_change_date"),
                        has_encumbrance=signals.get("has_encumbrance", False),
                        encumbrance_type=signals.get("encumbrance_type", ""),
                        fssp_amount=signals.get("fssp_amount", 0),
                        has_inheritance=signals.get("has_inheritance", False),
                        is_bankruptcy=signals.get("is_bankruptcy", False),
                        score=scored["score"],
                        signals=scored["signals"],
                        priority=scored["priority"],
                        status="new",
                    )
                    session.add(signal)
                    new_signals.append(signal)

                    # Уведомляем в Telegram
                    if scored["priority"] in ("high", "medium"):
                        await notifier.send_signal(signal)

            except Exception as e:
                logger.exception(f"Scan error for {cn}: {e}")

        await session.commit()

    duration = (datetime.utcnow() - started).total_seconds()
    result = {
        "scanned": len(cadastral_numbers),
        "new_signals": len(new_signals),
        "high_priority": sum(1 for s in new_signals if s.priority == "high"),
        "duration_sec": round(duration, 2),
        "started_at": started.isoformat(),
    }

    logger.info(f"Scan complete: {result}")
    return result


def run() -> None:
    """Точка входа: запустить один цикл."""
    asyncio.run(run_scan())


if __name__ == "__main__":
    logging.basicConfig(
        level=settings.log_level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    run()
