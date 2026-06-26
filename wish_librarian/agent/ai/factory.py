"""
Фабрика AI-клиентов.

Считывает `AI_PROVIDER` из настроек и возвращает соответствующий `BaseAIClient`.
Синглтон-кэш опционально (если `use_singleton=True`).
"""
from __future__ import annotations

from typing import Optional

from agent.ai.base import AIClientError, BaseAIClient
from agent.ai.claude_client import ClaudeClient
from agent.ai.fallback import FallbackAIClient
from agent.ai.gigachat_client import GigaChatClient
from agent.ai.yandex_client import YandexGPTClient
from agent.config import get_settings
from agent.utils.logger import get_logger


logger = get_logger()


_cached: Optional[BaseAIClient] = None


def get_ai_client(*, use_cache: bool = True) -> BaseAIClient:
    """
    Вернуть активный AI-клиент, выбранный через `AI_PROVIDER` в .env.

    Провайдеры:
      - "claude"     → ClaudeClient
      - "yandex"     → YandexGPTClient
      - "gigachat"   → GigaChatClient
      - "fallback"   → FallbackAIClient(YandexGPTClient, GigaChatClient)
    """
    global _cached
    if use_cache and _cached is not None:
        return _cached

    settings = get_settings()
    provider = settings.ai_provider

    if provider == "claude":
        client: BaseAIClient = ClaudeClient()
    elif provider == "yandex":
        client = YandexGPTClient()
    elif provider == "gigachat":
        client = GigaChatClient()
    elif provider == "fallback":
        # Сначала Yandex, при сбое — GigaChat
        primary: BaseAIClient
        if settings.has_yandex_key():
            primary = YandexGPTClient()
        elif settings.has_gigachat_key():
            # Yandex не сконфигурирован — fallback превращается в один GigaChat
            logger.warning(
                "AI_PROVIDER=fallback, но YANDEX_API_KEY/YANDEX_FOLDER_ID не заданы. "
                "Использую только GigaChat."
            )
            client = GigaChatClient()
            _cached = client
            return client
        else:
            raise RuntimeError(
                "AI_PROVIDER=fallback требует Yandex ИЛИ GigaChat ключи. "
                "Проверьте .env."
            )

        if settings.has_gigachat_key():
            client = FallbackAIClient(primary, GigaChatClient())
        else:
            logger.warning(
                "AI_PROVIDER=fallback, но GIGACHAT_AUTHORIZATION_KEY не задан. "
                "Использую только YandexGPT."
            )
            client = primary
    else:
        raise RuntimeError(f"Неизвестный AI_PROVIDER: {provider!r}")

    _cached = client
    logger.info("🤖 AI-провайдер: {} ({})", client.name, client.model_name)
    return client


def reset_ai_client() -> None:
    """Сбросить кэш (например, в тестах)."""
    global _cached
    _cached = None


__all__ = [
    "BaseAIClient",
    "AIClientError",
    "ClaudeClient",
    "YandexGPTClient",
    "GigaChatClient",
    "FallbackAIClient",
    "get_ai_client",
    "reset_ai_client",
]
