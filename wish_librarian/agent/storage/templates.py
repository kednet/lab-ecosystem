"""
Markdown / JSON-шаблоны для всех выходных файлов.
"""
from __future__ import annotations

import json
import re
from datetime import datetime
from typing import Any, Optional

from agent.models import (
    AffiliateLink,
    BookInfo,
    ReviewBundle,
    ScientificArticle,
)
from agent.templates import ContentTemplate
from agent.utils.logger import get_logger

logger = get_logger()


# ── metadata.json ───────────────────────────────────────────────
def render_metadata_json(book: BookInfo, extra: dict[str, Any] | None = None) -> str:
    data = book.model_dump(mode="json")
    data["generated_at"] = datetime.utcnow().isoformat() + "Z"
    if extra:
        data.update(extra)
    return json.dumps(data, ensure_ascii=False, indent=2, default=str)


# ── reviews.md ──────────────────────────────────────────────────
def render_reviews_md(book: BookInfo, bundle: ReviewBundle) -> str:
    lines: list[str] = []
    lines.append(f"# 💬 Отзывы: {book.title}")
    lines.append("")
    lines.append(f"> _{book.author}_")
    lines.append("")
    if bundle.average_rating is not None:
        lines.append(f"**Средняя оценка:** {bundle.average_rating} ⭐")
    lines.append(f"**Собрано отзывов:** {bundle.total_reviews}")
    lines.append("")

    if bundle.pros:
        lines.append("## 👍 Что понравилось")
        for p in bundle.pros:
            lines.append(f"- {p}")
        lines.append("")

    if bundle.cons:
        lines.append("## 👎 Что не понравилось")
        for c in bundle.cons:
            lines.append(f"- {c}")
        lines.append("")

    if bundle.reviews:
        lines.append("## 📖 Отзывы читателей")
        lines.append("")
        for i, r in enumerate(bundle.reviews, start=1):
            lines.append(f"### {i}. {r.author}" + (f" — ⭐ {r.rating}" if r.rating else ""))
            lines.append("")
            lines.append(r.text)
            if r.url:
                lines.append("")
                lines.append(f"[🔗 Источник]({r.url})")
            lines.append("")
            lines.append("---")
            lines.append("")
    else:
        lines.append("_Отзывы не найдены._")

    lines.append("")
    lines.append(f"_Сгенерировано WishLibrarian • {datetime.utcnow().isoformat(timespec='seconds')}Z_")
    return "\n".join(lines)


# ── scientific.md ───────────────────────────────────────────────
def render_scientific_md(
    book: BookInfo, articles: list[ScientificArticle]
) -> str:
    lines: list[str] = []
    lines.append(f"# 🔬 Научные статьи по теме: {book.title}")
    lines.append("")
    lines.append(f"_Книга: {book.title} — {book.author}_")
    lines.append("")

    if not articles:
        lines.append("_Научные статьи не найдены._")
    else:
        lines.append(f"Найдено статей: **{len(articles)}**")
        lines.append("")
        for i, a in enumerate(articles, start=1):
            lines.append(f"## {i}. {a.title}")
            lines.append("")
            if a.authors:
                lines.append(f"**Авторы:** {', '.join(a.authors)}")
            if a.year:
                lines.append(f"**Год:** {a.year}")
            if a.journal:
                lines.append(f"**Журнал:** {a.journal}")
            if a.abstract:
                lines.append("")
                lines.append(a.abstract[:600])
            lines.append("")
            lines.append(f"[📄 Читать на КиберЛенинке]({a.url})")
            lines.append("")
            lines.append("---")
            lines.append("")

    lines.append("")
    lines.append(f"_Сгенерировано WishLibrarian • {datetime.utcnow().isoformat(timespec='seconds')}Z_")
    return "\n".join(lines)


