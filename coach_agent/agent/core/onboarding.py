"""
Onboarding-сервис: первая сессия клиента.

Источник: PRD v2.0 раздел 7.3.
Шаги:
1. welcome + 4 кнопки тонов (S_ONBOARD)
2. выбор тона → 4 кнопки старта (S_DIALOG)
3. выбор старта → режим (talk/checkin/desire/workbook/unsure)
4. "не знаю" → стартовый вопрос по тону
5. первый ответ → onboarding_state='tone_picked'
6. завершение первой сессии → onboarding_state='first_session_done'
"""

from __future__ import annotations

from dataclasses import dataclass, field

from agent.core.state_machine import SessionStateMachine
from agent.core.states import (
    InvalidTransitionError,
    SessionState,
)
from agent.core.tones import (
    START_BUTTONS,
    START_QUESTIONS_BY_TONE,
    TONE_BUTTONS,
    Tone,
)
from agent.core.workbook import WorkbookService
from agent.storage.models import ClientRow, SessionRow
from agent.storage.repository import Repository
from agent.utils import get_logger

log = get_logger("onboarding")


@dataclass
class ButtonSpec:
    label: str
    payload: str
    kind: str  # 'tone_pick' | 'start_pick' | 'end_session'


@dataclass
class OnboardingResult:
    """Результат onboarding-действия."""

    text: str
    buttons: list[ButtonSpec] = field(default_factory=list)
    state: SessionState | None = None
    finished: bool = False  # True если онбординг завершён (после первого ответа)


class OnboardingService:
    def __init__(
        self,
        repository: Repository,
        state_machine: SessionStateMachine,
        workbook_service: WorkbookService | None = None,
    ) -> None:
        self._repo = repository
        self._fsm = state_machine
        self._workbook = workbook_service  # Phase 4: опционально

    async def start(self, client: ClientRow, session: SessionRow) -> OnboardingResult:
        """Первый заход клиента — welcome + 4 кнопки тонов."""
        log.info("onboarding.start", client_id=client.id, session_id=session.id)
        if session.current_state != SessionState.S_ONBOARD.value:
            # Клиент уже в S_DIALOG или дальше — welcome не нужен
            return OnboardingResult(
                text="",
                state=SessionState(session.current_state) if session.current_state else None,
            )

        return OnboardingResult(
            text=(
                "Привет! Я WishCoach — ИИ-коуч, который помогает отличить "
                "навязанные желания от истинных. Без цитат, без мотивашки — "
                "только честные вопросы.\n\n"
                "Чтобы мне было проще с тобой говорить, выбери тон диалога:"
            ),
            buttons=[
                ButtonSpec(label=b["label"], payload=b["payload"], kind="tone_pick")
                for b in TONE_BUTTONS
            ],
            state=SessionState.S_ONBOARD,
        )

    async def pick_tone(
        self,
        client: ClientRow,
        session: SessionRow,
        tone: Tone,
        intensity: int = 3,
    ) -> OnboardingResult:
        """Клиент выбрал тон → S_DIALOG + 4 кнопки старта + сохранить в client."""
        log.info(
            "onboarding.pick_tone",
            client_id=client.id,
            tone=tone.value,
            intensity=intensity,
        )
        # Обновляем client
        await self._repo.update_client_tone(client.id, tone.value, intensity)
        # Обновляем session.tone/intensity
        await self._repo.update_session_state(session.id, SessionState.S_DIALOG.value)
        # Перечитываем сессию
        updated_session = await self._repo.get_session_by_id(session.id)
        if updated_session is None:
            raise RuntimeError("pick_tone: session disappeared")
        # Обновляем onboarding_state
        await self._repo.update_client_onboarding(client.id, "tone_picked")

        return OnboardingResult(
            text=(
                f"Отлично, тон: {tone.value}. Можешь сменить в любой момент через /tone.\n\n"
                "С чего начнём?"
            ),
            buttons=[
                ButtonSpec(label=b["label"], payload=b["payload"], kind="start_pick")
                for b in START_BUTTONS
            ],
            state=SessionState.S_DIALOG,
        )

    async def pick_start(
        self,
        client: ClientRow,
        session: SessionRow,
        choice: str,
    ) -> OnboardingResult:
        """Клиент выбрал старт: talk/checkin/desire/workbook/unsure."""
        tone = Tone(client.current_tone)
        log.info("onboarding.pick_start", client_id=client.id, choice=choice, tone=tone.value)

        if choice == "talk":
            text = "Хорошо. Просто говори — что у тебя на уме?"
            buttons: list[ButtonSpec] = []
            state = SessionState.S_DIALOG
        elif choice == "checkin":
            text = (
                "Микро-чекин: я задам 5 коротких вопросов, займёт 3 минуты. "
                "Готов?"
            )
            buttons = []
            state = SessionState.S_DIALOG
        elif choice == "desire":
            text = "Какое желание хочешь разобрать?"
            buttons = []
            state = SessionState.S_DESIRE_DECOMP
            # Переводим сессию в S_DESIRE_DECOMP
            try:
                await self._fsm.transition(session, SessionState.S_DESIRE_DECOMP, reason="start_picked:desire")
            except InvalidTransitionError:
                pass
        elif choice == "workbook":
            # Phase 4: реальный список воркбуков + переход в S_WORKBOOK
            if self._workbook is None:
                text = "Воркбуки пока не подключены. Поговорим о желании?"
                buttons = []
                state = SessionState.S_DIALOG
            else:
                books = self._workbook.list_books()
                if not books:
                    text = (
                        "Воркбуков пока нет на диске. "
                        "Поговорим о желании?"
                    )
                    buttons = []
                    state = SessionState.S_DIALOG
                else:
                    text = (
                        f"📚 Доступные воркбуки ({len(books)}):\n"
                        "Выбери книгу — будем проходить шаг за шагом."
                    )
                    buttons = [
                        ButtonSpec(
                            label=f"📖 {b.title}",
                            payload=f"/workbook {b.slug}",
                            kind="start_pick",
                        )
                        for b in books
                    ]
                    state = SessionState.S_DIALOG
                    # Переход в S_WORKBOOK случится после выбора книги
                    # (в `_handle_workbook_command` через /workbook <slug>)
        elif choice == "unsure":
            # Стартовый вопрос по тону (PRD 7.3.1 шаг 4)
            question = START_QUESTIONS_BY_TONE.get(tone, START_QUESTIONS_BY_TONE[Tone.WARM])
            text = question
            buttons = []
            state = SessionState.S_DIALOG
        else:
            text = "Не понял выбор. Попробуй ещё раз."
            buttons = [
                ButtonSpec(label=b["label"], payload=b["payload"], kind="start_pick")
                for b in START_BUTTONS
            ]
            state = SessionState.S_DIALOG

        return OnboardingResult(text=text, buttons=buttons, state=state)


__all__ = ["OnboardingService", "OnboardingResult", "ButtonSpec"]
