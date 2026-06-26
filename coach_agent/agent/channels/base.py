"""
Базовый ABC для каналов.

Phase 1: только web (HTTP request/response). Telegram/VK — в Phase 6/7.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any

from agent.core.message_bus import NormalizedMessage


@dataclass
class ButtonSpec:
    label: str
    payload: str
    kind: str  # 'tone_pick' | 'start_pick' | 'end_session'


class ChannelAdapter(ABC):
    channel_name: str = "base"

    @abstractmethod
    def normalize_inbound(self, raw: dict[str, Any]) -> NormalizedMessage | None:
        """Превращает сырой payload канала в NormalizedMessage."""

    @abstractmethod
    def format_outbound(self, response_text: str, buttons: list[dict]) -> dict[str, Any]:
        """Превращает CoachResponse в payload для HTTP-ответа."""
