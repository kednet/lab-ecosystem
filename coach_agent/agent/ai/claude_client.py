"""
Claude-клиент (Anthropic SDK).

Создаёт свой httpx.Client с явным proxy (SOCKS5) и verify=settings.verify_ssl —
это критично для корпоративного MITM (см. memory: corporate-mitm-proxy).

Retry: 1 повтор с exponential backoff (2с). Timeout 30с.
"""

from __future__ import annotations

import asyncio

import httpx

from agent.ai.factory import AIClient, AIError, AIResponse, ToolCall
from agent.config import settings
from agent.utils import get_logger

log = get_logger("claude_client")

# === Цены (USD за 1M tokens), захардкожены для Phase 1 ===
# Источник: https://docs.anthropic.com/en/docs/about-claude/pricing
COST_PER_1M_INPUT: dict[str, float] = {
    "claude-sonnet-4-5": 3.0,
    "claude-sonnet-4-5-20251001": 3.0,
    "claude-haiku-4-5": 0.8,
    "claude-haiku-4-5-20251001": 0.8,
}
COST_PER_1M_OUTPUT: dict[str, float] = {
    "claude-sonnet-4-5": 15.0,
    "claude-sonnet-4-5-20251001": 15.0,
    "claude-haiku-4-5": 4.0,
    "claude-haiku-4-5-20251001": 4.0,
}
DEFAULT_MODEL = "claude-sonnet-4-5"


def estimate_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    in_price = COST_PER_1M_INPUT.get(model, 3.0)
    out_price = COST_PER_1M_OUTPUT.get(model, 15.0)
    return (input_tokens / 1_000_000) * in_price + (output_tokens / 1_000_000) * out_price


def _build_anthropic_client() -> anthropic.Anthropic:  # type: ignore[name-defined]  # noqa: F821
    """Создаёт anthropic.Anthropic с MITM-httpx.Client."""
    try:
        import anthropic
    except ImportError as e:
        raise AIError(
            "anthropic SDK не установлен. Выполните: pip install -e '.[ai]'"
        ) from e

    proxies: str | None = settings.socks5_proxy if settings.socks5_proxy else None
    http_client = httpx.Client(
        proxy=proxies,
        verify=settings.verify_ssl,
        timeout=httpx.Timeout(30.0, connect=10.0),
    )
    return anthropic.Anthropic(
        api_key=settings.anthropic_api_key,
        http_client=http_client,
    )


class ClaudeClient(AIClient):
    def __init__(self, model: str = DEFAULT_MODEL, max_retries: int = 1) -> None:
        self._model = model
        self._max_retries = max_retries
        self._client = _build_anthropic_client()

    @property
    def name(self) -> str:
        return "claude"

    def supports_tools(self) -> bool:
        return True

    async def complete(
        self,
        system: str,
        messages: list[dict],
        tools: list[dict] | None = None,
        max_tokens: int = 1024,
    ) -> AIResponse:
        """Запрос к Claude. Retry 1 раз при сетевых/5xx ошибках."""
        attempt = 0
        last_exc: Exception | None = None
        while attempt <= self._max_retries:
            try:
                return await self._call_once(system, messages, tools, max_tokens)
            except (httpx.HTTPError, AIError) as e:
                last_exc = e
                attempt += 1
                if attempt > self._max_retries:
                    break
                backoff = 2 ** attempt  # 2с
                log.warning(
                    "claude.retry",
                    attempt=attempt,
                    backoff=backoff,
                    error=str(e)[:200],
                )
                await asyncio.sleep(backoff)
        log.exception("claude.failed", last_exc=str(last_exc)[:200] if last_exc else "unknown")
        raise AIError(f"Claude API failed after {self._max_retries + 1} attempts: {last_exc}")

    async def _call_once(
        self,
        system: str,
        messages: list[dict],
        tools: list[dict] | None,
        max_tokens: int,
    ) -> AIResponse:
        # anthropic SDK синхронный — выполняем в executor
        loop = asyncio.get_running_loop()

        def _sync_call() -> AIResponse:
            kwargs: dict = {
                "model": self._model,
                "max_tokens": max_tokens,
                "system": system,
                "messages": messages,
            }
            if tools:
                kwargs["tools"] = tools
            r = self._client.messages.create(**kwargs)
            # Парсим ответ
            text_parts: list[str] = []
            tool_calls: list[ToolCall] = []
            for block in r.content:
                if block.type == "text":
                    text_parts.append(block.text)
                elif block.type == "tool_use":
                    tool_calls.append(
                        ToolCall(
                            name=block.name,
                            input=dict(block.input) if block.input else {},
                            tool_use_id=block.id,
                        )
                    )
            input_tokens = r.usage.input_tokens if r.usage else 0
            output_tokens = r.usage.output_tokens if r.usage else 0
            return AIResponse(
                text="\n".join(text_parts).strip(),
                tool_calls=tool_calls,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                model=self._model,
                provider="claude",
            )

        return await loop.run_in_executor(None, _sync_call)


__all__ = ["ClaudeClient", "estimate_cost", "DEFAULT_MODEL"]
