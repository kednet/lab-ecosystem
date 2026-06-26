"""
State machine: валидация и применение переходов.

Источник истины — таблица ALLOWED_TRANSITIONS из core.states.
Любой переход идёт через SessionStateMachine.transition().
"""

from __future__ import annotations

from agent.core.states import (
    ALLOWED_TRANSITIONS,
    InvalidTransitionError,
    SessionState,
)
from agent.storage.models import SessionRow
from agent.storage.repository import Repository
from agent.utils import get_logger

log = get_logger("state_machine")


class SessionStateMachine:
    """Валидирует и применяет переходы, обновляет session.current_state в D1."""

    def __init__(self, repository: Repository) -> None:
        self._repo = repository

    def can_transition(self, from_state: SessionState, to_state: SessionState) -> bool:
        return to_state in ALLOWED_TRANSITIONS.get(from_state, frozenset())

    async def transition(
        self,
        session: SessionRow,
        to_state: SessionState,
        reason: str | None = None,
        cost_delta: float = 0.0,
    ) -> SessionRow:
        """Применить переход. Бросает InvalidTransitionError если запрещён."""
        from_state = SessionState(session.current_state) if session.current_state else None
        if from_state is None:
            # Сессия без состояния (только что создана) — разрешаем в любой
            log.info(
                "state.transition.null_state",
                session_id=session.id,
                to_state=to_state.value,
                reason=reason,
            )
            updated = await self._repo.update_session_state(session.id, to_state.value, cost_delta)
            if updated is None:
                raise RuntimeError(f"transition: session {session.id} исчез")
            return updated

        if not self.can_transition(from_state, to_state):
            log.error(
                "state.transition.invalid",
                session_id=session.id,
                from_state=from_state.value,
                to_state=to_state.value,
                reason=reason,
            )
            raise InvalidTransitionError(
                f"Невозможен переход {from_state.value} → {to_state.value}"
            )

        log.info(
            "state.transition",
            session_id=session.id,
            from_state=from_state.value,
            to_state=to_state.value,
            reason=reason,
        )
        updated = await self._repo.update_session_state(session.id, to_state.value, cost_delta)
        if updated is None:
            raise RuntimeError(f"transition: session {session.id} исчез")
        return updated

    async def transition_to_idle(
        self, session: SessionRow
    ) -> SessionRow:
        """Ленивое завершение: 15 мин без ответа → S_IDLE_SAVED."""
        return await self.transition(
            session,
            SessionState.S_IDLE_SAVED,
            reason="idle_15min",
        )

    async def transition_to_crisis(
        self, session: SessionRow
    ) -> SessionRow:
        """Crisis-detection сработал → S_CRISIS_STOP."""
        return await self.transition(
            session,
            SessionState.S_CRISIS_STOP,
            reason="crisis_detected",
        )

    # === Welcome-back шаблоны (PRD 7.2.3) ===

    @staticmethod
    def welcome_back_template(gap_days: float) -> str:
        """Шаблон приветствия после паузы. gap_days — дни с последней сессии."""
        if gap_days < 1:
            return (
                "Продолжаем с того места. "
                "Если хочешь — напомни, на чём остановились."
            )
        if gap_days < 3:
            return (
                "Привет! В прошлый раз мы остановились на каком-то моменте. "
                "Продолжим?"
            )
        if gap_days < 7:
            return (
                "Привет! Прошло несколько дней с нашей последней сессии. "
                "Хочешь проверить прогресс или начнём новое?"
            )
        if gap_days < 30:
            return (
                "Давно не виделись! У тебя есть активные желания. "
                "Начать с проверки или с новой темы?"
            )
        return (
            "С возвращением! Не помню всех деталей — "
            "хочешь, я вкратце перескажу, что мы делали? "
            "(или начнём с чистого листа)"
        )


__all__ = ["SessionStateMachine"]
