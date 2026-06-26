"""
Тесты state machine: таблица переходов, idle, crisis, welcome_back, idle_timer.
"""

from __future__ import annotations

import asyncio

import pytest
from factories import make_session

from agent.core.idle import IdleTimer
from agent.core.state_machine import SessionStateMachine
from agent.core.states import (
    ALLOWED_TRANSITIONS,
    InvalidTransitionError,
    SessionState,
    is_terminal,
)

# === Полнота таблицы ===

def test_all_11_states_in_table() -> None:
    assert len(SessionState) == 11
    assert set(ALLOWED_TRANSITIONS.keys()) == set(SessionState)


def test_idle_transition_allowed_from_any_state() -> None:
    for state in SessionState:
        if state == SessionState.S_IDLE_SAVED:
            continue  # не петля
        assert SessionState.S_IDLE_SAVED in ALLOWED_TRANSITIONS[state], (
            f"Нет перехода {state} → S_IDLE_SAVED"
        )


def test_crisis_transition_allowed_from_any_state() -> None:
    for state in SessionState:
        if state == SessionState.S_CRISIS_STOP:
            continue
        assert SessionState.S_CRISIS_STOP in ALLOWED_TRANSITIONS[state]


# === Валидные переходы ===

@pytest.mark.asyncio
async def test_valid_transition_onboard_to_dialog(
    state_machine: SessionStateMachine, fake_repo
) -> None:
    session = make_session(current_state="S_ONBOARD")
    fake_repo._sessions[session.id] = session
    updated = await state_machine.transition(session, SessionState.S_DIALOG, reason="tone_picked")
    assert updated.current_state == "S_DIALOG"


@pytest.mark.asyncio
async def test_invalid_transition_raises(state_machine: SessionStateMachine, fake_repo) -> None:
    session = make_session(current_state="S_ONBOARD")
    fake_repo._sessions[session.id] = session
    # S_ONBOARD → S_DETECTOR напрямую запрещён
    with pytest.raises(InvalidTransitionError):
        await state_machine.transition(session, SessionState.S_DETECTOR, reason="bad")


@pytest.mark.asyncio
async def test_transition_with_null_state(state_machine: SessionStateMachine, fake_repo) -> None:
    session = make_session(current_state=None)  # type: ignore[arg-type]
    fake_repo._sessions[session.id] = session
    updated = await state_machine.transition(session, SessionState.S_DIALOG, reason="init")
    assert updated.current_state == "S_DIALOG"


# === can_transition ===

def test_can_transition_basic() -> None:
    sm = SessionStateMachine.__new__(SessionStateMachine)  # без __init__
    sm._repo = None
    assert sm.can_transition(SessionState.S_ONBOARD, SessionState.S_DIALOG) is True
    assert sm.can_transition(SessionState.S_ONBOARD, SessionState.S_DETECTOR) is False


# === Welcome-back шаблоны (PRD 7.2.3) ===

def test_welcome_back_less_1_day() -> None:
    text = SessionStateMachine.welcome_back_template(0.5)
    assert "Продолжаем" in text or "продолжим" in text.lower()


def test_welcome_back_1_to_3_days() -> None:
    text = SessionStateMachine.welcome_back_template(2)
    assert "Привет" in text
    assert "остановились" in text.lower() or "продолж" in text.lower()


def test_welcome_back_3_to_7_days() -> None:
    text = SessionStateMachine.welcome_back_template(5)
    assert "Привет" in text
    assert "дня" in text.lower() or "сессии" in text.lower()


def test_welcome_back_7_to_30_days() -> None:
    text = SessionStateMachine.welcome_back_template(15)
    assert "Давно" in text or "давно" in text.lower()
    assert "проверк" in text.lower() or "новое" in text.lower() or "новой" in text.lower()


def test_welcome_back_over_30_days() -> None:
    text = SessionStateMachine.welcome_back_template(45)
    assert "возвращением" in text.lower() or "возвращ" in text.lower()
    assert "перескажу" in text.lower() or "листа" in text.lower()


# === is_terminal ===

def test_is_terminal() -> None:
    assert is_terminal(SessionState.S_IDLE_SAVED) is True
    assert is_terminal(SessionState.S_CRISIS_STOP) is True
    assert is_terminal(SessionState.S_DIALOG) is False
    assert is_terminal(SessionState.S_DETECTOR) is False


# === IdleTimer ===

@pytest.mark.asyncio
async def test_idle_timer_fires_after_timeout() -> None:
    timer = IdleTimer(timeout_sec=1)
    fired = []

    async def cb() -> None:
        fired.append(True)

    timer.arm(1, cb)
    assert timer.is_armed(1)
    await asyncio.sleep(1.3)
    assert fired == [True]
    assert not timer.is_armed(1)


@pytest.mark.asyncio
async def test_idle_timer_disarm_prevents_fire() -> None:
    timer = IdleTimer(timeout_sec=1)
    fired = []

    async def cb() -> None:
        fired.append(True)

    timer.arm(1, cb)
    await asyncio.sleep(0.3)
    timer.disarm(1)
    await asyncio.sleep(0.8)
    assert fired == []


@pytest.mark.asyncio
async def test_idle_timer_reschedule() -> None:
    timer = IdleTimer(timeout_sec=1)
    fired = []

    async def cb() -> None:
        fired.append(True)

    timer.arm(1, cb)
    await asyncio.sleep(0.7)
    # Перезапускаем — старая задача отменяется
    timer.arm(1, cb)
    await asyncio.sleep(0.7)
    # Если бы reschedule не работал — fired был бы [True] к этому моменту
    assert fired == []
    await asyncio.sleep(0.5)
    assert fired == [True]
