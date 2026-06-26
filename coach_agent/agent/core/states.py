"""
Состояния сессии и таблица переходов.

Источник истины: PRD v2.0 раздел 7.2.
"""

from __future__ import annotations

from enum import StrEnum


class SessionState(StrEnum):
    """11 состояний сессии (PRD 7.2.1)."""

    S_ONBOARD = "S_ONBOARD"
    S_DIALOG = "S_DIALOG"
    S_DESIRE_DECOMP = "S_DESIRE_DECOMP"
    S_DETECTOR = "S_DETECTOR"
    S_DECISION = "S_DECISION"
    S_RELEASE = "S_RELEASE"
    S_DECOMP = "S_DECOMP"
    S_WORKBOOK = "S_WORKBOOK"
    S_ACHIEVE = "S_ACHIEVE"
    S_IDLE_SAVED = "S_IDLE_SAVED"
    S_CRISIS_STOP = "S_CRISIS_STOP"


class TransitionTrigger(StrEnum):
    """Триггеры переходов между состояниями."""

    TONE_PICKED = "tone_picked"
    USER_DESIRE = "user_desire"
    WORKBOOK_CMD = "workbook_cmd"
    DETECTOR_CMD = "detector_cmd"
    DETECTOR_START = "detector_start"
    VERDICT = "verdict"
    ALL_STEPS_DONE = "all_steps_done"
    IDLE_15MIN = "idle_15min"
    CRISIS_DETECTED = "crisis_detected"
    RESUME = "resume"
    USER_PAUSED = "user_paused"
    COMPLETED = "completed"
    USER_CANCEL = "user_cancel"
    START_PICKED = "start_picked"


# === Таблица разрешённых переходов (PRD 7.2.2) ===
#
# Из любого состояния → S_IDLE_SAVED (idle) и S_CRISIS_STOP (crisis) — добавляем явно.
# Из любого состояния → S_CRISIS_STOP — инвариант безопасности.
# S_DIALOG → S_DESIRE_DECOMP (user_desire)
# S_DIALOG → S_WORKBOOK (workbook_cmd) — зарезервировано для Phase 4
# S_DIALOG → S_ONBOARD — сброс через /reset onboarding
# S_ONBOARD → S_DIALOG (tone_picked)
# S_DESIRE_DECOMP → S_DETECTOR (detector_cmd или detector_start)
# S_DETECTOR → S_DECISION (verdict)
# S_DECISION → S_RELEASE (verdict imposed/mostly_imposed)
# S_DECISION → S_DECOMP (verdict true/mostly_true)
# S_DECISION → S_DESIRE_DECOMP (клиент не согласен)
# S_DECOMP → S_ACHIEVE (all_steps_done)
# любое → S_IDLE_SAVED (idle_15min)
# любое → S_CRISIS_STOP (crisis_detected)
# S_IDLE_SAVED → S_DIALOG (resume)
# S_CRISIS_STOP → S_DIALOG (start)


_BASE_TRANSITIONS: dict[SessionState, frozenset[SessionState]] = {
    SessionState.S_ONBOARD: frozenset({
        SessionState.S_DIALOG,
    }),
    SessionState.S_DIALOG: frozenset({
        SessionState.S_DESIRE_DECOMP,
        SessionState.S_DETECTOR,  # /detector команда
        SessionState.S_WORKBOOK,
        SessionState.S_ONBOARD,  # /reset onboarding
        SessionState.S_DECOMP,  # /decompose команда (Phase 5)
    }),
    SessionState.S_DESIRE_DECOMP: frozenset({
        SessionState.S_DETECTOR,
        SessionState.S_DIALOG,  # клиент передумал
    }),
    SessionState.S_DETECTOR: frozenset({
        SessionState.S_DECISION,
    }),
    SessionState.S_DECISION: frozenset({
        SessionState.S_RELEASE,
        SessionState.S_DECOMP,
        SessionState.S_DESIRE_DECOMP,  # хочет пересмотреть
    }),
    SessionState.S_RELEASE: frozenset({
        SessionState.S_DIALOG,
    }),
    SessionState.S_DECOMP: frozenset({
        SessionState.S_ACHIEVE,
        SessionState.S_DIALOG,  # клиент передумал разбивать
    }),
    SessionState.S_WORKBOOK: frozenset({
        SessionState.S_DIALOG,  # /cancel workbook
    }),
    SessionState.S_ACHIEVE: frozenset({
        SessionState.S_DIALOG,
    }),
    SessionState.S_IDLE_SAVED: frozenset({
        SessionState.S_DIALOG,
    }),
    SessionState.S_CRISIS_STOP: frozenset({
        SessionState.S_DIALOG,
        SessionState.S_ONBOARD,  # /start возвращает в онбординг
    }),
}


