"""
Клиент для GigaChat (Сбер).

Документация:
  https://developers.sber.ru/docs/ru/gigachat/api/overview
  https://developers.sber.ru/docs/ru/gigachat/api/reference/rest/post-chat-completions

Аутентификация (двухшаговая):
  1) POST /api/v2/oauth с `Authorization: Basic <GIGACHAT_AUTHORIZATION_KEY>`
     (это base64 от "client_id:client_secret") и заголовком `RqUID: <uuid>`.
     Возвращает `access_token` + `expires_at` (ms).
  2) Используем `Authorization: Bearer <access_token>` для вызова /api/v1/chat/completions.

Токен кэшируется в памяти до истечения.
"""
from __future__ import annotations

import time
import urllib3
import uuid
from typing import Any, Optional

import httpx
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from agent.ai.base import AIClientError, BaseAIClient
from agent.config import get_settings
from agent.utils.logger import get_logger


# Сбер использует самоподписанный сертификат на OAuth-эндпоинте, и в
# официальных примерах SDK отключают verify. Делаем то же самое ТОЛЬКО
# для OAuth-запроса и подавляем InsecureRequestWarning, чтобы не спамить
# в логи.
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
logger = get_logger()
class GigaChatClient(BaseAIClient):
    """Клиент GigaChat (Сбер)."""

    name = "gigachat"

    def __init__(
        self,
        *,
        authorization_key: Optional[str] = None,
        scope: Optional[str] = None,
        model: Optional[str] = None,
        base_url: Optional[str] = None,
        oauth_url: Optional[str] = None,
        timeout: Optional[int] = None,
    ):
        self.settings = get_settings()
        self.authorization_key = (
            authorization_key or self.settings.gigachat_authorization_key
        )
        self.scope = scope or self.settings.gigachat_scope
        self.model = model or self.settings.gigachat_model
        self.base_url = (base_url or self.settings.gigachat_base_url).rstrip("/")
        self.oauth_url = (oauth_url or self.settings.gigachat_oauth_url).rstrip("/")
        self.timeout = timeout or self.settings.request_timeout

        if not self.authorization_key:
            raise RuntimeError(
                "GIGACHAT_AUTHORIZATION_KEY не задан. "
                "Создайте ключ в https://developers.sber.ru/ и добавьте в .env"
            )

        # HTTP-клиент для chat/completions.
        # Сберовский API нередко недоступен из корпоративных сетей с MITM
        # (самоподписанный корневой сертификат в системе → SSL fail). Даём
        # возможность отключить verify, по умолчанию оставляем проверку.
        # В официальном gigachat Python SDK тоже используется verify=False.
        _verify = self.settings.gigachat_verify_ssl
        # trust_env=False, чтобы socks4:// от VPN не ломал httpx.
        self._http = httpx.Client(
            timeout=self.timeout,
            trust_env=False,
            verify=_verify,
            headers={
                "Content-Type": "application/json",
                "Accept": "application/json",
                "User-Agent": self.settings.user_agent,
            },
        )
        if not _verify:
            logger.warning(
                "⚠️ GigaChat: проверка SSL ОТКЛЮЧЕНА (GIGACHAT_VERIFY_SSL=false). "
                "Только для корпоративных сетей с MITM."
            )

        # Кэш access_token
        self._token: Optional[str] = None
        self._expires_at_ms: int = 0

    @property
    def model_name(self) -> str:
        return f"gigachat:{self.model}"

    # ── OAuth ──────────────────────────────────────────────────────
    def _get_access_token(self, force_refresh: bool = False) -> str:
        """Получить (или обновить) access_token GigaChat."""
        now_ms = int(time.time() * 1000)
        # Обновляем за 60 секунд до истечения
        if not force_refresh and self._token and now_ms < (self._expires_at_ms - 60_000):
            return self._token

        logger.debug("🔐 GigaChat: запрашиваю новый access_token")

        # OAuth-эндпоинт Сбера использует самоподписанный сертификат, и
        # для него в официальных примерах SDK отключают verify=False.
        # Мы делаем то же самое, но ТОЛЬКО для OAuth-запроса.
        try:
            oauth_client = httpx.Client(
                timeout=self.timeout, verify=False, trust_env=False,
            )
            try:
                resp = oauth_client.post(
                    self.oauth_url,
                    headers={
                        "Authorization": f"Basic {self.authorization_key}",
                        "RqUID": str(uuid.uuid4()),
                        "Content-Type": "application/x-www-form-urlencoded",
                    },
                    data={"scope": self.scope},
                )
            finally:
                oauth_client.close()
        except httpx.HTTPError as e:
            raise AIClientError(
                f"Ошибка HTTP при OAuth: {e}",
                retriable=True,
                provider=self.name,
            ) from e

        if resp.status_code != 200:
            try:
                err = resp.json()
            except Exception:
                err = resp.text[:300]
            raise AIClientError(
                f"OAuth HTTP {resp.status_code}: {err}",
                retriable=(resp.status_code == 429 or resp.status_code >= 500),
                provider=self.name,
            )

        data = resp.json()
        self._token = data.get("access_token")
        self._expires_at_ms = int(data.get("expires_at", 0))
        if not self._token or not self._expires_at_ms:
            raise AIClientError(
                f"Неожиданный ответ OAuth: {data}",
                retriable=False,
                provider=self.name,
            )
        logger.info(
            "🔐 GigaChat access_token получен (живёт до {})",
            time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime(self._expires_at_ms / 1000)),
        )
        return self._token

    # ── LLM ───────────────────────────────────────────────────────
    def _build_messages(self, system: str, user: str) -> list[dict[str, str]]:
        # GigaChat принимает роли system/user/assistant.
        # На некоторых моделях (Lite) system игнорируется — но мы всё равно
        # передаём, документированное API это поддерживает.
        msgs: list[dict[str, str]] = []
        if system:
            msgs.append({"role": "system", "content": system})
        msgs.append({"role": "user", "content": user})
        return msgs

    def _build_payload(
        self,
        system: str,
        user: str,
        max_tokens: Optional[int],
        temperature: Optional[float],
    ) -> dict[str, Any]:
        return {
            "model": self.model,
            "messages": self._build_messages(system, user),
            "temperature": (
                temperature
                if temperature is not None
                else self.settings.claude_temperature
            ),
            "max_tokens": max_tokens or self.settings.claude_max_tokens,
            "stream": False,
        }

    def _is_retriable(self, response: httpx.Response) -> bool:
        return response.status_code in (408, 409, 429, 500, 502, 503, 504)

    def _do_request(self, payload: dict[str, Any]) -> httpx.Response:
        """Один HTTP-вызов к chat/completions с автообновлением токена."""
        token = self._get_access_token()
        url = f"{self.base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        try:
            return self._http.post(url, json=payload, headers=headers)
        except httpx.HTTPError as e:
            raise AIClientError(
                f"Ошибка HTTP GigaChat: {e}",
                retriable=True,
                provider=self.name,
            ) from e

    @retry(
        retry=retry_if_exception_type((httpx.TimeoutException, httpx.NetworkError)),
        wait=wait_exponential(multiplier=1, min=2, max=20),
        stop=stop_after_attempt(3),
        reraise=True,
    )
    def generate(
        self,
        *,
        system: str,
        user: str,
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
    ) -> str:
        payload = self._build_payload(system, user, max_tokens, temperature)
        logger.debug(
            "🟢 GigaChat generate: model={}, max_tokens={}, temp={}",
            self.model, payload["max_tokens"], payload["temperature"],
        )

        t0 = time.time()
        resp = self._do_request(payload)
        elapsed = time.time() - t0

        # Если 401 — возможно протух токен, пробуем обновить и повторить
        if resp.status_code == 401:
            logger.info("🔐 GigaChat 401 — обновляю access_token и пробую снова")
            self._get_access_token(force_refresh=True)
            resp = self._do_request(payload)

        if not resp.is_success:
            retriable = self._is_retriable(resp)
            try:
                err_body = resp.json()
            except Exception:
                err_body = resp.text[:300]
            logger.error(
                "❌ GigaChat HTTP {} (retriable={}): {}",
                resp.status_code, retriable, err_body,
            )
            raise AIClientError(
                f"HTTP {resp.status_code}: {err_body}",
                retriable=retriable,
                provider=self.name,
            )

        data = resp.json()
        try:
            text = data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as e:
            logger.error("Неожиданный формат ответа GigaChat: {}", data)
            raise AIClientError(
                f"Не удалось извлечь текст: {e}",
                retriable=False,
                provider=self.name,
            ) from e

        usage = data.get("usage", {})
        logger.info(
            "✅ GigaChat: {}/{} tokens, {:.1f}s",
            usage.get("prompt_tokens", "?"),
            usage.get("completion_tokens", "?"),
            elapsed,
        )
        return text.strip()

    def close(self) -> None:
        self._http.close()
