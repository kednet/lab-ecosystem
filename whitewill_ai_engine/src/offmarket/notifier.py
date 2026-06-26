"""Telegram-нотификатор: шлёт алерты брокерам об off-market сигналах."""

import asyncio
import logging
from datetime import datetime

from ..shared.config import settings
from ..shared.models import OffMarketSignal

logger = logging.getLogger(__name__)


class TelegramNotifier:
    """Отправляет уведомления в Telegram о высокоприоритетных off-market объектах.

    В demo-режиме (нет токена) — логирует в консоль.
    """

    def __init__(self, token: str | None = None, chat_id: str | None = None) -> None:
        self.token = token or settings.telegram_bot_token
        self.chat_id = chat_id or settings.telegram_broker_chat_id
        self._bot = None

    async def _ensure_bot(self) -> None:
        """Lazy init Telegram-бота."""

        if self._bot is not None:
            return
        if not self.token:
            logger.warning("Telegram token not set, will log to console")
            return

        try:
            from telegram import Bot

            self._bot = Bot(token=self.token)
        except Exception as e:
            logger.exception(f"Failed to init Telegram bot: {e}")

    async def send_signal(self, signal: OffMarketSignal) -> bool:
        """Отправить алерт в Telegram."""

        text = self._format_signal(signal)

        if not self.token:
            # Demo-режим: пишем в лог
            logger.info(f"[DEMO TELEGRAM] {text}")
            return True

        await self._ensure_bot()
        if self._bot is None:
            return False

        try:
            await self._bot.send_message(
                chat_id=self.chat_id,
                text=text,
                parse_mode="HTML",
            )
            logger.info(f"Sent Telegram alert for {signal.cadastral_number}")
            return True
        except Exception as e:
            logger.exception(f"Telegram send error: {e}")
            return False

    def _format_signal(self, signal: OffMarketSignal) -> str:
        """Форматирование алерта."""

        priority_emoji = {"high": "🔴", "medium": "🟡", "low": "🟢"}.get(signal.priority, "⚪")

        text = (
            f"{priority_emoji} <b>Off-market сигнал: {signal.priority.upper()} (score {signal.score:.2f})</b>\n\n"
            f"📍 <b>Адрес:</b> {signal.address}\n"
            f"🏢 <b>Кадастровый:</b> <code>{signal.cadastral_number}</code>\n"
            f"💰 <b>Расчётная стоимость:</b> {signal.estimated_value_rub / 1_000_000:.0f} млн ₽\n\n"
            f"📊 <b>Сигналы:</b>\n"
        )

        for sig in signal.signals:
            text += f"  ✅ {sig}\n"

        text += "\n🎯 <b>Рекомендация:</b> связаться с собственником/нотариусом в течение 24 ч"

        return text


_notifier: TelegramNotifier | None = None


def get_notifier() -> TelegramNotifier:
    global _notifier
    if _notifier is None:
        _notifier = TelegramNotifier()
    return _notifier
