"""
Crisis-detection: 4 regex-маркера + шаблонный ответ.

Источник: PRD v2.0 раздел 5.8.

Проверяется **на каждом сообщении клиента** ДО отправки в AI.
При срабатывании: сессия → S_CRISIS_STOP, коуч отдаёт шаблонный ответ (НЕ Claude),
сообщение помечается is_crisis_message=1, excluded_from_training=1,
в crisis_log пишется только SHA-256 хэш.

Важно: \b в Python re работает только с [a-zA-Z0-9_] и НЕ работает с
кириллицей. Поэтому для русскоязычных паттернов используем либо точные
фразы с re.escape (без \b), либо lookbehind/lookahead с явными классами.
Поскольку наши паттерны достаточно длинные (3+ слов) и специфичные,
используем plain search — false positive крайне маловероятны.
"""

from __future__ import annotations

import hashlib
import re

# === 4 группы regex-паттернов (PRD 5.8) ===
# Каждый паттерн — список альтернатив (ИЛИ).
# Без \b — чтобы кириллица корректно ловилась.

CRISIS_MARKERS: list[tuple[str, re.Pattern[str]]] = [
    (
        "suicide",
        re.compile(
            r"(не хочу жить|"
            r"суицид|"
            r"убить себя|"
            r"лучше бы я умер|"
            r"всё равно как жить дальше)",
            re.IGNORECASE,
        ),
    ),
    (
        "violence",
        re.compile(
            r"(бью (себя|её|его|ребёнка)|"
            r"причиняю боль|"
            r"избиваю)",
            re.IGNORECASE,
        ),
    ),
    (
        "self_harm",
        re.compile(
            r"(порезы|порезов|порезами|"
            r"таблетки сразу|"
            r"выйти в окно|"
            r"повеситься)",
            re.IGNORECASE,
        ),
    ),
    (
        "distress",
        re.compile(
            r"(крик о помощи|"
            r"не могу больше|"
            r"всё бессмысленно)",
            re.IGNORECASE,
        ),
    ),
]


def detect_crisis(text: str) -> str | None:
    """Возвращает имя первого сработавшего паттерна или None."""
    if not text:
        return None
    for name, pattern in CRISIS_MARKERS:
        if pattern.search(text):
            return name
    return None


def hash_message(text: str) -> str:
    """SHA-256 хэш сообщения для crisis_log. Только хэш, не текст!"""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


# === Шаблонный crisis-ответ (PRD 5.8) ===
# Строго фиксированный текст, НЕ генерируется Claude.

CRISIS_RESPONSE: str = (
    "🛑 Я не могу продолжать как коуч — то, что ты описываешь, серьёзнее, чем я могу помочь.\n\n"
    "Пожалуйста, обратись за профессиональной поддержкой прямо сейчас:\n\n"
    "📞 Бесплатно, круглосуточно:\n"
    "• Телефон доверия: 8-800-2000-122\n"
    "• Помощь в кризисе: 051 (с мобильного — 8-495-051)\n\n"
    "Если рядом опасно — позвони 112.\n\n"
    "Я здесь, когда тебе станет безопаснее. Напиши /start, когда будешь готов."
)


__all__ = [
    "CRISIS_MARKERS",
    "detect_crisis",
    "hash_message",
    "CRISIS_RESPONSE",
]
