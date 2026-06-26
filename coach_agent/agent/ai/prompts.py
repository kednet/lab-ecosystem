"""
Сборка system-prompt: BASE + TONE_ADDON + INTENSITY_MODIFIER + CONTEXT.

Импортирует TONE_ADDONS / INTENSITY_MODIFIERS из core.tones (единственный источник истины).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from agent.core.tones import (
    INTENSITY_MODIFIERS,
    TONE_ADDONS,
    Tone,
)

# === Базовый system-prompt (PRD 10, 7.3) ===

BASE_SYSTEM_PROMPT: str = (
    "Ты — WishCoach, ИИ-коуч для подписчиков 'Лаборатории желаний'. "
    "Твоя ключевая суперсила — помочь отличить навязанное желание "
    "(страх, социум, реклама, 'надо') от истинного (внутреннее 'хочу', "
    "телесный отклик, спокойная радость).\n\n"

    "ПРАВИЛА:\n"
    "1. НЕ давай готовых ответов. Задавай структурированные вопросы.\n"
    "2. НЕ мотивируй цитатками и 'мотивашкой'.\n"
    "3. НЕ выдумывай фактов. Если не знаешь — скажи.\n"
    "4. НЕ давай медицинских, юридических, финансовых рекомендаций.\n"
    "5. Если клиент описывает кризис (суицид, насилие, самоповреждение) — "
    "НЕ продолжай как коуч. Crisis-detection уже сработает на нашей стороне, "
    "и ты не получишь такие сообщения.\n"
    "6. Говори на русском, дружелюбно, но без заискивания.\n"
    "7. Длина ответа: 1-4 предложения, без длинных лекций.\n"
)


# === Channel hints ===

CHANNEL_HINTS: dict[str, str] = {
    "web": (
        "КАНАЛ: web. Отвечай текстом, можно использовать markdown. "
        "Кнопки — отдельным списком, не в тексте."
    ),
    "telegram": (
        "КАНАЛ: telegram. Отвечай текстом с минимальной разметкой. "
        "Без markdown-заголовков."
    ),
    "vk": (
        "КАНАЛ: vk. Отвечай коротко, без markdown-разметки."
    ),
}


# === Context block ===

@dataclass
class ContextBlock:
    """Runtime-контекст для промпта: желания, последние сообщения, канал, онбординг."""

    active_desire_title: str | None = None
    recent_messages: list[str] = field(default_factory=list)
    channel: str = "web"
    is_onboarding: bool = False
    mode_hint: str = ""

    def render(self) -> str:
        parts: list[str] = []
        parts.append(CHANNEL_HINTS.get(self.channel, CHANNEL_HINTS["web"]))
        if self.mode_hint:
            parts.append(f"РЕЖИМ: {self.mode_hint}")
        if self.is_onboarding:
            parts.append("ЭТАП: первая сессия (онбординг). Помогай мягко, объясняй правила.")
        if self.active_desire_title:
            parts.append(f"АКТИВНОЕ ЖЕЛАНИЕ: {self.active_desire_title}")
        if self.recent_messages:
            parts.append("ПОСЛЕДНИЕ СООБЩЕНИЯ:")
            for m in self.recent_messages[-5:]:
                parts.append(f"  - {m[:300]}")
        return "\n".join(parts) if parts else ""


# === Сборка ===

def build_system_prompt(
    tone: Tone,
    intensity: int,
    context: ContextBlock,
) -> str:
    """Собирает финальный system-prompt из блоков."""
    if not 1 <= intensity <= 5:
        raise ValueError(f"intensity должна быть 1..5, получено {intensity}")

    blocks: list[str] = [
        BASE_SYSTEM_PROMPT,
        TONE_ADDONS[tone],
        INTENSITY_MODIFIERS[intensity],
    ]
    ctx = context.render()
    if ctx:
        blocks.append(ctx)
    return "\n\n".join(blocks)


__all__ = [
    "BASE_SYSTEM_PROMPT",
    "CHANNEL_HINTS",
    "ContextBlock",
    "build_system_prompt",
]
