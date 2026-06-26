"""
Общий ABC для AI-клиентов + фабрика.

Phase 1: Claude (основной), YandexGPT (fallback для summary).
AI_FAKE_MODE=true → встроенный FakeAIClient (без API-ключей).
"""

from __future__ import annotations

import os
from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class ToolCall:
    """Один tool call от AI."""

    name: str
    input: dict
    tool_use_id: str = ""


@dataclass
class AIResponse:
    """Ответ AI-клиента."""

    text: str
    tool_calls: list[ToolCall] = field(default_factory=list)
    input_tokens: int = 0
    output_tokens: int = 0
    model: str = ""
    provider: str = ""


class AIClient(ABC):
    """Базовый интерфейс AI-провайдера."""

    @property
    @abstractmethod
    def name(self) -> str: ...

    @abstractmethod
    def supports_tools(self) -> bool: ...

    @abstractmethod
    async def complete(
        self,
        system: str,
        messages: list[dict],
        tools: list[dict] | None = None,
        max_tokens: int = 1024,
    ) -> AIResponse: ...


class AIUnconfiguredError(RuntimeError):
    """Ни один провайдер не сконфигурирован."""


class AIError(RuntimeError):
    """Ошибка вызова AI (network, 5xx, rate limit, timeout)."""


# === Singleton-кэш ===

_clients: dict[str, AIClient] = {}


def _make_fake_client() -> AIClient:
    """Импортируется лениво, чтобы не тянуть anthropic в тестах без него."""
    from agent.ai.fake_client import FakeAIClient  # local import
    return FakeAIClient()


def _make_claude_client() -> AIClient:
    from agent.ai.claude_client import ClaudeClient
    return ClaudeClient()


def _make_yandex_client() -> AIClient:
    from agent.ai.yandex_client import YandexClient
    return YandexClient()


def get_ai_client(prefer: str = "claude") -> AIClient:
    """Singleton-фабрика.

    prefer='claude' (default): Claude → YandexGPT → Fake.
    prefer='yandex': YandexGPT → Claude → Fake.
    AI_FAKE_MODE=true → всегда Fake (для dev/тестов без ключей).
    """
    if os.getenv("AI_FAKE_MODE", "").lower() in ("1", "true", "yes"):
        if "fake" not in _clients:
            _clients["fake"] = _make_fake_client()
        return _clients["fake"]

    from agent.config import settings

    if prefer == "claude":
        if settings.has_anthropic:
            if "claude" not in _clients:
                _clients["claude"] = _make_claude_client()
            return _clients["claude"]
        if settings.yandexgpt_api_key and settings.yandexgpt_folder_id:
            if "yandex" not in _clients:
                _clients["yandex"] = _make_yandex_client()
            return _clients["yandex"]
    else:  # prefer='yandex'
        if settings.yandexgpt_api_key and settings.yandexgpt_folder_id:
            if "yandex" not in _clients:
                _clients["yandex"] = _make_yandex_client()
            return _clients["yandex"]
        if settings.has_anthropic:
            if "claude" not in _clients:
                _clients["claude"] = _make_claude_client()
            return _clients["claude"]

    raise AIUnconfiguredError(
        "Ни один AI-провайдер не сконфигурирован. "
        "Заполните ANTHROPIC_API_KEY или YANDEXGPT_API_KEY+YANDEXGPT_FOLDER_ID, "
        "или установите AI_FAKE_MODE=true для dev-режима."
    )


def reset_clients() -> None:
    """Сбрасывает singleton-кэш (для тестов)."""
    _clients.clear()


__all__ = [
    "ToolCall",
    "AIResponse",
    "AIClient",
    "AIUnconfiguredError",
    "AIError",
    "get_ai_client",
    "reset_clients",
]
