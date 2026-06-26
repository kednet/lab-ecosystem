"""
FallbackAIClient — обёртка, которая пробует primary, а при сбое — secondary.

Логика:
  - `primary.generate()` бросил `AIClientError(retriable=True)` → логируем warning,
    пробуем `secondary.generate(...)`.
  - Если primary упал с `retriable=False` (например, 400/401) — сразу пробрасываем,
    бессмысленно тратить токены на secondary с битым запросом.
  - Если secondary тоже упал — пробрасываем его исключение.
"""
from __future__ import annotations

from typing import Optional

from agent.ai.base import AIClientError, BaseAIClient
from agent.utils.logger import get_logger


logger = get_logger()


class FallbackAIClient(BaseAIClient):
    """Последовательный fallback между двумя клиентами."""

    name = "fallback"

    def __init__(self, primary: BaseAIClient, secondary: BaseAIClient):
        if not isinstance(primary, BaseAIClient) or not isinstance(secondary, BaseAIClient):
            raise TypeError(
                "primary и secondary должны наследовать BaseAIClient"
            )
        self.primary = primary
        self.secondary = secondary
        logger.info(
            "🔁 FallbackAIClient: primary={}, secondary={}",
            primary.model_name, secondary.model_name,
        )

    @property
    def model_name(self) -> str:
        return f"fallback({self.primary.model_name} → {self.secondary.model_name})"

    def generate(
        self,
        *,
        system: str,
        user: str,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
    ) -> str:
        # 1) Пытаемся primary
        try:
            return self.primary.generate(
                system=system, user=user,
                max_tokens=max_tokens, temperature=temperature,
            )
        except AIClientError as e:
            if not e.retriable:
                logger.error(
                    "❌ Primary {} вернул необратимую ошибку: {}",
                    self.primary.name, e,
                )
                raise
            logger.warning(
                "⚠️ Primary {} недоступен ({}). Переключаюсь на {}…",
                self.primary.name, e, self.secondary.name,
            )
        except Exception as e:  # noqa: BLE001
            # Не-AIClientError: считаем сетевой и пробуем secondary
            logger.warning(
                "⚠️ Primary {} бросил неожиданное исключение: {}. Переключаюсь на {}…",
                self.primary.name, e, self.secondary.name,
            )

        # 2) Пробуем secondary
        return self.secondary.generate(
            system=system, user=user,
            max_tokens=max_tokens, temperature=temperature,
        )

    def test_connection(self) -> bool:
        if self.primary.test_connection():
            return True
        logger.info(
            "🔁 Primary {} не прошёл self-test, проверяю secondary…",
            self.primary.name,
        )
        return self.secondary.test_connection()