# === Финальные переходы: добавляем "любое → S_IDLE_SAVED" и "любое → S_CRISIS_STOP" ===

def _build_allowed_transitions() -> dict[SessionState, frozenset[SessionState]]:
    out: dict[SessionState, frozenset[SessionState]] = {}
    set(SessionState)
    for state in SessionState:
        base = _BASE_TRANSITIONS.get(state, frozenset())
        # IDLE и CRISIS — доступны из любого состояния (кроме самого IDLE, чтобы не было петли)
        extra: set[SessionState] = set()
        if state != SessionState.S_IDLE_SAVED:
            extra.add(SessionState.S_IDLE_SAVED)
        if state != SessionState.S_CRISIS_STOP:
            extra.add(SessionState.S_CRISIS_STOP)
        out[state] = frozenset(base | extra)
    return out


ALLOWED_TRANSITIONS: dict[SessionState, frozenset[SessionState]] = _build_allowed_transitions()


class InvalidTransitionError(ValueError):
    """Попытка перейти в состояние, недостижимое из текущего."""


def is_terminal(state: SessionState) -> bool:
    """Состояние, в котором сессия фактически завершена (не требует немедленного ответа)."""
    return state in {
        SessionState.S_IDLE_SAVED,
        SessionState.S_CRISIS_STOP,
    }


def is_detector_active(state: SessionState) -> bool:
    """Сессия внутри детектора (нужны структурированные ответы)."""
    return state == SessionState.S_DETECTOR


# === Маппинг trigger → ожидаемый to_state (для валидации на уровне вызова) ===

TRIGGER_TO_STATE: dict[TransitionTrigger, SessionState] = {
    TransitionTrigger.TONE_PICKED: SessionState.S_DIALOG,
    TransitionTrigger.WORKBOOK_CMD: SessionState.S_WORKBOOK,
    TransitionTrigger.DETECTOR_CMD: SessionState.S_DETECTOR,
    TransitionTrigger.DETECTOR_START: SessionState.S_DETECTOR,
    TransitionTrigger.VERDICT: SessionState.S_DECISION,
    TransitionTrigger.ALL_STEPS_DONE: SessionState.S_ACHIEVE,
    TransitionTrigger.IDLE_15MIN: SessionState.S_IDLE_SAVED,
    TransitionTrigger.CRISIS_DETECTED: SessionState.S_CRISIS_STOP,
    TransitionTrigger.RESUME: SessionState.S_DIALOG,
    TransitionTrigger.USER_PAUSED: SessionState.S_IDLE_SAVED,
    TransitionTrigger.COMPLETED: SessionState.S_DIALOG,  # после summary → в dialog
    TransitionTrigger.USER_CANCEL: SessionState.S_DIALOG,
    TransitionTrigger.START_PICKED: SessionState.S_DIALOG,
    TransitionTrigger.USER_DESIRE: SessionState.S_DESIRE_DECOMP,
}


__all__ = [
    "SessionState",
    "TransitionTrigger",
    "ALLOWED_TRANSITIONS",
    "InvalidTransitionError",
    "is_terminal",
    "is_detector_active",
    "TRIGGER_TO_STATE",
]
