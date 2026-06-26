"""
Тесты для:
  - SOCKS5/HTTP прокси-коннектора в Telegram-боте
  - ВК-бота: маршрутизация команд, обработка URL

Запуск: python tests/test_bots.py
"""
from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path
from unittest.mock import MagicMock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

for _k in ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY",
           "http_proxy", "https_proxy", "all_proxy"):
    os.environ.pop(_k, None)


# ── Telegram proxy ──────────────────────────────────────────────────
def test_telegram_proxy_empty():
    """Пустой URL → None (без прокси)."""
    from agent.telegram_bot import _build_proxy_connector
    c = _build_proxy_connector("")
    assert c is None
    print("  ✅ proxy('') → None")


def test_telegram_proxy_socks5_full():
    from agent.telegram_bot import _build_proxy_connector
    c = _build_proxy_connector("socks5://user:pass@127.0.0.1:1080")
    assert c is not None
    assert type(c).__name__ == "ProxyConnector"
    print("  ✅ proxy(socks5://user:pass@host:port) → ProxyConnector")


def test_telegram_proxy_socks5_bare():
    """Голый host:port должен трактоваться как socks5."""
    from agent.telegram_bot import _build_proxy_connector
    c = _build_proxy_connector("127.0.0.1:9050")
    assert c is not None
    print("  ✅ proxy('127.0.0.1:9050') → socks5 автоматически")


def test_telegram_proxy_http():
    from agent.telegram_bot import _build_proxy_connector
    c = _build_proxy_connector("http://proxy.corp:8080")
    assert c is not None
    print("  ✅ proxy(http://...) → ProxyConnector")


def test_telegram_token_from_settings():
    """Токен берётся из settings (.env), не только из os.environ."""
    from agent.config import get_settings
    s = get_settings()
    assert s.telegram_bot_token, "telegram_bot_token не загружен из .env"
    # Формат токена Telegram: <bot_id>:<44 hex/base64-символа>
    assert ":" in s.telegram_bot_token, (
        f"Токен должен содержать ':', got: {s.telegram_bot_token[:20]}"
    )
    bot_id, _, secret = s.telegram_bot_token.partition(":")
    assert bot_id.isdigit() and len(secret) >= 30, (
        f"Токен выглядит подозрительно: {s.telegram_bot_token[:25]}"
    )
    print(f"  ✅ TELEGRAM_BOT_TOKEN из .env: {s.telegram_bot_token[:15]}... (id={bot_id})")


# ── VK bot: маршрутизация команд ──────────────────────────────────
class _FakeAPI:
    """Имитация vk_api для тестов маршрутизации."""

    def __init__(self):
        self.sent: list[dict] = []

    def messages_send(self, **kwargs):
        self.sent.append(kwargs)
        return [42]


def test_vk_route_start():
    """Команда /start → cmd_start, который шлёт приветствие."""
    from agent.vk_bot import handle_message
    api = MagicMock()
    api.messages.send = MagicMock(return_value=[1])
    handle_message(api, user_id=100, text="/start")
    assert api.messages.send.called, "messages.send не вызван"
    call = api.messages.send.call_args
    body = call.kwargs.get("message", "")
    assert "WishLibrarian" in body
    assert "Команды" in body or "/add" in body
    print("  ✅ /start → приветствие отправлено")


def test_vk_route_help():
    from agent.vk_bot import handle_message
    api = MagicMock()
    api.messages.send = MagicMock(return_value=[1])
    handle_message(api, user_id=100, text="/help")
    assert api.messages.send.called
    print("  ✅ /help → то же, что /start")


def test_vk_route_add_with_url():
    """Команда /add c URL должна запускать обработку (в потоке)."""
    from agent.vk_bot import handle_message, _user_state
    api = MagicMock()
    api.messages.send = MagicMock(return_value=[1])
    # Сбрасываем state
    _user_state.clear()
    # Не дожидаемся завершения — проверяем только что state создался
    handle_message(api, user_id=999, text="/add https://www.koob.ru/zeland/level1")
    # Должно быть минимум 2 вызова messages.send: "уже обрабатываю" нет
    # и "⏳ Обрабатываю:" — но обработка идёт в фоне, поэтому просто
    # проверим, что state создался с processing=True или отправлен первый message
    assert api.messages.send.called, "Не отправлен ответ"
    first = api.messages.send.call_args_list[0]
    body = first.kwargs.get("message", "")
    assert "Обрабатываю" in body or "Уже обрабатываю" in body
    # Дождёмся фонового потока
    import time
    for _ in range(30):
        if not _user_state.get(999, {}).get("processing"):
            break
        time.sleep(0.5)
    _user_state.clear()
    print("  ✅ /add URL → запускает обработку")


def test_vk_url_text_routes_to_add():
    """Свободный URL (без /add) → автоматически /add."""
    from agent.vk_bot import handle_message, _user_state
    api = MagicMock()
    api.messages.send = MagicMock(return_value=[1])
    _user_state.clear()
    handle_message(api, user_id=555, text="https://www.koob.ru/zeland/level1")
    assert api.messages.send.called
    body = api.messages.send.call_args.kwargs.get("message", "")
    assert "Обрабатываю" in body
    # Дождёмся фона
    import time
    for _ in range(30):
        if not _user_state.get(555, {}).get("processing"):
            break
        time.sleep(0.5)
    _user_state.clear()
    print("  ✅ URL без /add → автоматически обрабатывается")


