"""
VK-канал: Long Poll listener + ChannelAdapter.

Phase 7:
- VKAdapter — нормализует inbound (vk_api события) в NormalizedMessage
- vk_keyboard_from_buttons — рендерит наш ButtonSpec[] в VK keyboard JSON
- VKLongPollRunner — фоновый поток, слушает VK API, диспатчит в MessageBus
- dedup по event.message_id (TTL 5 мин)
- unbound_handlers — состояние «не привязан» (in-memory; до первой верификации)

Транспорт: Long Poll (не требует публичного URL, идеально для Render Free).
"""

from __future__ import annotations

import asyncio
import json
import threading
import time
from collections.abc import Coroutine
from typing import Any

from agent.channels.base import ChannelAdapter
from agent.channels.vk_unbound import VKUnboundHandler
from agent.core.message_bus import MessageBus
from agent.storage.repository import Repository
from agent.utils import get_logger

log = get_logger("channel_vk")


# === Keyboard renderer ===

def vk_keyboard_from_buttons(buttons: list[dict[str, Any]]) -> str:
    """Превращает список наших кнопок (label/payload/kind) в VK keyboard JSON.

    VK ждёт `{"one_time": bool, "buttons": [[{action:{type,label},color}], ...]}`.
    Наши payload'ы (warm:3, talk, /workbook atomic_habits) — это просто текст,
    который придёт в `event.text` при нажатии (для reply-keyboard) или в
    `event.payload` (для inline, но мы пока используем text-кнопки).
    """
    rows: list[list[dict[str, Any]]] = []
    for b in buttons:
        # payload — это строка, которую мы хотим получить в event.text
        # Для VK text-кнопки: action.type="text", label=label
        rows.append(
            [
                {
                    "action": {
                        "type": "text",
                        "label": b.get("label", b.get("payload", "?"))[:40],
                        # payload не поддерживается в text-кнопках, поэтому
                        # мы дублируем его в label для дебага или используем
                        # как сам текст сообщения (см. VKAdapter).
                    },
                    "color": _vk_color_for_kind(b.get("kind", "")),
                }
            ]
        )
    return json.dumps(
        {"one_time": False, "buttons": rows},
        ensure_ascii=False,
    )


def _vk_color_for_kind(kind: str) -> str:
    """Цвет кнопки в VK: primary/secondary/positive/negative."""
    return {
        "tone_pick": "primary",
        "start_pick": "positive",
        "end_session": "negative",
    }.get(kind, "secondary")


# === Adapter ===

