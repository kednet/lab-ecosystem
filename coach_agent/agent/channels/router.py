"""
ChannelRouter — регистрация и dispatch каналов.

Phase 1: только web. При добавлении TG/VK — register(TelegramAdapter()) и т.д.
"""

from __future__ import annotations

from typing import Any

from agent.channels.base import ChannelAdapter
from agent.channels.web import WebAdapter
from agent.core.message_bus import MessageBus
from agent.utils import get_logger

log = get_logger("channel_router")


class ChannelRouter:
    def __init__(self, message_bus: MessageBus) -> None:
        self._bus = message_bus
        self._adapters: dict[str, ChannelAdapter] = {}
        # По умолчанию — web
        self.register(WebAdapter())

    def register(self, adapter: ChannelAdapter) -> None:
        self._adapters[adapter.channel_name] = adapter
        log.info("channel.registered", name=adapter.channel_name)

    def get(self, channel: str) -> ChannelAdapter | None:
        return self._adapters.get(channel)

    async def handle(
        self, channel: str, raw: dict[str, Any]
    ) -> dict[str, Any]:
        adapter = self.get(channel)
        if adapter is None:
            return {"text": f"Канал '{channel}' не зарегистрирован.", "buttons": []}
        msg = adapter.normalize_inbound(raw)
        if msg is None:
            return {"text": "Не удалось разобрать сообщение.", "buttons": []}
        resp = await self._bus.dispatch(msg)
        return adapter.format_outbound(resp.text, resp.buttons)


__all__ = ["ChannelRouter"]
