"""
Клиент для Anthropic Claude API.

Использует официальный SDK `anthropic`. Поддерживает ретраи, логирование токенов.
"""
from __future__ import annotations

import time
from typing import Optional

from anthropic import APIError, APITimeoutError, Anthropic, RateLimitError
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from agent.ai.base import AIClientError, BaseAIClient
from agent.config import get_settings
from agent.utils.logger import get_logger


logger = get_logger()


class ClaudeClient(BaseAIClient):
    """Тонкая обёртка вокруг Anthropic SDK."""

    name = "claude"

    def __init__(self):
        self.settings = get_settings()
        if not self.settings.has_anthropic_key():
            raise AIClientError(
                "ANTHROPIC_API_KEY не задан или некорректен. "
                "Проверьте файл .env",
                retriable=False,
                provider=self.name,
            )
        self.client = Anthropic(api_key=self.settings.anthropic_api_key)
        self.model = self.settings.claude_model

    @property
    def model_name(self) -> str:
        return f"claude:{self.model}"

    @retry(
        retry=retry_if_exception_type((RateLimitError, APITimeoutError)),
        wait=wait_exponential(multiplier=1, min=2, max=20),
        stop=stop_after_attempt(3),
        reraise=True,
    )
    def generate(
        self,
        *,
        system: str,
        user: str,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
    ) -> str:
        """Сгенерировать ответ. Возвращает только текст."""
        model = self.model
        max_tokens = max_tokens or self.settings.claude_max_tokens
        temperature = (
            temperature if temperature is not None else self.settings.claude_temperature
        )

        logger.debug(
            "🤖 Claude generate: model={}, max_tokens={}, temp={}",
            model, max_tokens, temperature,
        )
        t0 = time.time()
        try:
            msg = self.client.messages.create(
                model=model,
                max_tokens=max_tokens,
                temperature=temperature,
                system=system,
                messages=[{"role": "user", "content": user}],
            )
        except RateLimitError as e:
            logger.warning("⚠️ Rate limit: {}", e)
            raise AIClientError(str(e), retriable=True, provider=self.name) from e
        except APITimeoutError as e:
            logger.warning("⏱ Timeout: {}", e)
            raise AIClientError(str(e), retriable=True, provider=self.name) from e
        except APIError as e:
            logger.error("❌ Anthropic API error: {}", e)
            raise AIClientError(
                str(e),
                retriable=False,
                provider=self.name,
            ) from e

        # Извлекаем текст
        text_parts = []
        for block in msg.content:
            if getattr(block, "type", None) == "text":
                text_parts.append(block.text)
        text = "\n".join(text_parts).strip()

        usage = getattr(msg, "usage", None)
        elapsed = time.time() - t0
        if usage:
            logger.info(
                "✅ Claude: {}/{} tokens, {:.1f}s",
                getattr(usage, "input_tokens", "?"),
                getattr(usage, "output_tokens", "?"),
                elapsed,
            )
        else:
            logger.info("✅ Claude: {:.1f}s", elapsed)
        return text

    def test_connection(self) -> bool:
        """Быстрая проверка ключа."""
        try:
            self.generate(
                system="Ты — тестовый ассистент.",
                user="Скажи одно слово: ОК",
                max_tokens=10,
                temperature=0.0,
            )
            return True
        except AIClientError as e:
            logger.error("❌ Тест Claude провалился: {}", e)
            return False
