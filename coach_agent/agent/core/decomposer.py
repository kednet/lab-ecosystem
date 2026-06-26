"""
DecomposerService — генерация шагов декомпозиции через AI tool_use + ручной ввод.

Phase 5: AI предлагает 3-7 черновых шагов через tool_use add_step. Юзер может
добавлять свои, отмечать done/skip, редактировать. При завершении всех шагов
(all_done=True) SessionService переходит в S_ACHIEVE.
"""

from __future__ import annotations

from agent.ai.factory import AIClient, AIError, AIResponse, AIUnconfiguredError
from agent.ai.prompts import ContextBlock, build_system_prompt
from agent.ai.tools import TOOL_SCHEMAS, ToolDispatcher
from agent.core.decomp import (
    ADD_OWN_BUTTON,
    BACK_TO_DIALOG_BUTTON,
    DECOMP_TYPE_BUTTONS,
    NEW_DESIRE_BUTTON,
    VALID_DEADLINE_TYPES,
    compute_deadline,
    days_for,
    parse_decomp_payload,
    step_action_buttons,
)
from agent.core.tones import Tone
from agent.storage.models import DesireRow, DesireStepRow
from agent.storage.repository import Repository
from agent.utils import get_logger

log = get_logger("decomposer")


# === Промпт для AI-генерации шагов ===

DECOMPOSE_PROMPT: str = (
    "Ты помогаешь клиенту разбить желание на конкретные шаги.\n\n"
    "Желание: {title}\n"
    "Горизонт (deadline_type): {deadline_type} — {days} дней.\n\n"
    "Сгенерируй от 3 до 7 конкретных, измеримых шагов, каждый из которых:\n"
    "- понятен без контекста (что именно сделать)\n"
    "- реалистичен за указанный горизонт\n"
    "- имеет явный результат (что увидим/получим)\n\n"
    "Используй tool `add_step` для каждого шага. "
    "В deadline_type передай '{deadline_type}'.\n"
    "После всех tool_use — дай клиенту короткое подтверждение (1-2 предложения)."
)


class DecomposerService:
    """Координатор декомпозиции: AI-черновик + ручной ввод + per-step действия."""

    def __init__(
        self,
        repository: Repository,
        ai_client: AIClient | None,
        tool_dispatcher: ToolDispatcher,
    ) -> None:
        self._repo = repository
        self._ai = ai_client
        self._dispatcher = tool_dispatcher
        # mode per session: None | 'awaiting_step_text' | 'awaiting_step_edit:<id>'
        self._mode: dict[int, str] = {}

    # === AI-генерация черновика ===

    async def propose_steps(
        self,
        desire: DesireRow,
        deadline_type: str,
        tone: Tone,
        intensity: int,
    ) -> list[int]:
        """Зовёт AI для генерации 3-7 шагов через tool_use add_step.

        Возвращает список созданных step_id. При AIError / unconfigured / no tool_calls
        возвращает пустой список (юзер вводит вручную).
        """
        if deadline_type not in VALID_DEADLINE_TYPES:
            raise ValueError(f"Неизвестный deadline_type: {deadline_type}")
        if self._ai is None:
            log.warning("decomposer.no_ai", desire_id=desire.id)
            return []

        system = build_system_prompt(
            tone, intensity,
            ContextBlock(active_desire_title=desire.title, channel="web"),
        )
        user_msg = DECOMPOSE_PROMPT.format(
            title=desire.title,
            deadline_type=deadline_type,
            days=days_for(deadline_type),
        )
        try:
            resp: AIResponse = await self._ai.complete(
                system=system,
                messages=[{"role": "user", "content": user_msg}],
                tools=TOOL_SCHEMAS if self._ai.supports_tools() else None,
                max_tokens=1500,
            )
        except (AIError, AIUnconfiguredError) as e:
            log.warning("decomposer.ai_failed", desire_id=desire.id, error=str(e))
            return []

        # Диспатчим tool_use блоки
        step_ids: list[int] = []
        for tc in resp.tool_calls:
            if tc.name == "add_step":
                # Подмешиваем deadline_type явно (AI может не передать)
                if "deadline_type" not in tc.input:
                    tc.input["deadline_type"] = deadline_type
                result = await self._dispatcher.dispatch(tc.name, tc.input)
                if result.get("status") == "ok" and "step_id" in result:
                    step_ids.append(int(result["step_id"]))
        return step_ids

    # === Manual ===

    async def create_manual_step(
        self, desire_id: int, title: str, deadline_type: str
    ) -> DesireStepRow:
        """Создаёт один шаг вручную (юзер нажал «+ свой»)."""
        if deadline_type not in VALID_DEADLINE_TYPES:
            raise ValueError(f"Неизвестный deadline_type: {deadline_type}")
        title = title.strip()
        if not title:
            raise ValueError("Пустой текст шага")
        deadline = compute_deadline(deadline_type)
        return await self._repo.create_desire_step(
            desire_id=desire_id, title=title,
            deadline=deadline, deadline_type=deadline_type,
        )

    async def edit_step(self, step_id: int, new_title: str) -> DesireStepRow | None:
        new_title = new_title.strip()
        if not new_title:
            raise ValueError("Пустой текст шага")
        return await self._repo.update_step(step_id, title=new_title)

    async def complete_step(self, step_id: int) -> DesireStepRow | None:
        return await self._repo.mark_step_done(step_id)

    async def skip_step(self, step_id: int) -> DesireStepRow | None:
        return await self._repo.mark_step_skipped(step_id)

    async def undo_done(self, step_id: int) -> DesireStepRow | None:
        """Снимает отметку done (status=pending)."""
        return await self._repo.set_step_status(step_id, "pending", done_at=None)

    async def undo_skip(self, step_id: int) -> DesireStepRow | None:
        """Снимает skip (status=pending)."""
        return await self._repo.set_step_status(step_id, "pending", done_at=None)

    async def all_done(self, desire_id: int) -> bool:
        """Все шаги либо done, либо skipped + есть хотя бы 1 done."""
        pending = await self._repo.count_steps_by_status(desire_id, "pending")
        if pending > 0:
            return False
        done = await self._repo.count_steps_by_status(desire_id, "done")
        return done > 0

    # === UI helpers ===

    def type_buttons(self) -> list[dict[str, str]]:
        return list(DECOMP_TYPE_BUTTONS) + [ADD_OWN_BUTTON]

    def add_own_button(self) -> dict[str, str]:
        return ADD_OWN_BUTTON

    def achieve_buttons(self) -> list[dict[str, str]]:
        return [NEW_DESIRE_BUTTON, BACK_TO_DIALOG_BUTTON]

    def set_mode(self, session_id: int, mode: str | None) -> None:
        if mode is None:
            self._mode.pop(session_id, None)
        else:
            self._mode[session_id] = mode

    def get_mode(self, session_id: int) -> str | None:
        return self._mode.get(session_id)

    def parse_payload(self, payload: str):
        return parse_decomp_payload(payload)

    def step_buttons(self, step_id: int, status: str) -> list[dict[str, str]]:
        return step_action_buttons(step_id, status)


__all__ = [
    "DecomposerService",
    "DECOMPOSE_PROMPT",
]
