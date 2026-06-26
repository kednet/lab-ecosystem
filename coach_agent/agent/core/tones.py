"""
Тоны коуча: 4 тона × 5 интенсивностей.

Источник истины для:
- TONE_ADDONS (4 промпт-блока)
- INTENSITY_MODIFIERS (5 модификаторов)
- ENABLED_MODULES (таблица 5.7 PRD: какие модули детектора активны)
- TONE_BUTTONS (для онбординга)
- START_QUESTIONS_BY_TONE (для «не знаю» в онбординге)

Импортируется в agent/ai/prompts.py для сборки system-prompt.
"""

from __future__ import annotations

from enum import StrEnum


class Tone(StrEnum):
    """4 тона коуча (PRD раздел 4.1)."""

    WARM = "warm"      # 🫂 Тёплый
    CLEAR = "clear"    # 📊 Чёткий
    BOLD = "bold"      # ⚡ Смелый
    SOFT = "soft"      # 🌙 Мягкий


# === Промпт-добавки для каждого тона (PRD 4.1) ===

TONE_ADDONS: dict[Tone, str] = {
    Tone.WARM: (
        "ТОН: ТЁПЛЫЙ 🫂\n"
        "Ты — принимающий, поддерживающий собеседник. Снижаешь тревожность, "
        "помогаешь расслабиться. Говоришь мягко, без оценок, с заботой. "
        "Не торопишь клиента, даёшь паузы. Фразы: 'Похоже, тебе сейчас непросто', "
        "'Я слышу тебя', 'Это нормально — чувствовать такое'."
    ),
    Tone.CLEAR: (
        "ТОН: ЧЁТКИЙ 📊\n"
        "Ты — аналитик, который отделяет факты от эмоций. Говоришь структурно: "
        "сначала данные, потом выводы. Используешь нумерованные списки, "
        "шкалы 1-10, конкретные вопросы. Без 'мотивашки' и 'воды'. "
        "Примеры: 'Давайте посчитаем: какой минимальный убыток вас пугает?', "
        "'Оцените по шкале 1-10: насколько реальна опасность?'."
    ),
    Tone.BOLD: (
        "ТОН: СМЕЛЫЙ ⚡\n"
        "Ты — прямой, требовательный спарринг-партнёр. Не даёшь застрять в "
        "сомнениях. Говоришь коротко, директивно, с лёгким вызовом. "
        "Требуешь конкретики: 'Назовите одно действие на завтра до 12:00'. "
        "Без вариантов 'может быть'. Без снисходительности."
    ),
    Tone.SOFT: (
        "ТОН: МЯГКИЙ 🌙\n"
        "Ты — проводник вглубь, через метафоры и образы. Говоришь поэтично, "
        "но без эзотерического тумана. Используешь вопросы про тело, цвета, "
        "погоду, сны. Помогаешь увидеть неожиданные ракурсы. "
        "Примеры: 'Если бы ваш страх был облаком — какое оно?', "
        "'Закройте глаза. Представьте, что желание уже сбылось. Кто вы?'."
    ),
}


# === Модификаторы интенсивности (PRD 4.2) ===

INTENSITY_MODIFIERS: dict[int, str] = {
    1: "ИНТЕНСИВНОСТЬ: 1/5 (едва заметный оттенок, почти нейтральный). Не подчёркивай стиль, говори ровно.",
    2: "ИНТЕНСИВНОСТЬ: 2/5 (лёгкое проявление тона). Один-два характерных приёма, без нажима.",
    3: "ИНТЕНСИВНОСТЬ: 3/5 (умеренно, по умолчанию). Тон слышен, но без крайностей.",
    4: "ИНТЕНСИВНОСТЬ: 4/5 (ярко выраженный тон). Используй характерные приёмы активно.",
    5: "ИНТЕНСИВНОСТЬ: 5/5 (максимальное проявление). Говори так, как будто это твой единственный стиль.",
}


# === Модули детектора по тону × интенсивности (PRD 5.7) ===
# Модуль 3 (телесный) работает только в Тёплом (3-5) и Мягком (1-5).

# Все доступные модули: 1, 2, 3, 4, 5
# Дефолт (без модуля 3): [1, 2, 4, 5]

_DEFAULT_NO_M3: list[int] = [1, 2, 4, 5]
_DEFAULT_WITH_M3: list[int] = [1, 2, 3, 4, 5]


