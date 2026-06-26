"""
Web-канал: HTTP request/response.

Phase 1: синхронный HTTP. SSE-стриминг — в будущем.
"""

from __future__ import annotations

from typing import Any

from agent.channels.base import ChannelAdapter
from agent.core.message_bus import NormalizedMessage


class WebAdapter(ChannelAdapter):
    channel_name = "web"

    def normalize_inbound(self, raw: dict[str, Any]) -> NormalizedMessage | None:
        """
        Принимает {"client_id": int, "text": str, "channel_meta": dict (опц.)}
        или {"text": str} + заголовок X-Client-Id (обрабатывается в deps.py).
        """
        if not raw:
            return None
        text = raw.get("text")
        client_id = raw.get("client_id")
        if not text or client_id is None:
            return None
        return NormalizedMessage(
            client_id=int(client_id),
            text=str(text),
            channel="web",
            raw=raw,
        )

    def format_outbound(self, response_text: str, buttons: list[dict]) -> dict[str, Any]:
        return {
            "text": response_text,
            "buttons": buttons or [],
        }


__all__ = ["WebAdapter"]
