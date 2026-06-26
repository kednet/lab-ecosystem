"""
VK Unbound Handler — обработка новых VK-юзеров до привязки к client.

Phase 7 flow:
1. Юзер шлёт "/start" → state=awaiting_email, ответ: "Привет! Напиши email"
2. Юзер шлёт email → validate → find_client_by_email →
   upsert_client_channel(client.id, "vk", user_id) → state=bound
3. После bind → возвращается welcome-message + 4 кнопки тонов (онбординг
   дальше поведёт SessionService).

Состояние хранится in-memory (на процесс). Если процесс перезапустится —
юзер должен будет пройти /start заново (acceptable для MVP).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from agent.core.tones import TONE_BUTTONS
from agent.storage.repository import Repository
from agent.utils import get_logger

log = get_logger("vk_unbound")


# Простой RFC-5322-lite regex (без строгой полной валидации).
_EMAIL_RE = re.compile(
    r"^[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}$"
)


def validate_email(text: str) -> bool:
    """True если text похож на валидный email."""
    if not text:
        return False
    return bool(_EMAIL_RE.match(text.strip()))


@dataclass
class _State:
    """Состояние unbound-юзера (per-vk-user)."""

    step: str = "awaiting_email"  # 'awaiting_email' | 'bound'
    client_id: int | None = None


@dataclass
class UnboundResult:
    """Результат обработки unbound сообщения."""

    text: str
    buttons: list[dict[str, Any]] = field(default_factory=list)
    # True если юзер только что был привязан (MessageBus должен переотправить
    # в SessionService). True ТОЛЬКО в первом сообщении ПОСЛЕ bind —
    # следующие сообщения уже идут через нормальный путь (т.к. lookup
    # в client_channel найдёт привязку).
    just_bound: bool = False


class VKUnboundHandler:
    """In-memory state-машина для unbound VK-юзеров."""

    def __init__(self, repository: Repository) -> None:
        self._repo = repository
        self._states: dict[int, _State] = {}  # user_id -> state

    def get_state(self, user_id: int) -> _State:
        """Lazy-init состояния для нового юзера."""
        if user_id not in self._states:
            self._states[user_id] = _State()
        return self._states[user_id]

    def clear(self, user_id: int) -> None:
        """Сброс состояния (например, для тестов)."""
        self._states.pop(user_id, None)

    async def handle(self, user_id: int, text: str) -> tuple[str, list[dict[str, Any]]]:
        """Обработать сообщение unbound юзера.

        Возвращает (response_text, response_buttons) — что отправить юзеру.
        """
        state = self.get_state(user_id)
        text_clean = (text or "").strip()

        # 1) "/start" — начинаем flow
        if state.step == "awaiting_email" and text_clean.lower() in ("/start", "start", "начать"):
            state.step = "awaiting_email"  # остаёмся
            return (
                "👋 Привет! Я WishCoach — ИИ-коуч для подписчиков "
                "«Лаборатории желаний».\n\n"
                "Чтобы привязать твой VK к аккаунту, напиши свой email, "
                "который ты указывал при регистрации:",
                [],
            )

        # 2) Прислали email — пробуем найти клиента
        if state.step == "awaiting_email" and validate_email(text_clean):
            client = await self._repo.get_client_by_email(text_clean.lower())
            if client is None:
                return (
                    f"❌ Не нашёл аккаунт с email {text_clean}. "
                    "Проверь, не опечатался ли, и попробуй ещё раз "
                    "(или напиши /start, чтобы начать заново).",
                    [],
                )
            # Bind!
            await self._repo.upsert_client_channel(
                client_id=client.id, channel="vk", external_id=str(user_id)
            )
            state.step = "bound"
            state.client_id = client.id
            log.info(
                "vk.bound",
                user_id=user_id,
                client_id=client.id,
                email=text_clean.lower(),
            )
            return (
                "✅ Готово, твой VK привязан!\n\n"
                "Привет! Я WishCoach — ИИ-коуч, который помогает отличить "
                "навязанные желания от истинных. Без цитат, без мотивашки — "
                "только честные вопросы.\n\n"
                "Выбери тон диалога:",
                [
                    {"label": b["label"], "payload": b["payload"], "kind": "tone_pick"}
                    for b in TONE_BUTTONS
                ],
            )

        # 3) Email невалидный — попросить ввести заново
        if state.step == "awaiting_email" and text_clean:
            return (
                "⚠️ Похоже, это не email. Напиши, пожалуйста, адрес "
                "в формате name@example.com",
                [],
            )

        # 4) bound — сюда попадать не должны (lookup в client_channel найдёт
        #    привязку). Но на всякий случай:
        if state.step == "bound":
            return (
                "Твой аккаунт уже привязан. Попробуй ещё раз "
                "или напиши /start.",
                [],
            )

        # Fallback
        return (
            "Напиши /start, чтобы начать.",
            [],
        )


__all__ = [
    "VKUnboundHandler",
    "validate_email",
    "UnboundResult",
]