# ── buy_links.md ────────────────────────────────────────────────
def render_buy_links_md(
    book: BookInfo, links: list[AffiliateLink]
) -> str:
    lines: list[str] = []
    lines.append(f"# 🛒 Где купить: {book.title}")
    lines.append("")
    lines.append(f"_{book.author}_")
    lines.append("")
    lines.append("Партнёрские ссылки на основные книжные магазины. "
                 "Покупая по этим ссылкам, вы поддерживаете проект WishLibrarian.")
    lines.append("")

    for l in links:
        price = f" — {l.price}" if l.price else ""
        partner = (
            f" `(партнёр: {l.partner_id})`"
            if l.partner_id else " _(без партнёрского ID)_"
        )
        lines.append(f"## {l.store}{price}{partner}")
        lines.append("")
        lines.append(f"[🔗 Перейти в магазин]({l.url})")
        lines.append("")

    lines.append("---")
    lines.append("")
    lines.append(f"_Сгенерировано WishLibrarian • {datetime.utcnow().isoformat(timespec='seconds')}Z_")
    return "\n".join(lines)


# ── Заглушка для practical_tips, если AI недоступен ─────────────
def render_tips_md_fallback(book: BookInfo) -> str:
    return (
        f"# 💡 Практические советы: {book.title}\n\n"
        f"_Контент не сгенерирован Claude (см. logs/)._\n\n"
        f"Опирайтесь на конспект и воркбук этой книги.\n"
    )


# ── Маркер для cover.jpg (если не удалось скачать) ──────────────
def render_cover_note(book: BookInfo) -> str:
    return (
        f"# 📕 Обложка: {book.title}\n\n"
        f"Обложка не была загружена автоматически.\n\n"
        f"**URL обложки:** {book.cover_url or '—'}\n"
        f"**Источник:** {book.source_url}\n"
    )


# ── Пост-процессор для воркбука ─────────────────────────────────────
_HABIT_BLOCK_RE = re.compile(
    r"\[HABIT_NAMES\](.*?)\[/HABIT_NAMES\]", re.DOTALL,
)
_HABIT_LINE_RE = re.compile(r"^\s*\d+\.\s*(.+?)\s*$")


def _extract_habits(llm_output: str) -> list[str]:
    """Извлечь список привычек из блока [HABIT_NAMES]…[/HABIT_NAMES]."""
    m = _HABIT_BLOCK_RE.search(llm_output)
    if not m:
        return []
    out: list[str] = []
    for line in m.group(1).splitlines():
        m2 = _HABIT_LINE_RE.match(line)
        if m2:
            out.append(m2.group(1).strip())
    return [h for h in out if h][:3]


def _extract_self_analysis_questions(llm_output: str) -> list[str]:
    """
    Извлечь список нумерованных вопросов из секции «Упражнение 1. Самоанализ».
    Возвращает до 7 вопросов (до следующей секции ``## ``).
    """
    m = re.search(
        r"##\s+🔍\s+Упражнение\s+1\.\s*Самоанализ\s*(.*?)(?=^##\s|\Z)",
        llm_output,
        re.DOTALL | re.MULTILINE,
    )
    if not m:
        return []
    block = m.group(1)
    questions: list[str] = []
    for line in block.splitlines():
        s = line.strip()
        m2 = re.match(r"^\d+\.\s+(.+)$", s)
        if m2:
            questions.append(m2.group(1).strip())
        elif s and not s.startswith(">") and not s.startswith("-") and questions:
            # продолжение предыдущего вопроса (на случай многострочных формулировок)
            questions[-1] = (questions[-1] + " " + s).strip()
    return questions[:7]


def _render_answer_fields(questions: list[str], lines_per_q: int = 4) -> str:
    """Сгенерировать секцию «📝 Поля для ответов» с подчёркиваниями."""
    if not questions:
        return ""
    sep = "  " + "_" * 70
    parts: list[str] = [
        "## 📝 Поля для ответов",
        "",
        "_Отвечай письменно на вопросы выше. "
        f"По {lines_per_q} строки на вопрос._",
        "",
    ]
    for i, q in enumerate(questions, start=1):
        parts.append(f"{i}. _{q}_")
        for _ in range(lines_per_q):
            parts.append(sep)
        parts.append("")
    return "\n".join(parts)


