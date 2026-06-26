"""
MessageBus — единая точка входа для каналов.

Phase 1: только web. Telegram/VK зарезервированы под Phase 6/7.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from agent.core.session import CoachResponse, SessionService
from agent.storage.repository import Repository
from agent.utils import get_logger

log = get_logger("message_bus")


@dataclass
class NormalizedMessage:
    """Нормализованное сообщение из любого канала."""

    client_id: int
    text: str
    channel: str
    raw: dict[str, Any]


class MessageBus:
    def __init__(self, session_service: SessionService, repository: Repository) -> None:
        self._session = session_service
        self._repo = repository

    async def dispatch(self, msg: NormalizedMessage) -> CoachResponse:
        log.info(
            "bus.dispatch",
            channel=msg.channel,
            client_id=msg.client_id,
            text_len=len(msg.text),
        )
        client = await self._repo.get_client_by_id(msg.client_id)
        if client is None:
            # Создаём минимального клиента (Phase 1: без авторизации,
            # real auth будет в lab_site через magic-link)
            client = await self._repo.upsert_client(
                email=f"client_{msg.client_id}@local",
                name=None,
            )
        return await self._session.process_message(
            client=client, text=msg.text, channel=msg.channel
        )


__all__ = ["MessageBus", "NormalizedMessage"]
