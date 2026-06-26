"""
Тесты для Phase 8: cost budget в SessionService.

Бюджет $1/сессия (настраивается). Превышение → friendly text, AI НЕ вызывается.
"""

from __future__ import annotations

import pytest

from agent.core.session import SessionService


@pytest.mark.asyncio
async def test_cost_budget_blocks_excess(
    session_service: SessionService, fake_repo, fake_ai
) -> None:
    """Если накопленный cost > budget → AI не вызывается, возвращается friendly text."""
    from agent.storage.models import ClientRow

    fake_repo._clients[1] = ClientRow(
        id=1, email="c1@local", name=None,
        current_tone="warm", tone_intensity=3,
        timezone="Europe/Moscow", push_enabled=1, push_time="10:00",
        onboarding_state="tone_picked",
        created_at="2026-06-10T00:00:00+00:00",
        last_seen_at="2026-06-10T00:00:00+00:00",
        subscription_status="active",
    )
    client = await session_service._repo.get_client_by_id(1)
    # Создаём сессию
    fake_ai.push_response("Привет!")
    await session_service.process_message(client, "Привет", channel="web")
    sess = await fake_repo.get_active_session(1)
    assert sess is not None
    # Имитируем накопление cost выше budget
    session_service._session_cost[sess.id] = 1.5
    session_service._session_cost_budget = 1.0

    call_count_before = fake_ai.call_count
    resp = await session_service.process_message(
        client, "Как дела?", channel="web"
    )
    # AI НЕ вызван
    assert fake_ai.call_count == call_count_before
    # Возвращён friendly text про бюджет
    assert "бюджет" in resp.text.lower() or "budget" in resp.text.lower()


@pytest.mark.asyncio
async def test_cost_budget_allows_under_budget(
    session_service: SessionService, fake_repo, fake_ai
) -> None:
    """Cost < budget → AI вызывается нормально."""
    from agent.storage.models import ClientRow

    fake_repo._clients[1] = ClientRow(
        id=1, email="c1@local", name=None,
        current_tone="warm", tone_intensity=3,
        timezone="Europe/Moscow", push_enabled=1, push_time="10:00",
        onboarding_state="tone_picked",
        created_at="2026-06-10T00:00:00+00:00",
        last_seen_at="2026-06-10T00:00:00+00:00",
        subscription_status="active",
    )
    client = await session_service._repo.get_client_by_id(1)
    fake_ai.push_response("Привет!")
    await session_service.process_message(client, "Привет", channel="web")
    sess = await fake_repo.get_active_session(1)
    assert sess is not None
    # Малый cost — под бюджетом
    session_service._session_cost[sess.id] = 0.01
    session_service._session_cost_budget = 1.0

    call_count_before = fake_ai.call_count
    fake_ai.push_response("Нормальный ответ")
    resp = await session_service.process_message(client, "Ещё вопрос", channel="web")
    assert fake_ai.call_count == call_count_before + 1
    # Бюджет НЕ превышен — обычный ответ
    assert "бюджет" not in resp.text.lower()


@pytest.mark.asyncio
async def test_cost_budget_resets_on_new_session(
    session_service: SessionService, fake_repo, fake_ai
) -> None:
    """Новая сессия → cost accumulator сбрасывается для нового session.id."""
    from agent.storage.models import ClientRow

    fake_repo._clients[1] = ClientRow(
        id=1, email="c1@local", name=None,
        current_tone="warm", tone_intensity=3,
        timezone="Europe/Moscow", push_enabled=1, push_time="10:00",
        onboarding_state="tone_picked",
        created_at="2026-06-10T00:00:00+00:00",
        last_seen_at="2026-06-10T00:00:00+00:00",
        subscription_status="active",
    )
    client = await session_service._repo.get_client_by_id(1)
    fake_ai.push_response("Пока!")
    await session_service.process_message(client, "Пока", channel="web")
    # Эмулируем завершение сессии (end_session) и создание новой
    sess_old = await fake_repo.get_active_session(1)
    assert sess_old is not None
    # Накопим cost для старой
    session_service._session_cost[sess_old.id] = 0.5
    # Имитируем завершение
    await fake_repo.end_session(sess_old.id, reason="user_ended")
    # Новая сессия
    fake_ai.push_response("Снова привет!")
    await session_service.process_message(client, "Привет ещё раз", channel="web")
    sess_new = await fake_repo.get_active_session(1)
    assert sess_new is not None
    # Cost для новой сессии должен быть 0 (или очень мал после estimate)
    new_cost = session_service.get_session_cost(sess_new.id)
    # Либо 0 (estimate), либо 0.0X после fake_complete с минимальным cost
    assert new_cost < 0.01, f"Expected near-zero cost for new session, got {new_cost}"


def test_cost_budget_helper_methods(session_service: SessionService) -> None:
    """Sanity-check для _is_budget_exceeded и get_session_cost."""
    assert session_service._is_budget_exceeded(999) is False
    assert session_service.get_session_cost(999) == 0.0
    session_service._session_cost[1] = 2.0
    assert session_service._is_budget_exceeded(1) is True
    assert session_service.get_session_cost(1) == 2.0