def _make_envelope() -> dict[tuple[Tone, int], list[int]]:
    """Генерирует таблицу ENABLED_MODULES по (тон, интенсивность)."""
    out: dict[tuple[Tone, int], list[int]] = {}

    # WARM: 1-2 без M3, 3-5 с M3
    for i in (1, 2):
        out[(Tone.WARM, i)] = list(_DEFAULT_NO_M3)
    for i in (3, 4, 5):
        out[(Tone.WARM, i)] = list(_DEFAULT_WITH_M3)

    # CLEAR: всегда без M3
    for i in (1, 2, 3, 4, 5):
        out[(Tone.CLEAR, i)] = list(_DEFAULT_NO_M3)

    # BOLD: всегда без M3
    for i in (1, 2, 3, 4, 5):
        out[(Tone.BOLD, i)] = list(_DEFAULT_NO_M3)

    # SOFT: 1-2 частично (только Q9 = модуль 3 включён, но обработка спец),
    #       3-5 полный
    for i in (1, 2, 3, 4, 5):
        out[(Tone.SOFT, i)] = list(_DEFAULT_WITH_M3)

    return out


ENABLED_MODULES: dict[tuple[Tone, int], list[int]] = _make_envelope()


def get_enabled_modules(tone: Tone, intensity: int) -> list[int]:
    """Возвращает список активных модулей детектора для тона и интенсивности."""
    if not 1 <= intensity <= 5:
        raise ValueError(f"intensity должна быть 1..5, получено {intensity}")
    return list(ENABLED_MODULES[(tone, intensity)])


# === Замена Q9 для тонов, где Модуль 3 отключён (PRD 5.7) ===

MODULE3_Q9_REPLACEMENT: dict[Tone, str | None] = {
    Tone.WARM: None,    # M3 включён в warm 3-5; для warm 1-2 замены нет (модуль пропускается)
    Tone.CLEAR: "Опишите желание в 1 факте: что именно вы хотите, без эпитетов?",
    Tone.BOLD: "Что вы сделаете на этой неделе по этому желанию? Назовите конкретное действие.",
    Tone.SOFT: None,    # M3 включён всегда
}


def get_module3_replacement(tone: Tone) -> str | None:
    """Текст замены Q9 для тонов с отключённым Модулем 3. None если не нужна замена."""
    return MODULE3_Q9_REPLACEMENT.get(tone)


# === Кнопки тонов для онбординга (PRD 7.3.1) ===

TONE_BUTTONS: list[dict[str, str]] = [
    {"label": "🫂 Тёплый", "payload": "warm:3", "tone": "warm"},
    {"label": "📊 Чёткий", "payload": "clear:3", "tone": "clear"},
    {"label": "⚡ Смелый", "payload": "bold:3", "tone": "bold"},
    {"label": "🌙 Мягкий", "payload": "soft:3", "tone": "soft"},
]


# === Кнопки выбора старта (PRD 7.3.1) ===

START_BUTTONS: list[dict[str, str]] = [
    {"label": "🟢 Просто поговорить", "payload": "talk", "kind": "start_pick"},
    {"label": "📋 Микро-чекин 3 мин", "payload": "checkin", "kind": "start_pick"},
    {"label": "🎯 Разобрать желание", "payload": "desire", "kind": "start_pick"},
    {"label": "📚 Пройти воркбук", "payload": "workbook", "kind": "start_pick"},
    {"label": "🤷 Не знаю — ты веди", "payload": "unsure", "kind": "start_pick"},
]


# === Стартовый вопрос для «не знаю» по тону (PRD 7.3.1 шаг 4) ===

START_QUESTIONS_BY_TONE: dict[Tone, str] = {
    Tone.WARM: "Что у тебя сейчас на душе?",
    Tone.CLEAR: "Какая у тебя сейчас главная задача?",
    Tone.BOLD: "Что ты откладываешь?",
    Tone.SOFT: "Если бы день сегодня был цветом — какой?",
}


# === Кнопки завершения (PRD 7.2.4) ===

END_BUTTONS: list[dict[str, str]] = [
    {"label": "💾 Сохранить и выйти", "payload": "save", "kind": "end_session"},
    {"label": "✅ Завершить сессию", "payload": "complete", "kind": "end_session"},
]


__all__ = [
    "Tone",
    "TONE_ADDONS",
    "INTENSITY_MODIFIERS",
    "ENABLED_MODULES",
    "get_enabled_modules",
    "get_module3_replacement",
    "TONE_BUTTONS",
    "START_BUTTONS",
    "START_QUESTIONS_BY_TONE",
    "END_BUTTONS",
]
