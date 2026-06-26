"""
Базовый класс для всех AI-провайдеров.

Любой провайдер (Claude, YandexGPT, GigaChat, …) реализует единый контракт
`generate(*, system, user, max_tokens, temperature) -> str` — благодаря этому
Librarian и CLI не знают, какой провайдер активен.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional


class AIClientError(Exception):
    """
    Базовое исключение AI-клиента.

    Параметр `retriable` сигнализирует FallbackAIClient, можно ли пробовать
    резервный провайдер (например, при HTTP 429/5xx/timeout — да, при
    HTTP 401/400 — нет).
    """

    def __init__(
        self,
        message: str,
        *,
        retriable: bool = False,
        provider: str = "",
    ):
        super().__init__(message)
        self.retriable = retriable
        self.provider = provider

    def __str__(self) -> str:
        prefix = f"[{self.provider}] " if self.provider else ""
        return f"{prefix}{super().__str__()}"


class BaseAIClient(ABC):
    """
    Абстрактный AI-клиент.

    Подклассы обязаны реализовать `generate` и указать `name`.
    """

    name: str = "base"

    @abstractmethod
    def generate(
        self,
        *,
        system: str,
        user: str,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
    ) -> str:
        """Сгенерировать ответ модели. Возвращает только текст."""
        raise NotImplementedError

    def test_connection(self) -> bool:
        """
        Быстрая проверка доступности. По умолчанию — тривиальный запрос.
        Провайдеры могут переопределить для скорости/особенностей.
        """
        try:
            self.generate(
                system="Ты — тестовый ассистент.",
                user="Скажи одно слово: ОК",
                max_tokens=10,
                temperature=0.0,
            )
            return True
        except AIClientError as e:
            from agent.utils.logger import get_logger
            get_logger().error("❌ Тест {} провалился: {}", self.name, e)
            return False
        except Exception as e:  # noqa: BLE001
            from agent.utils.logger import get_logger
            get_logger().error("❌ Тест {} провалился (непредвиденная ошибка): {}",
                               self.name, e)
            return False

    @property
    def model_name(self) -> str:
        """Краткое описание активной модели (для логов и metadata.json)."""
        return getattr(self, "model", self.name)
