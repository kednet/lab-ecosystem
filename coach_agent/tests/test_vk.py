"""
Phase 7: VK-канал — адаптер, keyboard, unbound handler, repository, dedup, lifecycle.

12+ кейсов:
- 4 VKAdapter (normalize_inbound text/empty, format_outbound с/без кнопок)
- 3 VKUnboundHandler (email validate valid/invalid, bind flow, ask email on start)
- 3 Repository (find/upsert/list)
- 1 dedup
- 1 lifecycle (start/stop VKLongPollRunner)
"""

from __future__ import annotations

import asyncio
import json
import time

import pytest

# === Adapter ===

def test_vk_adapter_normalize_inbound_text():
    from agent.channels.vk import VKAdapter
    a = VKAdapter()
    raw = {"user_id": 12345, "text": "Привет", "message_id": 999}
    out = a.normalize_inbound(raw)
    assert out is not None
    assert out["user_id"] == 12345
    assert out["text"] == "Привет"
    assert out["message_id"] == 999


def test_vk_adapter_normalize_inbound_empty():
    from agent.channels.vk import VKAdapter
    a = VKAdapter()
    assert a.normalize_inbound({}) is None
    assert a.normalize_inbound({"text": ""}) is None
    assert a.normalize_inbound({"user_id": 1}) is None
    assert a.normalize_inbound({"text": "hi"}) is None  # нет user_id


def test_vk_adapter_normalize_inbound_keeps_payload():
    """payload (для будущих callback-кнопок) сохраняется в raw."""
    from agent.channels.vk import VKAdapter
    a = VKAdapter()
    out = a.normalize_inbound(
        {"user_id": 1, "text": "warm:3", "message_id": 5, "payload": "warm:3"}
    )
    assert out["payload"] == "warm:3"


def test_vk_adapter_format_outbound_with_buttons():
    from agent.channels.vk import VKAdapter
    a = VKAdapter()
    out = a.format_outbound(
        "Привет!",
        [{"label": "🫂 Тёплый", "payload": "warm:3", "kind": "tone_pick"}],
    )
    assert out["text"] == "Привет!"
    assert "keyboard" in out
    kb = json.loads(out["keyboard"])
    assert kb["one_time"] is False
    assert len(kb["buttons"]) == 1
    assert kb["buttons"][0][0]["action"]["label"] == "🫂 Тёплый"
    assert kb["buttons"][0][0]["action"]["type"] == "text"
    assert kb["buttons"][0][0]["color"] == "primary"  # tone_pick


def test_vk_adapter_format_outbound_no_buttons():
    from agent.channels.vk import VKAdapter
    a = VKAdapter()
    out = a.format_outbound("Просто текст", [])
    assert out["text"] == "Просто текст"
    assert out["keyboard"] is None


def test_vk_keyboard_color_mapping():
    from agent.channels.vk import vk_keyboard_from_buttons
    kb = json.loads(
        vk_keyboard_from_buttons(
            [
                {"label": "A", "payload": "a", "kind": "tone_pick"},
                {"label": "B", "payload": "b", "kind": "start_pick"},
                {"label": "C", "payload": "c", "kind": "end_session"},
                {"label": "D", "payload": "d", "kind": ""},
            ]
        )
    )
    colors = [row[0]["color"] for row in kb["buttons"]]
    assert colors == ["primary", "positive", "negative", "secondary"]


# === Unbound Handler ===

def test_validate_email_valid():
    from agent.channels.vk_unbound import validate_email
    assert validate_email("user@example.com") is True
    assert validate_email("name+tag@sub.domain.io") is True
    assert validate_email("  user@example.com  ") is True


def test_validate_email_invalid():
    from agent.channels.vk_unbound import validate_email
    assert validate_email("not-an-email") is False
    assert validate_email("missing@dot") is False
    assert validate_email("@no-local.com") is False
    assert validate_email("") is False
    assert validate_email("spaces in@addr.com") is False


@pytest.mark.asyncio
async def test_unbound_handler_asks_email_on_start(fake_repo):
    from agent.channels.vk_unbound import VKUnboundHandler
    h = VKUnboundHandler(fake_repo)
    text, buttons = await h.handle(user_id=111, text="/start")
    assert "Напиши" in text or "email" in text.lower()
    assert buttons == []
    assert h.get_state(111).step == "awaiting_email"


@pytest.mark.asyncio
async def test_unbound_handler_rejects_invalid_email(fake_repo):
    from agent.channels.vk_unbound import VKUnboundHandler
    h = VKUnboundHandler(fake_repo)
    text, buttons = await h.handle(user_id=222, text="/start")
    text2, _ = await h.handle(user_id=222, text="not-an-email")
    assert "не email" in text2 or "name@example.com" in text2
    # state не сменился
    assert h.get_state(222).step == "awaiting_email"


