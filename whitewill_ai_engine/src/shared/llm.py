"""Обёртка над YandexGPT через OpenAI-совместимый API.

В demo-режиме возвращает мок-ответы, чтобы не тратить деньги на каждом тесте.
"""

import json
import logging
import time
from typing import Any

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from .config import settings

logger = logging.getLogger(__name__)


class YandexGPTClient:
    """Клиент YandexGPT через OpenAI-совместимый API Yandex Cloud.

    Docs: https://yandex.cloud/docs/foundation-models/openai-api
    """

    BASE_URL = "https://llm.api.cloud.yandex.net/v1"

    def __init__(
        self,
        folder_id: str | None = None,
        api_key: str | None = None,
        use_mock: bool | None = None,
    ) -> None:
        self.folder_id = folder_id or settings.yandex_folder_id
        self.api_key = api_key or settings.yandex_api_key
        self.model = settings.yandex_gpt_model
        self.use_mock = use_mock if use_mock is not None else settings.use_mock_llm

        if not self.use_mock and not self.api_key:
            raise ValueError("YANDEX_API_KEY is required when use_mock=False")

    @property
    def model_uri(self) -> str:
        return f"gpt://{self.folder_id}/{self.model}/{settings.yandex_gpt_version}"

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        reraise=True,
    )
    async def chat(
        self,
        messages: list[dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 1024,
        response_format: dict[str, str] | None = None,
        lang: str | None = None,
    ) -> dict[str, Any]:
        """Запрос к YandexGPT. Возвращает {"content": str, "tokens_in": int, "tokens_out": int, "latency_ms": int}."""

        start = time.perf_counter()

        if self.use_mock:
            return self._mock_response(messages, temperature, max_tokens, lang=lang)

        payload = {
            "model": self.model_uri,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": False,
        }
        if response_format:
            payload["response_format"] = response_format

        headers = {
            "Authorization": f"Api-Key {self.api_key}",
            "Content-Type": "application/json",
        }

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{self.BASE_URL}/chat/completions",
                json=payload,
                headers=headers,
            )
            response.raise_for_status()
            data = response.json()

        latency_ms = int((time.perf_counter() - start) * 1000)
        choice = data["choices"][0]
        usage = data.get("usage", {})

        return {
            "content": choice["message"]["content"],
            "tokens_in": usage.get("prompt_tokens", 0),
            "tokens_out": usage.get("completion_tokens", 0),
            "latency_ms": latency_ms,
            "finish_reason": choice.get("finish_reason"),
        }

    def _mock_response(
        self,
        messages: list[dict[str, str]],
        temperature: float,
        max_tokens: int,
        lang: str | None = None,
    ) -> dict[str, Any]:
        """Мок-ответы для demo. Имитирует LLM с учётом текущего состояния диалога."""
        last_user_msg = next(
            (m["content"] for m in reversed(messages) if m["role"] == "user"),
            "",
        )
        last_user_msg_lower = last_user_msg.lower()

        # Приоритет: явный lang от бота → иначе fallback по кириллице в user-сообщении
        if lang not in ("ru", "en"):
            lang = "en" if last_user_msg and any("A" <= ch <= "z" for ch in last_user_msg) and not any("Ѐ" <= ch <= "ӿ" for ch in last_user_msg) else "ru"

        # Достаём текущее состояние диалога из system prompt (бот кладёт "ТЕКУЩАЯ СТАДИЯ ДИАЛОГА: <state>")
        current_state = "welcome"
        for m in messages:
            if m["role"] == "system":
                sys_content = m["content"]
                if lang == "en":
                    if "CURRENT DIALOG STAGE:" in sys_content:
                        current_state = sys_content.split("CURRENT DIALOG STAGE:")[1].split("\n")[0].strip().lower()
                else:
                    if "ТЕКУЩАЯ СТАДИЯ ДИАЛОГА:" in sys_content:
                        current_state = sys_content.split("ТЕКУЩАЯ СТАДИЯ ДИАЛОГА:")[1].split("\n")[0].strip().lower()
                break

        content = self._select_mock_reply(last_user_msg_lower, lang, current_state)

        return {
            "content": content,
            "tokens_in": len(last_user_msg.split()) * 2,
            "tokens_out": len(content.split()) * 2,
            "latency_ms": 850,
            "finish_reason": "stop",
        }

    def _select_mock_reply(self, user_msg: str, lang: str = "ru", current_state: str = "welcome") -> str:
        """Подбирает мок-ответ по текущему состоянию диалога (а не по user-сообщению)."""

        if lang == "en":
            return self._select_mock_reply_en(user_msg, current_state)

        # RU-сценарий — логика по state, а не по сообщению
        if current_state == "goal":
            return "Понял! Какой бюджет рассматриваете? (до 100 млн / 100–300 млн / 300 млн+ / гибкий)"
        if current_state == "budget":
            return "Отлично! Какие районы рассматриваете? (Хамовники / Остоженка / Патриаршие / Арбат / Тверской) Или интересует Дубай / Абу-Даби?"
        if current_state == "district":
            return "Хорошо! В какие сроки планируете сделку? (срочно / 1–3 мес / 3–6 мес / 6+ мес)"
        if current_state == "timeline":
            return "Спасибо! Какой способ оплаты рассматриваете? (ипотека / наличные / перевод из-за рубежа)"
        if current_state == "payment":
            return json.dumps(
                {
                    "qualified": True,
                    "score": 0.85,
                    "summary": "Клиент готов к сделке, готов передать брокеру",
                },
                ensure_ascii=False,
            )

        # welcome или fallback
        return "Здравствуйте! Я AI-ассистент Whitewill. Помогу подобрать элитную недвижимость. Какая цель покупки: для себя, инвестиция или сохранение капитала?"

    def _select_mock_reply_en(self, user_msg: str, current_state: str = "welcome") -> str:
        """EN-сценарий: логика по state."""

        if current_state == "goal":
            return "Got it! What's your budget? (up to $1M / $1–3M / $3M+ / flexible)"
        if current_state == "budget":
            return "Great! Which districts are you considering? (Khamovniki / Ostozhenka / Patriarshy / Arbat / Tverskoy) Or are you also looking at Dubai / Abu Dhabi?"
        if current_state == "district":
            return "Perfect! What's your timeline? (urgent / 1–3 months / 3–6 months / 6+ months)"
        if current_state == "timeline":
            return "Thank you! How do you plan to pay? (mortgage / cash / international wire transfer)"
        if current_state == "payment":
            return json.dumps(
                {
                    "qualified": True,
                    "score": 0.85,
                    "summary": "Client ready, handing off to broker",
                }
            )

        return "Hello! I'm Whitewill's AI assistant. I'll help you find luxury real estate in Moscow. What's the purpose of your purchase? (personal / investment / capital preservation)"

    async def embed(self, texts: list[str]) -> list[list[float]]:
        """Получить эмбеддинги через Yandex Cloud. В мок-режиме возвращает фейковые вектора."""

        if self.use_mock:
            # Возвращаем детерминированные фейковые вектора размерности 256
            import hashlib

            vectors = []
            for text in texts:
                h = hashlib.sha256(text.encode()).digest()
                # 32 байта → 32 float (используем каждый байт / 255)
                vec = [b / 255.0 for b in h] * 8  # 256 значений
                vectors.append(vec)
            return vectors

        # Реальный вызов к Yandex Cloud Embeddings
        url = "https://llm.api.cloud.yandex.net/v1/embeddings"
        headers = {
            "Authorization": f"Api-Key {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": f"emb://{self.folder_id}/{settings.yandex_embeddings_model}/latest",
            "input": texts,
        }

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(url, json=payload, headers=headers)
            response.raise_for_status()
            data = response.json()

        return [item["embedding"] for item in data["data"]]

    def estimate_cost(self, tokens_in: int, tokens_out: int) -> float:
        """Оценить стоимость запроса в рублях."""
        return (
            tokens_in * settings.yandex_gpt_input_price / 1000
            + tokens_out * settings.yandex_gpt_output_price / 1000
        )


# Singleton
_llm_instance: YandexGPTClient | None = None


def get_llm() -> YandexGPTClient:
    global _llm_instance
    if _llm_instance is None:
        _llm_instance = YandexGPTClient()
    return _llm_instance