class VKAdapter(ChannelAdapter):
    channel_name = "vk"

    def normalize_inbound(self, raw: dict[str, Any]) -> dict[str, Any] | None:
        """Из VK-события в сырьё для NormalizedMessage.

        `raw` ожидается в формате:
            {
                "user_id": int,
                "text": str,
                "message_id": int,
                "payload": str | None,  # для callback-кнопок (не используем пока)
                "peer_id": int,
            }

        Возвращает dict, который MessageBus дальше превратит в NormalizedMessage,
        либо None если raw пустой.
        """
        if not raw:
            return None
        text = raw.get("text", "")
        user_id = raw.get("user_id")
        if user_id is None or not text:
            return None
        return {
            "user_id": int(user_id),
            "text": str(text),
            "message_id": raw.get("message_id"),
            "peer_id": raw.get("peer_id", user_id),
            "payload": raw.get("payload"),
        }

    def format_outbound(
        self,
        response_text: str,
        buttons: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """CoachResponse → payload для VK messages.send."""
        return {
            "text": response_text,
            "keyboard": vk_keyboard_from_buttons(buttons) if buttons else None,
        }


# === Long Poll runner ===

class VKLongPollRunner(threading.Thread):
    """Фоновый поток: слушает VK Long Poll, диспатчит в MessageBus.

    Использование:
        runner = VKLongPollRunner(token, group_id, bus, repo)
        runner.start()
        ...
        runner.stop()
    """

    DEDUP_TTL_SEC = 300.0  # 5 минут

    def __init__(
        self,
        token: str,
        group_id: int,
        message_bus: MessageBus,
        repository: Repository,
        loop: asyncio.AbstractEventLoop | None = None,
    ) -> None:
        super().__init__(name="VKLongPoll", daemon=True)
        self._token = token
        self._group_id = group_id
        self._bus = message_bus
        self._repo = repository
        self._loop = loop  # main asyncio loop (нужен для run_coroutine_threadsafe)
        self._stop_event = threading.Event()
        self._seen_message_ids: dict[int, float] = {}
        self._unbound = VKUnboundHandler(repository)

    def stop(self) -> None:
        self._stop_event.set()
        log.info("vk.runner.stop_requested")

    def _is_duplicate(self, message_id: int | None) -> bool:
        """True если этот message_id уже видели (и не истёк TTL)."""
        if message_id is None:
            return False
        now = time.monotonic()
        # Чистим протухшие
        expired = [mid for mid, t in self._seen_message_ids.items() if now - t > self.DEDUP_TTL_SEC]
        for mid in expired:
            self._seen_message_ids.pop(mid, None)
        if message_id in self._seen_message_ids:
            return True
        self._seen_message_ids[message_id] = now
        return False

    def _dispatch_coroutine(self, coro: Coroutine) -> None:
        """Запустить async-корутину в основном event loop из потока."""
        if self._loop is None:
            log.error("vk.runner.no_event_loop")
            return
        try:
            asyncio.run_coroutine_threadsafe(coro, self._loop)
        except Exception:
            log.exception("vk.runner.dispatch_failed")

    def _handle_event(self, event: dict[str, Any]) -> None:
        """Обработать одно VK-событие (вызывается из Long Poll loop)."""
        # VK Long Poll события имеют тип и поля.
        # Нас интересует только MESSAGE_NEW (type=4).
        # Используем dict-интерфейс — одинаково работает и с реальным vk_api,
        # и с тестовыми mock'ами.
        if event.get("type") != 4:  # MESSAGE_NEW
            return
        # to_me — флаг «сообщение в ЛС сообщества». Для группы — всегда True
        # в MESSAGE_NEW (мы и так слушаем только inbound).
        user_id = event.get("user_id")
        text = event.get("text") or ""
        message_id = event.get("message_id")
        if user_id is None or not text:
            return
        if self._is_duplicate(message_id):
            log.info("vk.event.duplicate", message_id=message_id)
            return

        log.info("vk.event.received", user_id=user_id, text_len=len(text), message_id=message_id)

        # Шаг 1: ищем привязку (client_channel)
        try:
            client = self._run_async(
                self._repo.find_client_by_channel("vk", str(user_id))
            )
        except Exception:
            log.exception("vk.lookup_failed", user_id=user_id)
            return

        if client is not None:
            # Привязан → нормальный диспатч
            raw = {
                "user_id": user_id,
                "text": text,
                "message_id": message_id,
                "peer_id": event.get("peer_id", user_id),
                "payload": event.get("payload"),
            }
            from agent.core.message_bus import NormalizedMessage

            msg = NormalizedMessage(
                client_id=client.id,
                text=text,
                channel="vk",
                raw=raw,
            )
            self._dispatch_coroutine(self._send_response(msg, user_id))
        else:
            # Unbound → handled by VKUnboundHandler
            log.info("vk.event.unbound", user_id=user_id)
            try:
                response_text, response_buttons = self._run_async(
                    self._unbound.handle(user_id, text)
                )
            except Exception:
                log.exception("vk.unbound_failed", user_id=user_id)
                return
            self._dispatch_coroutine(
                self._send_text(user_id, response_text, response_buttons)
            )

    async def _send_response(self, msg, user_id: int) -> None:
        """Диспатч + отправка ответа обратно в VK."""
        resp = await self._bus.dispatch(msg)
        await self._send_text(user_id, resp.text, resp.buttons)

    async def _send_text(
        self,
        user_id: int,
        text: str,
        buttons: list[dict[str, Any]] | None = None,
    ) -> None:
        """Отправляет текст + (опц.) кнопки в VK через VK API."""
        # NB: api инициализируется в run() (Long Poll создаёт VK session).
        api = getattr(self, "_vk_api", None)
        if api is None:
            log.warning("vk.send.api_not_ready", user_id=user_id)
            return
        try:
            import time as _time

            kwargs: dict[str, Any] = {
                "user_id": user_id,
                "message": text[:4000],
                "random_id": int(_time.time() * 1000),
            }
            if buttons:
                kwargs["keyboard"] = vk_keyboard_from_buttons(buttons)
            api.messages.send(**kwargs)
            log.info("vk.sent", user_id=user_id, text_len=len(text), has_kb=bool(buttons))
        except Exception:
            log.exception("vk.send.failed", user_id=user_id)

    def _run_async(self, coro: Coroutine) -> Any:
        """Запустить async-корутину в основном loop и дождаться результата.

        Используется в _handle_event (Long Poll loop — синхронный).
        """
        if self._loop is None:
            raise RuntimeError("no event loop set on VKLongPollRunner")
        future = asyncio.run_coroutine_threadsafe(coro, self._loop)
        return future.result(timeout=10.0)

    def _vk_make_session(self) -> tuple[Any, Any]:
        """Создаёт vk_api сессию (с MITM-обвязкой, как в wishlibrarian)."""
        try:
            import requests
            import vk_api  # type: ignore
        except ImportError as e:
            raise RuntimeError(
                "vk_api не установлен. Поставь: pip install 'wishcoach[vk]'"
            ) from e

        session = requests.Session()
        # Наследуем MITM-настройки из agent.config
        from agent.config import apply_mitm_globals, settings

        apply_mitm_globals()
        if not settings.verify_ssl:
            session.verify = False
            import warnings

            from urllib3.exceptions import InsecureRequestWarning
            warnings.filterwarnings("ignore", category=InsecureRequestWarning)
        # VK через корпоративный SOCKS — не нужно (Long Poll сам обрабатывает),
        # но если в settings.socks5_proxy задан, requests его подхватит через
        # SOCKS5_PROXY env, если установлен PySocks.
        vk_session = vk_api.VkApi(token=self._token, session=session)
        return vk_session.get_api(), vk_session

    def run(self) -> None:
        """Главный цикл Long Poll."""
        try:
            api, vk_session = self._vk_make_session()
        except Exception:
            log.exception("vk.session_failed")
            return
        self._vk_api = api
        try:
            from vk_api.longpoll import VkLongPoll  # type: ignore
        except ImportError:
            log.error("vk.longpoll_import_failed")
            return

        try:
            longpoll = VkLongPoll(vk_session, wait=25, mode=234, group_id=self._group_id)
        except Exception:
            log.exception("vk.longpoll_init_failed")
            return

        # Отключаем trust_env на LongPoll session (если нет явного proxy)
        from agent.config import settings
        if not settings.socks5_proxy:
            try:
                longpoll.session.trust_env = False
            except AttributeError:
                pass

        log.info("vk.longpoll.started", group_id=self._group_id)
        try:
            for event in longpoll.listen():
                if self._stop_event.is_set():
                    log.info("vk.longpoll.stopping")
                    break
                # Конвертируем vk_api Event в dict (для тестируемости)
                ev_dict = {
                    "type": int(event.type),
                    "user_id": getattr(event, "user_id", None),
                    "text": getattr(event, "text", "") or "",
                    "message_id": getattr(event, "message_id", None),
                    "peer_id": getattr(event, "peer_id", None),
                    "payload": getattr(event, "payload", None),
                }
                try:
                    self._handle_event(ev_dict)
                except Exception:
                    log.exception("vk.handle_event_failed", event_type=ev_dict["type"])
        except Exception:
            log.exception("vk.longpoll_crashed")
        finally:
            log.info("vk.longpoll.stopped")


__all__ = [
    "VKAdapter",
    "VKLongPollRunner",
    "vk_keyboard_from_buttons",
]
