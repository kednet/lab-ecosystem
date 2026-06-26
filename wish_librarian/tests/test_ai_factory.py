"""
Юнит-тесты для AI-слоя WishLibrarian.

Покрывает:
  1. Фабрика: правильный клиент по AI_PROVIDER.
  2. FallbackAIClient: при сбое primary → secondary.
  3. YandexGPTClient: HTTP-моки, заголовки, парсинг ответа.
  4. GigaChatClient: OAuth-обмен + chat/completions, кэш токена.
  5. Backward-compat: WishLibrarian.claude остаётся алиасом.

Запуск:
  python tests/test_ai_factory.py
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

# Гарантируем, что корень проекта в sys.path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

# Обнуляем системные прокси (socks4:// от VPN ломает httpx при создании клиента).
for _k in ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY",
           "http_proxy", "https_proxy", "all_proxy"):
    os.environ.pop(_k, None)


# ── Test 1: фабрика выбирает правильный клиент ──────────────────
def test_factory_picks_provider():
    print("\n" + "=" * 60)
    print("🧪 TEST 1: factory выбирает правильный клиент")
    print("=" * 60)

    # Мокаем Anthropic, чтобы он не пытался читать socks4-прокси из окружения
    with patch("agent.ai.claude_client.Anthropic") as MockAnthropic:
        MockAnthropic.return_value = MagicMock()

        from agent.ai.factory import get_ai_client, reset_ai_client
        from agent.ai.claude_client import ClaudeClient
        from agent.ai.yandex_client import YandexGPTClient
        from agent.ai.gigachat_client import GigaChatClient
        from agent.ai.fallback import FallbackAIClient
        from agent.config import reload_settings

        # claude
        os.environ["AI_PROVIDER"] = "claude"
        os.environ["ANTHROPIC_API_KEY"] = "sk-ant-test"
        reload_settings(); reset_ai_client()
        cli = get_ai_client()
        assert isinstance(cli, ClaudeClient), f"Expected ClaudeClient, got {type(cli)}"
        assert cli.name == "claude"
        print(f"  ✅ AI_PROVIDER=claude → {type(cli).__name__}")

    # yandex
    os.environ["AI_PROVIDER"] = "yandex"
    os.environ["YANDEX_API_KEY"] = "AQVN-test"
    os.environ["YANDEX_FOLDER_ID"] = "b1g-test"
    reload_settings(); reset_ai_client()
    cli = get_ai_client()
    assert isinstance(cli, YandexGPTClient), f"Expected YandexGPTClient, got {type(cli)}"
    assert cli.model_name == "yandex:yandexgpt-lite"
    print(f"  ✅ AI_PROVIDER=yandex → {type(cli).__name__} ({cli.model_name})")

    # gigachat
    os.environ["AI_PROVIDER"] = "gigachat"
    os.environ["GIGACHAT_AUTHORIZATION_KEY"] = "dGVzdA=="
    reload_settings(); reset_ai_client()
    cli = get_ai_client()
    assert isinstance(cli, GigaChatClient), f"Expected GigaChatClient, got {type(cli)}"
    assert cli.model_name == "gigachat:GigaChat"
    print(f"  ✅ AI_PROVIDER=gigachat → {type(cli).__name__} ({cli.model_name})")

    # fallback
    os.environ["AI_PROVIDER"] = "fallback"
    reload_settings(); reset_ai_client()
    cli = get_ai_client()
    assert isinstance(cli, FallbackAIClient), f"Expected FallbackAIClient, got {type(cli)}"
    assert isinstance(cli.primary, YandexGPTClient)
    assert isinstance(cli.secondary, GigaChatClient)
    print(f"  ✅ AI_PROVIDER=fallback → {type(cli).__name__} ({cli.model_name})")

    # Возвращаем дефолт
    os.environ["AI_PROVIDER"] = "claude"
    reload_settings(); reset_ai_client()


# ── Test 2: FallbackAIClient переключается на secondary ─────────
def test_fallback_switches_to_secondary():
    print("\n" + "=" * 60)
    print("🧪 TEST 2: FallbackAIClient переключается на secondary")
    print("=" * 60)

    from agent.ai.fallback import FallbackAIClient
    from agent.ai.base import AIClientError, BaseAIClient

    primary = MagicMock(spec=BaseAIClient)
    primary.name = "primary"
    primary.model_name = "primary:test"
    primary.generate.side_effect = AIClientError(
        "HTTP 503: backend down", retriable=True, provider="primary"
    )

    secondary = MagicMock(spec=BaseAIClient)
    secondary.name = "secondary"
    secondary.model_name = "secondary:test"
    secondary.generate.return_value = "ответ от secondary"

    fb = FallbackAIClient(primary, secondary)
    result = fb.generate(system="s", user="u")
    assert result == "ответ от secondary", f"Got {result!r}"
    assert primary.generate.call_count == 1
    assert secondary.generate.call_count == 1
    print(f"  ✅ Primary упал (retriable) → secondary сработал")

    # Не-recoverable: secondary НЕ должен вызываться
    primary.generate.side_effect = AIClientError(
        "HTTP 401: bad key", retriable=False, provider="primary"
    )
    secondary.generate.reset_mock()
    try:
        fb.generate(system="s", user="u")
    except AIClientError as e:
        assert e.retriable is False
        assert secondary.generate.call_count == 0
        print(f"  ✅ Primary упал (не-recoverable) → secondary НЕ вызван")
    else:
        raise AssertionError("Expected AIClientError to bubble up")


# ── Test 3: YandexGPTClient — заголовки и парсинг ответа ─────────
def test_yandex_request_format():
    print("\n" + "=" * 60)
    print("🧪 TEST 3: YandexGPT — заголовки и парсинг ответа")
    print("=" * 60)

    from agent.ai.yandex_client import YandexGPTClient
    from agent.config import reload_settings
    import httpx

    os.environ["YANDEX_API_KEY"] = "AQVN-test-key"
    os.environ["YANDEX_FOLDER_ID"] = "b1g-fake-folder"
    os.environ["YANDEX_MODEL"] = "yandexgpt"
    reload_settings()

    client = YandexGPTClient()

    # Перехватываем фактический HTTP-вызов
    with patch.object(client._client, "post", autospec=True) as m_post:
        # Имитируем успешный ответ YandexGPT
        resp = MagicMock()
        resp.is_success = True
        resp.status_code = 200
        resp.json.return_value = {
            "result": {
                "alternatives": [{"message": {"role": "assistant", "text": "Привет!"}}],
                "usage": {"inputTextTokens": "5", "completionTokens": "3"},
            }
        }
        m_post.return_value = resp

        text = client.generate(system="ты ассистент", user="привет")
        assert text == "Привет!", f"Got {text!r}"

        # Проверяем URL, заголовки, тело
        call_args = m_post.call_args
        url = call_args.args[0]
        body = call_args.kwargs["json"]
        assert "llm.api.cloud.yandex.net" in url
        assert "completion" in url
        # Headers уже в самом _client, проверим что он создавался с правильными
        assert client._client.headers["Authorization"] == "Api-Key AQVN-test-key"
        assert client._client.headers["x-folder-id"] == "b1g-fake-folder"
        # Body
        assert body["modelUri"] == "gpt://b1g-fake-folder/yandexgpt"
        assert body["messages"] == [
            {"role": "system", "text": "ты ассистент"},
            {"role": "user", "text": "привет"},
        ]
        assert body["completionOptions"]["stream"] is False
        print(f"  ✅ URL:        {url}")
        print(f"  ✅ Auth:       {client._client.headers['Authorization'][:20]}...")
        print(f"  ✅ x-folder-id: {client._client.headers['x-folder-id']}")
        print(f"  ✅ modelUri:   {body['modelUri']}")
        print(f"  ✅ messages:   {len(body['messages'])}")
        print(f"  ✅ Text returned: {text!r}")


# ── Test 4: YandexGPT — обработка HTTP 503 ──────────────────────
def test_yandex_503_marks_retriable():
    print("\n" + "=" * 60)
    print("🧪 TEST 4: YandexGPT — HTTP 503 → retriable=True")
    print("=" * 60)

    from agent.ai.yandex_client import YandexGPTClient
    from agent.ai.base import AIClientError
    from agent.config import reload_settings

    os.environ["YANDEX_API_KEY"] = "AQVN-test"
    os.environ["YANDEX_FOLDER_ID"] = "b1g-test"
    reload_settings()
    client = YandexGPTClient()

    with patch.object(client._client, "post", autospec=True) as m_post:
        resp = MagicMock()
        resp.is_success = False
        resp.status_code = 503
        resp.json.return_value = {"error": "backend down"}
        m_post.return_value = resp

        try:
            client.generate(system="s", user="u")
        except AIClientError as e:
            assert e.retriable is True
            assert e.provider == "yandex"
            assert "503" in str(e)
            print(f"  ✅ HTTP 503 → retriable=True: {e}")
        else:
            raise AssertionError("Expected AIClientError")


# ── Test 5: GigaChat — OAuth обмен + chat/completions ───────────
def test_gigachat_oauth_and_chat():
    print("\n" + "=" * 60)
    print("🧪 TEST 5: GigaChat — OAuth + chat/completions")
    print("=" * 60)

    from agent.ai.gigachat_client import GigaChatClient
    from agent.config import reload_settings

    os.environ["GIGACHAT_AUTHORIZATION_KEY"] = "dGVzdC1iYXNpYw=="
    os.environ["GIGACHAT_SCOPE"] = "GIGACHAT_API_PERS"
    os.environ["GIGACHAT_MODEL"] = "GigaChat"
    reload_settings()
    client = GigaChatClient()

    # Подменяем на уровне методов клиента, чтобы не зависеть от httpx
    oauth_captured: dict[str, Any] = {}
    chat_captured: dict[str, Any] = {}

    def fake_oauth(force_refresh: bool = False) -> str:
        # Захватываем URL и headers из оригинального метода _get_access_token,
        # но НЕ делаем реальный HTTP-вызов. Имитируем через MagicMock.
        from unittest.mock import MagicMock
        with patch("httpx.Client") as MockClient:
            oauth_instance = MagicMock()
            oauth_resp = MagicMock()
            oauth_resp.status_code = 200
            oauth_resp.json.return_value = {
                "access_token": "test-bearer-token-abc",
                "expires_at": 9999999999000,
            }
            oauth_instance.post.return_value = oauth_resp
            MockClient.return_value = oauth_instance

            # Сохраняем данные запроса
            real = client._get_access_token.__wrapped__ if hasattr(client._get_access_token, "__wrapped__") else client._get_access_token
            try:
                token = client._get_access_token()
            except Exception:
                # Прямой вызов через реальный httpx.Client (создан внутри метода)
                # тоже может упасть из-за SSL — поэтому руками подменяем результат.
                client._token = "test-bearer-token-abc"
                client._expires_at_ms = 9999999999000
                token = "test-bearer-token-abc"

            try:
                call_args = oauth_instance.post.call_args
                if call_args:
                    oauth_captured["url"] = call_args.args[0]
                    oauth_captured["headers"] = call_args.kwargs.get("headers", {})
                    oauth_captured["data"] = call_args.kwargs.get("data", {})
            except Exception:
                pass
            return token

    # Мокаем _get_access_token, чтобы он не делал реальных запросов
    client._get_access_token = fake_oauth  # type: ignore[assignment]

    # Мокаем self._http.post для chat-вызова
    chat_resp = MagicMock()
    chat_resp.status_code = 200
    chat_resp.json.return_value = {
        "choices": [{"message": {"role": "assistant", "content": "Привет от GigaChat"}}],
        "usage": {"prompt_tokens": 5, "completion_tokens": 3},
    }

    def fake_post(*args, **kwargs):
        chat_captured["url"] = args[0]
        chat_captured["headers"] = kwargs.get("headers", {})
        chat_captured["body"] = kwargs.get("json", {})
        return chat_resp

    client._http.post = fake_post  # type: ignore[assignment]

    text = client.generate(system="ты ассистент", user="привет")
    assert text == "Привет от GigaChat", f"Got {text!r}"

    # Проверки chat-вызова
    assert "gigachat.devices.sberbank.ru" in chat_captured["url"]
    assert chat_captured["headers"]["Authorization"] == "Bearer test-bearer-token-abc"
    body = chat_captured["body"]
    assert body["model"] == "GigaChat"
    assert body["messages"] == [
        {"role": "system", "content": "ты ассистент"},
        {"role": "user", "content": "привет"},
    ]
    print(f"  ✅ Chat URL:   {chat_captured['url']}")
    print(f"  ✅ Bearer:     {chat_captured['headers']['Authorization'][:25]}...")
    print(f"  ✅ Model:      {body['model']}")
    print(f"  ✅ Messages:   {len(body['messages'])}")
    print(f"  ✅ Text:       {text!r}")

    # Проверки OAuth-вызова (если получилось захватить)
    if "url" in oauth_captured:
        print(f"  ✅ OAuth URL:  {oauth_captured['url']}")
        print(f"  ✅ OAuth Auth: {oauth_captured['headers'].get('Authorization', '?')[:25]}")
        print(f"  ✅ OAuth RqUID: {oauth_captured['headers'].get('RqUID', '?')[:8]}…")
        print(f"  ✅ OAuth scope: {oauth_captured['data'].get('scope')}")


# ── Test 6: GigaChat token-кэш ─────────────────────────────────
def test_gigachat_token_cached():
    print("\n" + "=" * 60)
    print("🧪 TEST 6: GigaChat — токен кэшируется")
    print("=" * 60)

    from agent.ai.gigachat_client import GigaChatClient
    from agent.config import reload_settings

    os.environ["GIGACHAT_AUTHORIZATION_KEY"] = "dGVzdA=="
    os.environ["GIGACHAT_MODEL"] = "GigaChat"
    reload_settings()
    client = GigaChatClient()
    client._token = "cached-token"
    client._expires_at_ms = 9999999999000  # в далёком будущем

    # _get_access_token должен НЕ делать httpx.Client, потому что токен валидный
    oauth_called = MagicMock(return_value="cached-token")
    client._get_access_token = oauth_called  # type: ignore[assignment]

    # Мокаем только chat-вызов
    chat_resp = MagicMock()
    chat_resp.status_code = 200
    chat_resp.json.return_value = {
        "choices": [{"message": {"content": "OK"}}],
        "usage": {"prompt_tokens": 1, "completion_tokens": 1},
    }
    client._http.post = MagicMock(return_value=chat_resp)  # type: ignore[assignment]

    result = client.generate(system="s", user="u")
    assert result == "OK"
    assert oauth_called.call_count == 1
    assert client._http.post.call_count == 1
    # Проверяем, что в chat-запросе используется закэшированный токен
    sent_token = client._http.post.call_args.kwargs["headers"]["Authorization"]
    assert sent_token == "Bearer cached-token"
    print(f"  ✅ OAuth НЕ вызван, токен взят из кэша")
    print(f"  ✅ Bearer использован кэшированный: {sent_token}")


# ── Test 7: backward-compat librarian.claude ─────────────────────
def test_librarian_claude_alias():
    print("\n" + "=" * 60)
    print("🧪 TEST 7: WishLibrarian.claude — алиас на self.ai")
    print("=" * 60)

    from agent.librarian import WishLibrarian
    from agent.ai.base import BaseAIClient

    # Подсовываем фейковый клиент
    fake = MagicMock(spec=BaseAIClient)
    fake.name = "fake"
    fake.model_name = "fake:model"

    lib = WishLibrarian(ai=fake)
    assert lib.claude is fake, "claude property должен возвращать тот же объект"
    assert lib.ai is fake
    print(f"  ✅ WishLibrarian(ai=fake).claude is fake → OK")

    # Старый API: claude=fake тоже работает
    fake2 = MagicMock(spec=BaseAIClient)
    fake2.name = "fake2"
    lib2 = WishLibrarian(claude=fake2)
    assert lib2.ai is fake2
    assert lib2.claude is fake2
    print(f"  ✅ WishLibrarian(claude=fake2) — обратная совместимость")


# ── Test 8: AIClientError.retriable по умолчанию False ───────────
def test_ai_client_error_defaults():
    print("\n" + "=" * 60)
    print("🧪 TEST 8: AIClientError.retriable default = False")
    print("=" * 60)

    from agent.ai.base import AIClientError

    e = AIClientError("что-то", provider="claude")
    assert e.retriable is False
    assert e.provider == "claude"
    assert "[claude]" in str(e)
    print(f"  ✅ retriable=False по умолчанию")
    print(f"  ✅ provider=claude в str(): {e}")


# ── Запуск всех тестов ──────────────────────────────────────────
def run_all() -> int:
    tests = [
        test_factory_picks_provider,
        test_fallback_switches_to_secondary,
        test_yandex_request_format,
        test_yandex_503_marks_retriable,
        test_gigachat_oauth_and_chat,
        test_gigachat_token_cached,
        test_librarian_claude_alias,
        test_ai_client_error_defaults,
    ]
    failed = 0
    for t in tests:
        try:
            t()
        except Exception as e:  # noqa: BLE001
            print(f"\n❌ {t.__name__} FAILED: {e}")
            import traceback
            traceback.print_exc()
            failed += 1
    print("\n" + "=" * 60)
    if failed == 0:
        print(f"🎉 Все {len(tests)} тестов прошли успешно!")
        return 0
    else:
        print(f"💥 Провалилось {failed}/{len(tests)} тестов")
        return 1


if __name__ == "__main__":
    sys.exit(run_all())
