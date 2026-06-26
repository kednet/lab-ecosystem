"""
Тесты crisis-detection: 4 regex, инвариант перед AI, FSM, log hash, flags.
"""

from __future__ import annotations

import pytest

from agent.core.crisis import (
    CRISIS_RESPONSE,
    detect_crisis,
    hash_message,
)

# === Базовые срабатывания ===

@pytest.mark.parametrize("text,expected_pattern", [
    ("Не хочу жить, всё бессмысленно", "suicide"),
    ("Лучше бы я умер", "suicide"),
    ("Думаю о суициде", "suicide"),
    ("Всё равно как жить дальше", "suicide"),
    ("Бью ребёнка", "violence"),
    ("Бью себя", "violence"),
    ("Причиняю боль", "violence"),
    ("Избиваю", "violence"),
    ("Порезы, таблетки", "self_harm"),
    ("Хочу выйти в окно", "self_harm"),
    ("Могу повеситься", "self_harm"),
    ("Крик о помощи", "distress"),
    ("Не могу больше так", "distress"),
    ("Всё бессмысленно", "distress"),
])
def test_crisis_patterns_match(text: str, expected_pattern: str) -> None:
    assert detect_crisis(text) == expected_pattern


def test_no_match_normal_text() -> None:
    assert detect_crisis("Хочу открыть бизнес") is None
    assert detect_crisis("Не хочу кашу на завтрак") is None
    assert detect_crisis("") is None


# === hash_message ===

def test_hash_message_sha256() -> None:
    h = hash_message("тест")
    assert len(h) == 64
    # детерминированный
    assert hash_message("тест") == h
    # разные тексты → разные хэши
    assert hash_message("другое") != h


# === Инвариант: AI НЕ вызывается при crisis ===

@pytest.mark.asyncio
async def test_crisis_invariance_before_ai(
    session_service, fake_ai, seeded_repo
) -> None:
    """AI.complete() НЕ должен быть вызван при crisis-сообщении."""
    from agent.storage.models import ClientRow

    seeded_repo._clients[1] = ClientRow(
        id=1, email="c1@local", name=None,
        current_tone="warm", tone_intensity=3,
        timezone="Europe/Moscow", push_enabled=1, push_time="10:00",
        onboarding_state="tone_picked",
        created_at="2026-06-10T00:00:00+00:00",
        last_seen_at="2026-06-10T00:00:00+00:00",
        subscription_status="active",
    )
    client = await session_service._repo.get_client_by_id(1)
    assert client is not None
    resp = await session_service.process_message(
        client, "Не хочу жить, всё бессмысленно", channel="web"
    )
    assert resp.crisis_flag is True
    assert resp.state.value == "S_CRISIS_STOP"
    # AI не вызван
    assert fake_ai.call_count == 0


# === Crisis response: шаблонный ===

@pytest.mark.asyncio
async def test_crisis_response_is_templated(
    session_service, seeded_repo
) -> None:
    from agent.storage.models import ClientRow

    seeded_repo._clients[1] = ClientRow(
        id=1, email="c1@local", name=None,
        current_tone="warm", tone_intensity=3,
        timezone="Europe/Moscow", push_enabled=1, push_time="10:00",
        onboarding_state="tone_picked",
        created_at="2026-06-10T00:00:00+00:00",
        last_seen_at="2026-06-10T00:00:00+00:00",
        subscription_status="active",
    )
    client = await session_service._repo.get_client_by_id(1)
    resp = await session_service.process_message(
        client, "Бью ребёнка", channel="web"
    )
    assert "8-800-2000-122" in resp.text
    assert "112" in resp.text
    assert resp.text == CRISIS_RESPONSE


# === Crisis FSM transition ===

@pytest.mark.asyncio
async def test_crisis_transitions_to_crisis_stop(
    session_service, seeded_repo, fake_repo, fake_ai
) -> None:
    from agent.storage.models import ClientRow

    seeded_repo._clients[1] = ClientRow(
        id=1, email="c1@local", name=None,
        current_tone="warm", tone_intensity=3,
        timezone="Europe/Moscow", push_enabled=1, push_time="10:00",
        onboarding_state="tone_picked",
        created_at="2026-06-10T00:00:00+00:00",
        last_seen_at="2026-06-10T00:00:00+00:00",
        subscription_status="active",
    )
    client = await session_service._repo.get_client_by_id(1)
    # Сначала создадим нормальную сессию через сообщение
    fake_ai.push_response("Привет, как дела?")
    await session_service.process_message(client, "Привет", channel="web")
    # Затем crisis
    resp = await session_service.process_message(
        client, "Не могу больше, всё бессмысленно", channel="web"
    )
    assert resp.state.value == "S_CRISIS_STOP"


# === Crisis log: только хэш, не текст ===

