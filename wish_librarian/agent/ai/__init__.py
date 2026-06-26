"""
AI-модули WishLibrarian.

Поддерживаемые провайдеры (выбираются через AI_PROVIDER в .env):
  - claude    → ClaudeClient (Anthropic)
  - yandex    → YandexGPTClient (Yandex Cloud Foundation Models)
  - gigachat  → GigaChatClient (Сбер)
  - fallback  → FallbackAIClient(YandexGPTClient, GigaChatClient)
"""
from agent.ai.base import AIClientError, BaseAIClient
from agent.ai.claude_client import ClaudeClient
from agent.ai.fallback import FallbackAIClient
from agent.ai.gigachat_client import GigaChatClient
from agent.ai.prompts import (
    SUMMARY_SYSTEM_PROMPT,
    TIPS_SYSTEM_PROMPT,
    WORKBOOK_SYSTEM_PROMPT,
    build_summary_prompt,
    build_tips_prompt,
    build_workbook_prompt,
)
from agent.ai.yandex_client import YandexGPTClient
from agent.ai.factory import get_ai_client, reset_ai_client

__all__ = [
    "BaseAIClient",
    "AIClientError",
    "ClaudeClient",
    "YandexGPTClient",
    "GigaChatClient",
    "FallbackAIClient",
    "get_ai_client",
    "reset_ai_client",
    "SUMMARY_SYSTEM_PROMPT",
    "WORKBOOK_SYSTEM_PROMPT",
    "TIPS_SYSTEM_PROMPT",
    "build_summary_prompt",
    "build_workbook_prompt",
    "build_tips_prompt",
]
