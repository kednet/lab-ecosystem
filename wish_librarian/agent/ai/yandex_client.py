"""
Клиент для YandexGPT (Foundation Models API).

Документация:
  https://cloud.yandex.ru/docs/yandexgpt/api-ref/v1/operations/generate

Аутентификация: header `Authorization: Api-Key <YANDEX_API_KEY>` +
header `x-folder-id: <YANDEX_FOLDER_ID>`.
"""
from __future__ import annotations

import time
from typing import Any, Optional

import httpx
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


class YandexGPTClient(BaseAIClient):
    """Клиент YandexGPT Foundation Models v1."""

    name = "yandex"
    DEFAULT_BASE_URL = "https://llm.api.cloud.yandex.net/foundationModels/v1"

    def __init__(
        self,
        *,
        api_key: Optional[str] = None,
        folder_id: Optional[str] = None,
        model: Optional[str] = None,
        base_url: Optional[str] = None,
        timeout: Optional[int] = None,
    ):
        self.settings = get_settings()
        self.api_key = api_key or self.settings.yandex_api_key
        self.folder_id = folder_id or self.settings.yandex_folder_id
        self.model = model or self.settings.yandex_model
        self.base_url = (base_url or self.settings.yandex_base_url).rstrip("/")
        self.timeout = timeout or self.settings.request_timeout

        if not self.api_key:
            raise RuntimeError(
                "YANDEX_API_KEY не задан. Получите ключ в "
                "https://console.yandex.cloud/ и добавьте в .env"
            )
        if not self.folder_id:
            raise RuntimeError(
                "YANDEX_FOLDER_ID не задан. Скопируйте ID каталога в "
                "https://console.yandex.cloud/ и добавьте в .env"
            )

        # trust_env=False — игнорируем HTTP(S)_PROXY из окружения, чтобы
        # socks4:// от VPN-клиента не валил httpx (SOCKS не поддерживается).
        self._client = httpx.Client(
            timeout=self.timeout,
            trust_env=False,
            headers={
                "Authorization": f"Api-Key {self.api_key}",
                "x-folder-id": self.folder_id,
                "Content-Type": "application/json",
                "User-Agent": self.settings.user_agent,
            },
        )

    @property
    def model_name(self) -> str:
        return f"yandex:{self.model}"

    def _build_payload(
        self,
        system: str,
        user: str,
        max_tokens: Optional[int],
        temperature: Optional[float],
    ) -> dict[str, Any]:
        return {
            "modelUri": f"gpt://{self.folder_id}/{self.model}",
            "completionOptions": {
                "stream": False,
                "temperature": (
                    temperature
                    if temperature is not None
                    else self.settings.claude_temperature
                ),
                "maxTokens": str(
                    max_tokens or self.settings.claude_max_tokens
                ),
            },
            "messages": [
                {"role": "system", "text": system},
                {"role": "user", "text": user},
            ],
        }

    def _is_retriable(self, response: httpx.Response) -> bool:
        return response.status_code in (408, 409, 429, 500, 502, 503, 504)

    @retry(
        retry=retry_if_exception_type((httpx.TimeoutException, httpx.NetworkError)),
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
        url = f"{self.base_url}/completion"
        payload = self._build_payload(system, user, max_tokens, temperature)

        logger.debug(
            "🟡 YandexGPT generate: model={}, max_tokens={}, temp={}",
            self.model,
            payload["completionOptions"]["maxTokens"],
            payload["completionOptions"]["temperature"],
        )

        t0 = time.time()
        try:
            resp = self._client.post(url, json=payload)
        except httpx.TimeoutException as e:
            logger.warning("⏱ YandexGPT timeout: {}", e)
            raise
        except httpx.NetworkError as e:
            logger.warning("🌐 YandexGPT network error: {}", e)
            raise

        elapsed = time.time() - t0
        if not resp.is_success:
            retriable = self._is_retriable(resp)
            try:
                err_body = resp.json()
            except Exception:
                err_body = resp.text[:300]
            logger.error(
                "❌ YandexGPT HTTP {} (retriable={}): {}",
                resp.status_code, retriable, err_body,
            )
            raise AIClientError(
                f"HTTP {resp.status_code}: {err_body}",
                retriable=retriable,
                provider=self.name,
            )

        data = resp.json()
        try:
            text = data["result"]["alternatives"][0]["message"]["text"]
        except (KeyError, IndexError, TypeError) as e:
            logger.error("Неожиданный формат ответа YandexGPT: {}", data)
            raise AIClientError(
                f"Не удалось извлечь текст из ответа: {e}",
                retriable=False,
                provider=self.name,
            ) from e

        usage = data.get("result", {}).get("usage", {})
        logger.info(
            "✅ YandexGPT: {}/{} tokens, {:.1f}s",
            usage.get("inputTextTokens", "?"),
            usage.get("completionTokens", "?"),
            elapsed,
        )
        return text.strip()

    def close(self) -> None:
        self._client.close()
