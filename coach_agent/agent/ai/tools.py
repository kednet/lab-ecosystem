"""
Tool-calling: схемы для Anthropic + диспетчер.

Phase 5: add_step реально создаёт шаги в D1, save_desire остаётся deferred
(желания создаются через /coach/desire endpoint, а не tool_use).
"""

from __future__ import annotations

from typing import Any

from agent.core.decomp import VALID_DEADLINE_TYPES, compute_deadline
from agent.storage.repository import Repository
from agent.utils import get_logger

log = get_logger("tools")


# === JSON Schemas для Anthropic tool_use ===

TOOL_SCHEMAS: list[dict[str, Any]] = [
    {
        "name": "save_desire",
        "description": (
            "Сохранить новое желание клиента в его профиль. "
            "Используй, когда клиент явно назвал, чего хочет "
            "('хочу X', 'мечтаю о Y')."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "title": {
                    "type": "string",
                    "description": "Краткая формулировка желания (1-7 слов)",
                },
                "kind_hint": {
                    "type": "string",
                    "enum": ["imposed", "true", "mixed", "unknown"],
                    "description": "Гипотеза коуча о природе (unknown если не уверен)",
                },
            },
            "required": ["title"],
        },
    },
    {
        "name": "add_step",
        "description": (
            "Добавить под-шаг к существующему желанию. "
            "Используй после декомпозиции, когда клиент согласился с шагом."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "desire_id": {"type": "integer", "description": "ID желания"},
                "title": {"type": "string", "description": "Что нужно сделать"},
                "deadline_type": {
                    "type": "string",
                    "enum": ["micro_test", "first_step", "trial", "mini_project"],
                    "description": (
                        "Тип дедлайна: micro_test (3д), first_step (7д), "
                        "trial (14д), mini_project (30д)"
                    ),
                },
            },
            "required": ["desire_id", "title", "deadline_type"],
        },
    },
    {
        "name": "mark_step_done",
        "description": "Отметить под-шаг как выполненный.",
        "input_schema": {
            "type": "object",
            "properties": {
                "step_id": {"type": "integer", "description": "ID под-шага"},
            },
            "required": ["step_id"],
        },
    },
]


# === Диспетчер ===

class ToolDispatcher:
    """Маппинг tool_name → repository-метод. Все async."""

    def __init__(self, repository: Repository) -> None:
        self._repo = repository

    async def dispatch(self, tool_name: str, tool_input: dict) -> dict[str, Any]:
        log.info("tools.dispatch", tool=tool_name, input=str(tool_input)[:200])
        if tool_name == "save_desire":
            # Желания создаются через /coach/desire endpoint (Phase 1).
            # Через tool_use не вызывается — отдаём deferred, чтобы AI не ломал флоу.
            return {"status": "deferred", "reason": "use /coach/desire endpoint"}
        if tool_name == "add_step":
            return await self._add_step(tool_input)
        if tool_name == "mark_step_done":
            return await self._mark_step_done(tool_input)
        return {"status": "unknown_tool", "tool": tool_name}

    async def _add_step(self, args: dict) -> dict[str, Any]:
        desire_id = args.get("desire_id")
        title = (args.get("title") or "").strip()
        deadline_type = args.get("deadline_type")
        if not desire_id or not title:
            return {"status": "error", "error": "desire_id and title required"}
        if deadline_type not in VALID_DEADLINE_TYPES:
            return {
                "status": "error",
                "error": f"invalid deadline_type: {deadline_type}",
            }
        deadline = compute_deadline(deadline_type)
        step = await self._repo.create_desire_step(
            desire_id=int(desire_id),
            title=title,
            deadline=deadline,
            deadline_type=deadline_type,
        )
        return {
            "status": "ok",
            "step_id": step.id,
            "deadline": step.deadline,
        }

    async def _mark_step_done(self, args: dict) -> dict[str, Any]:
        step_id = args.get("step_id")
        if not step_id:
            return {"status": "error", "error": "step_id required"}
        step = await self._repo.mark_step_done(int(step_id))
        return {"status": "ok", "step": step.model_dump() if step else None}


__all__ = ["TOOL_SCHEMAS", "ToolDispatcher"]
