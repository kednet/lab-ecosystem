"""
Парсер workbook.md → структура Workbook (Phase 4).

Источник формата: wishlibrarian output `<book>/workbook.md`. Структура стабильная:
    # ✍️ ВОРКБУК: <title>
    ## 🔍 Упражнение N. <title>    ← шаг (N — 1-индексированный, внутри 0-индекс)
    ## ✍️ Упражнение N. <title>      ← другой префикс
    ## 💭 Рефлексия                  ← (опц.) рефлексия
    ## 🎁 Бонус                      ← (опц.) бонус

Pure-Python, без I/O. Без зависимостей от markdown-парсера.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

# === Regex-паттерны (anchor на начало строки) ===

# Title: `# ✍️ ВОРКБУК: Тестовая книга`
_TITLE_RE = re.compile(r"^#\s*✍️\s*ВО?Р?К?БУ?К?\s*:?\s*(.+?)\s*$", re.IGNORECASE | re.MULTILINE)

# Step: heading вида `🔍 Упражнение 1. Самоанализ` (БЕЗ `##` — отдано split_h2_blocks)
# Поддерживаем любой эмодзи/префикс перед словом "Упражнение" и после.
_STEP_RE = re.compile(
    r"^[^\n]*?Упражнение\s+(\d+)\.\s*([^\n]+)$",
)

# Reflection: `💭 Рефлексия (через 30 дней)` или `✍️ Рефлексия`
_REFLECTION_RE = re.compile(
    r"^[^\n]*?Рефлексия[^\n]*$",
)

# Bonus: `🎁 Бонус: ежедневные микро-привычки`
_BONUS_RE = re.compile(
    r"^[^\n]*?Бонус[^\n]*$",
)

# Любой `##`-заголовок (для разделения body по блокам)
_H2_RE = re.compile(r"^##\s+([^\n]+)$", re.MULTILINE)

# Нумерованный список или чек-бокс = «есть вопросы»
_QUESTIONS_RE = re.compile(r"(?m)^\s*(\d+\.|-\s*\[\s*\])")


# === Data classes ===

@dataclass(frozen=True)
class WorkbookStep:
    """Один шаг воркбука (один блок `## Упражнение N`)."""

    index: int           # 0-based
    title: str           # "Самоанализ" (без эмодзи и нумерации, как есть после точки)
    body: str            # сырой markdown: вопросы / чек-боксы / таблица
    has_questions: bool  # содержит нумерованный список или чек-боксы


@dataclass(frozen=True)
class Workbook:
    """Распарсенный воркбук."""

    slug: str
    title: str
    steps: tuple[WorkbookStep, ...]
    reflection: str | None  # raw markdown секции "## Рефлексия" (без заголовка)
    bonus: str | None       # raw markdown секции "## Бонус" (без заголовка)


# === Helpers ===

def _split_h2_blocks(text: str) -> list[tuple[str, str]]:
    """Разбивает текст по `##`-заголовкам.

    Возвращает список (heading_text, body_text) — где heading это строка
    заголовка (с `##`), а body — текст до следующего `##` или до конца.
    Перед первым `##` — преамбула (title, описание) — отбрасывается.
    """
    matches = list(_H2_RE.finditer(text))
    if not matches:
        return []
    blocks: list[tuple[str, str]] = []
    for i, m in enumerate(matches):
        heading = m.group(1).strip()
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        body = text[start:end].strip()
        blocks.append((heading, body))
    return blocks


# === Main entrypoint ===

def parse_workbook(slug: str, text: str) -> Workbook:
    """Парсит содержимое workbook.md в Workbook.

    Args:
        slug: идентификатор книги (= basename директории).
        text: полный текст файла.

    Raises:
        ValueError: если title не найден или нет ни одного шага.
    """
    # Title
    title_m = _TITLE_RE.search(text)
    if title_m is None:
        raise ValueError(
            f"workbook.md для slug={slug!r} не содержит заголовок '# ✍️ ВОРКБУК: <title>'"
        )
    title = title_m.group(1).strip()

    # Разбиваем по `##`-заголовкам
    blocks = _split_h2_blocks(text)

    # Шаги, рефлексия, бонус
    steps: list[WorkbookStep] = []
    reflection: str | None = None
    bonus: str | None = None
    step_counter = 0
    for heading, body in blocks:
        step_m = _STEP_RE.match(heading)
        refl_m = _REFLECTION_RE.match(heading)
        bon_m = _BONUS_RE.match(heading)
        if step_m:
            step_title = step_m.group(2).strip()
            # Если заголовок "## Упражнение 1." (без title) — оставляем title пустым
            # (на практике так не бывает, но защищаемся)
            steps.append(
                WorkbookStep(
                    index=step_counter,
                    title=step_title,
                    body=body,
                    has_questions=bool(_QUESTIONS_RE.search(body)),
                )
            )
            step_counter += 1
        elif refl_m:
            reflection = body
        elif bon_m:
            bonus = body

    if not steps:
        raise ValueError(
            f"workbook.md для slug={slug!r} не содержит ни одного "
            f"'## Упражнение N. <title>'"
        )

    return Workbook(
        slug=slug,
        title=title,
        steps=tuple(steps),
        reflection=reflection,
        bonus=bonus,
    )


__all__ = [
    "WorkbookStep",
    "Workbook",
    "parse_workbook",
]
