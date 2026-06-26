"""
YandexGPT клиент (минимум для Phase 1).

Используется для summary и как fallback при сбое Claude.
Без tool calling (YandexGPT tool API — отдельная история, отложено).
"""

from __future__ import annotations

import httpx

from agent.ai.factory import AIClient, AIError, AIResponse
from agent.config import settings
from agent.utils import get_logger

log = get_logger("yandex_client")

YANDEXGPT_URL = "https://llm.api.cloud.yandex.net/foundationModels/v1/completion"
DEFAULT_MODEL_URI = "yandexgpt-lite"


class YandexClient(AIClient):
    def __init__(self, model_uri: str = DEFAULT_MODEL_URI) -> None:
        self._model_uri = (
            f"gpt://{settings.yandexgpt_folder_id}/{model_uri}"
            if not model_uri.startswith("gpt://")
            else model_uri
        )
        proxies: str | None = settings.socks5_proxy if settings.socks5_proxy else None
        self._client = httpx.AsyncClient(
            headers={
                "Authorization": f"Api-Key {settings.yandexgpt_api_key}",
                "Content-Type": "application/json",
            },
            timeout=httpx.Timeout(30.0, connect=10.0),
            verify=settings.verify_ssl,
            proxy=proxies,
        )

    @property
    def name(self) -> str:
        return "yandexgpt"

    def supports_tools(self) -> bool:
        return False

    async def complete(
        self,
        system: str,
        messages: list[dict],
        tools: list[dict] | None = None,
        max_tokens: int = 1024,
    ) -> AIResponse:
        # YandexGPT ожидает system + alternation user/assistant в messages
        # Конвертируем messages в формат YandexGPT
        ya_messages: list[dict] = []
        for m in messages:
            role = m.get("role", "user")
            if role == "system":
                ya_messages.append({"role": "system", "text": m.get("content", "")})
            elif role == "user":
                ya_messages.append({"role": "user", "text": m.get("content", "")})
            elif role == "assistant":
                ya_messages.append({"role": "assistant", "text": m.get("content", "")})
        # System YandexGPT принимает в отдельном поле
        body = {
            "modelUri": self._model_uri,
            "completionOptions": {
                "stream": False,
                "maxTokens": str(max_tokens),
                "temperature": 0.6,
            },
            "messages": ya_messages,
        }
        try:
            r = await self._client.post(YANDEXGPT_URL, json=body)
        except httpx.HTTPError as e:
            log.exception("yandex.network_error")
            raise AIError(f"YandexGPT network: {e}") from e

        if r.status_code != 200:
            log.error("yandex.http_error", status=r.status_code, body=r.text[:300])
            raise AIError(f"YandexGPT {r.status_code}: {r.text[:200]}")

        data = r.json()
        try:
            text = data["result"]["alternatives"][0]["message"]["text"].strip()
            usage = data["result"].get("usage", {})
            in_tok = int(usage.get("inputTextTokens", 0))
            out_tok = int(usage.get("completionTokens", 0))
        except (KeyError, IndexError) as e:
            log.exception("yandex.parse_error", data=str(data)[:300])
            raise AIError(f"YandexGPT parse error: {e}") from e

        return AIResponse(
            text=text,
            tool_calls=[],
            input_tokens=in_tok,
            output_tokens=out_tok,
            model=self._model_uri,
            provider="yandexgpt",
        )

    async def close(self) -> None:
        await self._client.aclose()


__all__ = ["YandexClient", "YANDEXGPT_URL"]