def _render_habit_grid(habits: list[str], days: int = 30) -> str:
    """Сгенерировать таблицу-трекер привычек (days × len(habits))."""
    # Если привычек не 3 — дополняем заглушками, чтобы колонок было ровно 3
    habit_names = list(habits) + [f"Привычка {i+1}" for i in range(len(habits), 3)]
    habit_names = habit_names[:3]

    header = "| День | " + " | ".join(habit_names) + " |"
    sep    = "|------|" + "|".join(["----------"] * len(habit_names)) + "|"
    rows   = "\n".join(
        f"| {d}   | " + " | ".join([""] * len(habit_names)) + " |"
        for d in range(1, days + 1)
    )
    return "\n".join([header, sep, rows])


def render_workbook_postprocess(
    llm_output: str,
    tpl: ContentTemplate,
    book: BookInfo,
) -> str:
    """
    Пост-обработка ответа LLM для воркбука:

    1. Извлекает блок ``[HABIT_NAMES]…[/HABIT_NAMES]`` и заменяет его на
       полноценную таблицу-трекер 30×3.
    2. Добавляет (или заменяет) секцию ``## 📝 Поля для ответов`` с
       подчёркиваниями для рукописного заполнения.
    3. Удаляет служебные ремарки вида «_Таблица … будет добавлена
       автоматически._».

    Args:
        llm_output: текст, который вернула LLM.
        tpl:        распарсенный шаблон (используется для подсчёта строк).
        book:       метаданные книги (нужны для заголовка таблицы).

    Returns:
        Итоговый markdown для записи в ``workbook.md``.
    """
    # Параметры из frontmatter
    lines_per_q = 4
    grid_days = 30
    for s in tpl.sections:
        if s.id == "answer_fields":
            lines_per_q = int(s.options.get("lines_per_question", 4) or 4)
        elif s.id == "habit_tracker":
            grid_days = int(s.options.get("days", 30) or 30)

    text = llm_output

    # 1) Привычки → таблица
    habits = _extract_habits(text)
    if habits:
        table = _render_habit_grid(habits, days=grid_days)
        text = _HABIT_BLOCK_RE.sub(table, text, count=1)
        # удаляем ремарку о «таблица будет добавлена автоматически»
        text = re.sub(
            r"^> ℹ️ _Таблица.*?автоматически\._\s*\n",
            "",
            text,
            flags=re.MULTILINE,
        )
        # убираем явный заголовок «Привычки для отслеживания:»,
        # заменяя его на короткую подсказку
        text = re.sub(
            r"Привычки для отслеживания:\s*\n",
            "Привычки для отслеживания (отмечай ежедневно):\n\n",
            text,
        )
    else:
        # Нет блока — генерим универсальную таблицу и не падаем
        table = _render_habit_grid([], days=grid_days)
        # вставляем после заголовка секции
        text = re.sub(
            r"(##\s+🔥\s+Трекер привычек[^\n]*\n)"
            r"([^\n]*\n)?",
            r"\1\n" + table + "\n\n",
            text,
            count=1,
        )

    # 2) Поля для ответов — после блока самоанализа
    questions = _extract_self_analysis_questions(text)
    answer_section = _render_answer_fields(questions, lines_per_q=lines_per_q)
    if answer_section:
        # Если секция уже есть (например, LLM сам сгенерил) — заменяем её
        existing = re.search(
            r"##\s+📝\s+Поля для ответов.*?(?=^##\s|\Z)",
            text,
            re.DOTALL | re.MULTILINE,
        )
        if existing:
            text = text[: existing.start()] + answer_section + "\n\n" + text[existing.end():]
        else:
            # иначе вставляем сразу после блока самоанализа
            sa_match = re.search(
                r"(##\s+🔍\s+Упражнение\s+1\.\s*Самоанализ.*?)(?=^##\s|\Z)",
                text,
                re.DOTALL | re.MULTILINE,
            )
            if sa_match:
                insert_at = sa_match.end()
                # убрать служебную ремарку «ℹ️ Раздел … будет добавлен»
                text = re.sub(
                    r"\n> ℹ️ _Раздел «Поля для ответов» будет добавлен автоматически._\n",
                    "\n",
                    text,
                )
                text = text[:insert_at] + "\n" + answer_section + "\n\n" + text[insert_at:]

    # 3) Чистка лишних пустых строк (3+ → 2)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text
