"""
FakeAIClient для dev/test режима без реальных API-ключей.

Возвращает предзаданные ответы из очереди. По умолчанию — эхо входящего текста
с преамбулой "[fake]". Тесты могут заменить очередь через set_responses().
"""

from __future__ import annotations

import asyncio
from collections import deque

from agent.ai.factory import AIClient, AIResponse, ToolCall


class FakeAIClient(AIClient):
    @property
    def name(self) -> str:
        return "fake"

    def supports_tools(self) -> bool:
        # Fake-клиент может имитировать tool_use через push_response(text, tool_calls=[...]).
        return True

    def __init__(self) -> None:
        self._queue: deque[AIResponse] = deque()
        self._default_lock = asyncio.Lock()
        self.call_count = 0
        self.total_input_tokens = 0
        self.total_output_tokens = 0
        self.last_system: str | None = None
        self.last_messages: list[dict] | None = None

    def set_responses(self, responses: list[AIResponse]) -> None:
        self._queue = deque(responses)

    def push_response(self, text: str, tool_calls: list[ToolCall] | None = None) -> None:
        self._queue.append(
            AIResponse(
                text=text,
                tool_calls=tool_calls or [],
                input_tokens=10,
                output_tokens=len(text.split()),
                model="fake",
                provider="fake",
            )
        )

    async def complete(
        self,
        system: str,
        messages: list[dict],
        tools: list[dict] | None = None,
        max_tokens: int = 1024,
    ) -> AIResponse:
        self.call_count += 1
        self.last_system = system
        self.last_messages = list(messages)

        if self._queue:
            resp = self._queue.popleft()
            self.total_input_tokens += resp.input_tokens
            self.total_output_tokens += resp.output_tokens
            return resp

        # Дефолт: эхо последнего user-сообщения с преамбулой
        last_user = ""
        for m in reversed(messages):
            if m.get("role") == "user":
                last_user = m.get("content", "")
                break
        text = f"[fake-ai] Эхо: {last_user[:200]}"
        self.total_input_tokens += 10
        self.total_output_tokens += len(text.split())
        return AIResponse(
            text=text,
            tool_calls=[],
            input_tokens=10,
            output_tokens=len(text.split()),
            model="fake",
            provider="fake",
        )


__all__ = ["FakeAIClient"]
