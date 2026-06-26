"""
Декомпозиция: 4 типа дедлайнов (3/7/14/30 дней), payload-схема, кнопки.

Источник: PRD v2.0 раздел 5 — типы дедлайнов micro_test/first_step/trial/mini_project.

Этот модуль — pure-Python константы и парсеры, без зависимостей от репозитория или AI.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

# === 4 типа дедлайнов (PRD) ===

DEADLINE_DAYS: dict[str, int] = {
    "micro_test": 3,
    "first_step": 7,
    "trial": 14,
    "mini_project": 30,
}

VALID_DEADLINE_TYPES: frozenset[str] = frozenset(DEADLINE_DAYS.keys())


def days_for(deadline_type: str) -> int:
    """Количество дней для типа дедлайна. Raises ValueError для неизвестного типа."""
    if deadline_type not in DEADLINE_DAYS:
        raise ValueError(
            f"Неизвестный deadline_type '{deadline_type}'. "
            f"Допустимые: {sorted(DEADLINE_DAYS)}"
        )
    return DEADLINE_DAYS[deadline_type]


def compute_deadline(deadline_type: str, now: datetime | None = None) -> str:
    """Возвращает ISO-строку дедлайна (UTC) = now() + N дней.

    По умолчанию now() — текущее UTC-время. Параметр `now` нужен для тестов.
    """
    if deadline_type not in DEADLINE_DAYS:
        raise ValueError(
            f"Неизвестный deadline_type '{deadline_type}'. "
            f"Допустимые: {sorted(DEADLINE_DAYS)}"
        )
    base = now or datetime.now(UTC)
    deadline = base + timedelta(days=DEADLINE_DAYS[deadline_type])
    return deadline.isoformat()


# === Парсинг payload ===

@dataclass(frozen=True)
class DecompAction:
    """Результат парсинга payload-кнопки декомпозиции.

    action ∈ {type, done, edit, skip, add_own, new_desire, unknown}
    """

    action: str
    step_id: int | None = None
    deadline_type: str | None = None


def parse_decomp_payload(payload: str) -> DecompAction:
    """Парсит payload из inline-кнопки декомпозии в структурированное действие.

    Поддерживаемые форматы:
    - `decomp_type:<type>` → action=type, deadline_type=<type>
    - `step_done:<id>` / `step_edit:<id>` / `step_skip:<id>` → action + step_id
    - `add_own` → action=add_own
    - `new_desire` → action=new_desire
    - `resume` / `cancel` / `new_desire` → action=соответствующее

    Неизвестный payload → action=unknown, без id/type.
    """
    if not payload:
        return DecompAction(action="unknown")
    text = payload.strip()
    if ":" in text:
        head, _, rest = text.partition(":")
        head = head.strip()
        rest = rest.strip()
        if head == "decomp_type" and rest in VALID_DEADLINE_TYPES:
            return DecompAction(action="type", deadline_type=rest)
        if head in ("step_done", "step_edit", "step_skip", "step_undo_done", "step_undo_skip"):
            try:
                sid = int(rest)
            except ValueError:
                return DecompAction(action="unknown")
            action = head[len("step_"):]  # done / edit / skip / undo_done / undo_skip
            return DecompAction(action=action, step_id=sid)
    # Простые payload без двоеточия
    if text in ("add_own", "new_desire", "cancel", "resume"):
        return DecompAction(action=text)
    return DecompAction(action="unknown")


# === Кнопки ===

DECOMP_TYPE_BUTTONS: list[dict[str, str]] = [
    {
        "label": "🌱 Микро-тест (3 дня)",
        "payload": "decomp_type:micro_test",
        "kind": "decomp_type",
    },
    {
        "label": "🚶 Первый шаг (7 дней)",
        "payload": "decomp_type:first_step",
        "kind": "decomp_type",
    },
    {
        "label": "🏃 Проба (14 дней)",
        "payload": "decomp_type:trial",
        "kind": "decomp_type",
    },
    {
        "label": "🗻 Мини-проект (30 дней)",
        "payload": "decomp_type:mini_project",
        "kind": "decomp_type",
    },
]

ADD_OWN_BUTTON: dict[str, str] = {
    "label": "+ свой шаг",
    "payload": "add_own",
    "kind": "decomp_add_own",
}

NEW_DESIRE_BUTTON: dict[str, str] = {
    "label": "🎯 Новое желание",
    "payload": "new_desire",
    "kind": "new_desire",
}

BACK_TO_DIALOG_BUTTON: dict[str, str] = {
    "label": "💬 В диалог",
    "payload": "resume",
    "kind": "resume",
}


def step_action_buttons(step_id: int, status: str = "pending") -> list[dict[str, str]]:
    """Кнопки действий над конкретным шагом, в зависимости от текущего статуса.

    pending   → [✓ готово, ✏️ редактировать, ⏭ пропустить]
    done      → [↩ отменить готовность, ✏️ редактировать]
    skipped   → [↩ вернуть в работу, ✏️ редактировать]
    """
    if status == "done":
        return [
            {
                "label": "↩ Отменить",
                "payload": f"step_undo_done:{step_id}",
                "kind": "step_undo_done",
            },
            {
                "label": "✏️ Редактировать",
                "payload": f"step_edit:{step_id}",
                "kind": "step_edit",
            },
        ]
    if status == "skipped":
        return [
            {
                "label": "↩ Вернуть в работу",
                "payload": f"step_undo_skip:{step_id}",
                "kind": "step_undo_skip",
            },
            {
                "label": "✏️ Редактировать",
                "payload": f"step_edit:{step_id}",
                "kind": "step_edit",
            },
        ]
    # pending (дефолт)
    return [
        {
            "label": "✓ Готово",
            "payload": f"step_done:{step_id}",
            "kind": "step_done",
        },
        {
            "label": "✏️ Редактировать",
            "payload": f"step_edit:{step_id}",
            "kind": "step_edit",
        },
        {
            "label": "⏭ Пропустить",
            "payload": f"step_skip:{step_id}",
            "kind": "step_skip",
        },
    ]


__all__ = [
    "DEADLINE_DAYS",
    "VALID_DEADLINE_TYPES",
    "days_for",
    "compute_deadline",
    "DecompAction",
    "parse_decomp_payload",
    "DECOMP_TYPE_BUTTONS",
    "ADD_OWN_BUTTON",
    "NEW_DESIRE_BUTTON",
    "BACK_TO_DIALOG_BUTTON",
    "step_action_buttons",
]