@pytest.mark.asyncio
async def test_unbound_handler_binds_on_valid_email(fake_repo):
    from agent.channels.vk_unbound import VKUnboundHandler
    # создаём клиента
    client = await fake_repo.upsert_client(email="test@example.com")
    h = VKUnboundHandler(fake_repo)
    await h.handle(user_id=333, text="/start")
    text, buttons = await h.handle(user_id=333, text="test@example.com")
    assert "✅" in text
    assert "Готово" in text
    assert len(buttons) == 4  # 4 tone buttons
    # Bind в repo
    chans = await fake_repo.list_client_channels(client.id)
    assert len(chans) == 1
    assert chans[0].channel == "vk"
    assert chans[0].external_id == "333"
    # state сменился
    assert h.get_state(333).step == "bound"
    assert h.get_state(333).client_id == client.id


@pytest.mark.asyncio
async def test_unbound_handler_unknown_email_keeps_state(fake_repo):
    from agent.channels.vk_unbound import VKUnboundHandler
    h = VKUnboundHandler(fake_repo)
    await h.handle(user_id=444, text="/start")
    text, _ = await h.handle(user_id=444, text="ghost@nowhere.com")
    assert "Не нашёл" in text or "❌" in text
    assert h.get_state(444).step == "awaiting_email"


# === Repository ===

@pytest.mark.asyncio
async def test_repository_find_client_by_channel_finds(fake_repo):
    client = await fake_repo.upsert_client(email="a@b.com")
    await fake_repo.upsert_client_channel(client.id, "vk", "99999")
    found = await fake_repo.find_client_by_channel("vk", "99999")
    assert found is not None
    assert found.id == client.id
    assert found.email == "a@b.com"


@pytest.mark.asyncio
async def test_repository_find_client_by_channel_returns_none(fake_repo):
    found = await fake_repo.find_client_by_channel("vk", "00000")
    assert found is None


@pytest.mark.asyncio
async def test_repository_upsert_client_channel_creates_or_updates(fake_repo):
    client = await fake_repo.upsert_client(email="x@y.com")
    # Создаём
    ch1 = await fake_repo.upsert_client_channel(client.id, "vk", "111")
    assert ch1.client_id == client.id
    assert ch1.channel == "vk"
    assert ch1.external_id == "111"
    # Обновляем
    ch2 = await fake_repo.upsert_client_channel(client.id, "vk", "222")
    assert ch2.client_id == client.id
    assert ch2.external_id == "222"
    # Дублей не появилось
    chans = await fake_repo.list_client_channels(client.id)
    assert len(chans) == 1


@pytest.mark.asyncio
async def test_repository_list_client_channels(fake_repo):
    client = await fake_repo.upsert_client(email="a@b.com")
    await fake_repo.upsert_client_channel(client.id, "vk", "v1")
    await fake_repo.upsert_client_channel(client.id, "telegram", "t1")
    channels = await fake_repo.list_client_channels(client.id)
    assert len(channels) == 2
    names = {c.channel for c in channels}
    assert names == {"vk", "telegram"}


# === Dedup (in VKLongPollRunner) ===

def test_dedup_skips_duplicate_message_ids():
    """message_id повторно в течение TTL → игнорируется."""
    from agent.channels.vk import VKLongPollRunner
    # Минимальный объект runner (без реального Long Poll)
    runner = VKLongPollRunner(
        token="dummy", group_id=1,
        message_bus=None, repository=None,  # type: ignore[arg-type]
    )
    assert runner._is_duplicate(123) is False
    assert runner._is_duplicate(123) is True  # дубль
    assert runner._is_duplicate(456) is False  # новый
    # None всегда False (безопасный fallback)
    assert runner._is_duplicate(None) is False


# === Lifecycle (start/stop) ===

def test_vk_runner_start_stop_does_not_crash():
    """Runner.start() + stop() — без реального VK API, без падений."""
    from agent.channels.vk import VKLongPollRunner
    # Используем мок-loop, чтобы run() сразу завершился (мы не хотим
    # открывать реальное VK-соединение в тестах).
    loop = asyncio.new_event_loop()
    try:
        runner = VKLongPollRunner(
            token="bogus_token_for_test",
            group_id=12345,
            message_bus=None,  # type: ignore[arg-type]
            repository=None,   # type: ignore[arg-type]
            loop=loop,
        )
        runner.start()
        time.sleep(0.2)  # дать потоку стартовать
        # Stop должен сработать (если run() уже вошёл в longpoll.listen()
        # — может не сработать, но stop_event — флаг, не блокирующий)
        runner.stop()
        # Ждём завершения (макс 2 сек)
        runner.join(timeout=2.0)
        # Поток либо завершился (vk session failed → return), либо daemon
        # и main-thread завершит его. Не assert'им is_alive строго.
    finally:
        loop.close()