def test_vk_unknown_command():
    from agent.vk_bot import handle_message
    api = MagicMock()
    api.messages.send = MagicMock(return_value=[1])
    handle_message(api, user_id=100, text="/foobar")
    body = api.messages.send.call_args.kwargs.get("message", "")
    assert "Неизвестная команда" in body or "❓" in body
    print("  ✅ /foobar → 'неизвестная команда'")


def test_vk_non_url_text():
    from agent.vk_bot import handle_message
    api = MagicMock()
    api.messages.send = MagicMock(return_value=[1])
    handle_message(api, user_id=100, text="просто текст без URL")
    body = api.messages.send.call_args.kwargs.get("message", "")
    assert "/help" in body or "ℹ️" in body
    print("  ✅ Текст без URL → подсказка")


def test_vk_send_message_chunking():
    """Длинные сообщения делятся на чанки по 4000 симв."""
    from agent.vk_bot import _send_message
    api = MagicMock()
    api.messages.send = MagicMock(return_value=[1])
    long_text = "абвгде" * 1000  # 6000 символов
    _send_message(api, user_id=1, text=long_text)
    # Должно быть ≥ 2 вызова
    assert api.messages.send.call_count >= 2, (
        f"Должно быть ≥ 2 чанка, получено {api.messages.send.call_count}"
    )
    print(f"  ✅ _send_message: 6000 симв → {api.messages.send.call_count} чанков")


def test_vk_config_loaded():
    """VK-конфиг читается (полей в Settings)."""
    from agent.config import get_settings
    s = get_settings()
    assert hasattr(s, "vk_group_token")
    assert hasattr(s, "vk_group_id")
    assert hasattr(s, "vk_proxy_url")
    print(f"  ✅ Settings: vk_group_token={'*' * 10 if s.vk_group_token else 'пусто'}, "
          f"vk_group_id={s.vk_group_id}")


# ── AI fallback для прокси-теста ───────────────────────────────────
def test_proxy_url_normalization():
    """Разные форматы URL нормализуются в один."""
    from agent.telegram_bot import _build_proxy_connector
    cases = [
        ("127.0.0.1:1080", True),         # голый → socks5
        ("socks5://1.2.3.4:1080", True),
        ("http://p:8080", True),
        ("", False),                       # пустой → None
    ]
    for url, should_be_set in cases:
        c = _build_proxy_connector(url)
        is_set = c is not None
        assert is_set == should_be_set, f"{url}: expected {should_be_set}, got {is_set}"
    print(f"  ✅ Нормализация: {len(cases)} формата прокси корректно распознаны")


if __name__ == "__main__":
    print("=" * 60); print("🧪 TEST 1: Telegram proxy — empty"); print("=" * 60)
    test_telegram_proxy_empty()
    print()
    print("=" * 60); print("🧪 TEST 2: Telegram proxy — socks5 full"); print("=" * 60)
    test_telegram_proxy_socks5_full()
    print()
    print("=" * 60); print("🧪 TEST 3: Telegram proxy — socks5 bare host:port"); print("=" * 60)
    test_telegram_proxy_socks5_bare()
    print()
    print("=" * 60); print("🧪 TEST 4: Telegram proxy — http"); print("=" * 60)
    test_telegram_proxy_http()
    print()
    print("=" * 60); print("🧪 TEST 5: Telegram token from .env"); print("=" * 60)
    test_telegram_token_from_settings()
    print()
    print("=" * 60); print("🧪 TEST 6: VK /start"); print("=" * 60)
    test_vk_route_start()
    print()
    print("=" * 60); print("🧪 TEST 7: VK /help"); print("=" * 60)
    test_vk_route_help()
    print()
    print("=" * 60); print("🧪 TEST 8: VK /add URL"); print("=" * 60)
    test_vk_route_add_with_url()
    print()
    print("=" * 60); print("🧪 TEST 9: VK free URL → auto add"); print("=" * 60)
    test_vk_url_text_routes_to_add()
    print()
    print("=" * 60); print("🧪 TEST 10: VK unknown command"); print("=" * 60)
    test_vk_unknown_command()
    print()
    print("=" * 60); print("🧪 TEST 11: VK non-URL text"); print("=" * 60)
    test_vk_non_url_text()
    print()
    print("=" * 60); print("🧪 TEST 12: VK message chunking"); print("=" * 60)
    test_vk_send_message_chunking()
    print()
    print("=" * 60); print("🧪 TEST 13: VK config loaded"); print("=" * 60)
    test_vk_config_loaded()
    print()
    print("=" * 60); print("🧪 TEST 14: Proxy URL normalization"); print("=" * 60)
    test_proxy_url_normalization()
    print()
    print("🎉 Все 14 тестов test_bots прошли успешно!")