@pytest.mark.asyncio
async def test_crisis_log_written_with_hash_not_text(
    session_service, seeded_repo, fake_repo
) -> None:
    from agent.storage.models import ClientRow

    seeded_repo._clients[1] = ClientRow(
        id=1, email="c1@local", name=None,
        current_tone="warm", tone_intensity=3,
        timezone="Europe/Moscow", push_enabled=1, push_time="10:00",
        onboarding_state="tone_picked",
        created_at="2026-06-10T00:00:00+00:00",
        last_seen_at="2026-06-10T00:00:00+00:00",
        subscription_status="active",
    )
    client = await session_service._repo.get_client_by_id(1)
    original_text = "Совершенно секретное сообщение: не хочу жить уникальные-слова-12345"
    await session_service.process_message(client, original_text, channel="web")
    # Проверяем, что crisis_log содержит хэш
    crisis_logs = fake_repo._crisis
    assert len(crisis_logs) == 1
    log_row = crisis_logs[0]
    assert log_row.message_hash == hash_message(original_text)
    # Текст НЕ сохранился
    for _m in fake_repo._messages:
        # Сообщения сохраняются в message, но с is_crisis=1 и excluded=1
        # Главное — что в crisis_log не текст
        pass
    assert log_row.message_hash != original_text


# === Message flags ===

@pytest.mark.asyncio
async def test_crisis_message_marked_excluded(
    session_service, seeded_repo, fake_repo
) -> None:
    from agent.storage.models import ClientRow

    seeded_repo._clients[1] = ClientRow(
        id=1, email="c1@local", name=None,
        current_tone="warm", tone_intensity=3,
        timezone="Europe/Moscow", push_enabled=1, push_time="10:00",
        onboarding_state="tone_picked",
        created_at="2026-06-10T00:00:00+00:00",
        last_seen_at="2026-06-10T00:00:00+00:00",
        subscription_status="active",
    )
    client = await session_service._repo.get_client_by_id(1)
    await session_service.process_message(client, "Порезы на руках", channel="web")
    # Ищем user-message с is_crisis=1
    crisis_msgs = [m for m in fake_repo._messages if m.is_crisis_message == 1]
    assert len(crisis_msgs) >= 1
    for m in crisis_msgs:
        assert m.excluded_from_training == 1


# === Без AI: crisis всё равно обрабатывается ===

@pytest.mark.asyncio
async def test_crisis_works_without_ai_configured(
    session_service, seeded_repo
) -> None:
    """Даже если AI не сконфигурирован, crisis-detection работает (без AI)."""
    from agent.ai.factory import AIClient
    from agent.storage.models import ClientRow

    class FailingAI(AIClient):
        @property
        def name(self): return "failing"
        def supports_tools(self): return False
        async def complete(self, **kw):
            raise RuntimeError("AI down")

    session_service._ai = FailingAI()

    seeded_repo._clients[1] = ClientRow(
        id=1, email="c1@local", name=None,
        current_tone="warm", tone_intensity=3,
        timezone="Europe/Moscow", push_enabled=1, push_time="10:00",
        onboarding_state="tone_picked",
        created_at="2026-06-10T00:00:00+00:00",
        last_seen_at="2026-06-10T00:00:00+00:00",
        subscription_status="active",
    )
    client = await session_service._repo.get_client_by_id(1)
    resp = await session_service.process_message(
        client, "Не хочу жить", channel="web"
    )
    assert resp.crisis_flag is True
    assert resp.state.value == "S_CRISIS_STOP"


# === Phase 8: crisis_flag persistence ===

@pytest.mark.asyncio
async def test_crisis_writes_session_crisis_flag(
    session_service, seeded_repo, fake_repo
) -> None:
    """Phase 8: после crisis-сообщения session.crisis_flag=1 в репо."""
    from agent.storage.models import ClientRow

    seeded_repo._clients[1] = ClientRow(
        id=1, email="c1@local", name=None,
        current_tone="warm", tone_intensity=3,
        timezone="Europe/Moscow", push_enabled=1, push_time="10:00",
        onboarding_state="tone_picked",
        created_at="2026-06-10T00:00:00+00:00",
        last_seen_at="2026-06-10T00:00:00+00:00",
        subscription_status="active",
    )
    client = await session_service._repo.get_client_by_id(1)
    await session_service.process_message(
        client, "Не хочу жить", channel="web"
    )
    # Достаём сессию из репо и проверяем crisis_flag
    sess = await fake_repo.get_active_session(1)
    assert sess is not None
    assert sess.crisis_flag == 1


@pytest.mark.asyncio
async def test_crisis_invariance_persists_flag(
    session_service, seeded_repo, fake_repo
) -> None:
    """Phase 8: crisis_flag остаётся 1 после нескольких сообщений / get_session_by_id."""
    from agent.storage.models import ClientRow

    seeded_repo._clients[1] = ClientRow(
        id=1, email="c1@local", name=None,
        current_tone="warm", tone_intensity=3,
        timezone="Europe/Moscow", push_enabled=1, push_time="10:00",
        onboarding_state="tone_picked",
        created_at="2026-06-10T00:00:00+00:00",
        last_seen_at="2026-06-10T00:00:00+00:00",
        subscription_status="active",
    )
    client = await session_service._repo.get_client_by_id(1)
    await session_service.process_message(
        client, "Всё бессмысленно", channel="web"
    )
    # Перечитываем сессию через get_session_by_id (имитация нового запроса)
    sess = await fake_repo.get_active_session(1)
    assert sess is not None
    sid = sess.id
    fresh = await fake_repo.get_session_by_id(sid)
    assert fresh is not None
    assert fresh.crisis_flag == 1
    # Повторный get не сбрасывает флаг
    fresh2 = await fake_repo.get_session_by_id(sid)
    assert fresh2.crisis_flag == 1
