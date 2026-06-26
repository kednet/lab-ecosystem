"""
SessionService — главный оркестратор обработки сообщений.

Pipeline process_message():
1. crisis-detection (ВСЕГДА первый — инвариант безопасности)
2. get_or_create_session (с welcome_back)
3. диспетчер по current_state
4. persist user message + assistant message + cost
5. arm idle timer

Все stubs (S_DECOMP/S_WORKBOOK/S_ACHIEVE/S_RELEASE) возвращают friendly text
без вызова AI.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from agent.ai.factory import AIClient, AIError, AIUnconfiguredError, get_ai_client
from agent.ai.prompts import ContextBlock, build_system_prompt
from agent.ai.tools import TOOL_SCHEMAS, ToolDispatcher
from agent.core.crisis import CRISIS_RESPONSE, detect_crisis, hash_message
from agent.core.decomp import days_for
from agent.core.decomposer import DecomposerService
from agent.core.detector import DetectorDepth, DetectorService
from agent.core.idle import IdleTimer
from agent.core.onboarding import OnboardingService
from agent.core.state_machine import SessionStateMachine
from agent.core.states import (
    InvalidTransitionError,
    SessionState,
)
from agent.core.tones import Tone, get_enabled_modules, get_module3_replacement
from agent.core.workbook import WorkbookService
from agent.core.workbook_parser import Workbook, WorkbookStep
from agent.storage.models import ClientRow, DesireRow, SessionRow, WorkbookRunRow
from agent.storage.repository import Repository
from agent.utils import get_logger

log = get_logger("session")


@dataclass
class CoachResponse:
    text: str
    buttons: list[dict] = field(default_factory=list)
    state: SessionState | None = None
    welcome_back: str | None = None
    crisis_flag: bool = False
    cost_usd: float = 0.0
    finished: bool = False  # True если сессия завершена (crisis / end)


class SessionService:
    def __init__(
        self,
        repository: Repository,
        state_machine: SessionStateMachine,
        onboarding: OnboardingService,
        detector: DetectorService,
        idle_timer: IdleTimer,
        ai_client: AIClient | None = None,
    ) -> None:
        self._repo = repository
        self._fsm = state_machine
        self._onboarding = onboarding
        self._detector = detector
        self._idle = idle_timer
        self._ai = ai_client  # если None — get_ai_client() на каждый вызов
        # detector state per session
        self._detector_states: dict[int, object] = {}  # session_id -> DetectorSession
        # tool dispatcher + decomposer
        self._tools = ToolDispatcher(repository)
        self._decomposer = DecomposerService(repository, ai_client, self._tools)
        # workbook service (Phase 4)
        self._workbook = WorkbookService(repository, ai_client)
        # active desire per session (для /decompose <N> и контекста S_DECOMP)
        self._active_desire: dict[int, int] = {}  # session_id -> desire_id
        # deadline_type per desire (запоминаем выбор юзера)
        self._current_deadline_type: dict[int, str] = {}  # desire_id -> type
        # channel hint for context
        self._default_channel = "web"
        # === Phase 8: cost budget accumulator (per session_id) ===
        # Сессия с cost > 1.0 USD блокируется. Сброс при новой сессии.
        self._session_cost: dict[int, float] = {}
        self._session_cost_budget: float = 1.0  # USD per session

    # === Получение/создание сессии ===

    async def get_or_create_session(
        self,
        client: ClientRow,
        channel: str = "web",
        mode: str = "dialog",
    ) -> tuple[SessionRow, str | None]:
        """Возвращает (сессия, welcome_back_text)."""
        active = await self._repo.get_active_session(client.id)
        if active is not None:
            return active, None

        last = await self._repo.get_last_session(client.id)
        welcome_back: str | None = None
        if last and last.ended_at:
            # Считаем gap
            try:
                last_dt = datetime.fromisoformat(last.ended_at.replace("Z", "+00:00"))
                gap = (datetime.now(last_dt.tzinfo) - last_dt).total_seconds() / 86400
                if last.ended_reason in ("user_paused", "idle_15min", "error_recoverable"):
                    welcome_back = SessionStateMachine.welcome_back_template(gap)
            except (ValueError, TypeError):
                welcome_back = None

        # Создаём новую
        new_session = await self._repo.create_session(
            client_id=client.id,
            tone=client.current_tone,
            tone_intensity=client.tone_intensity,
            mode=mode,
        )
        # Phase 8: сбросить cost accumulator для новой сессии
        self._session_cost.pop(new_session.id, None)
        log.info(
            "session.created",
            session_id=new_session.id,
            client_id=client.id,
            welcome_back=bool(welcome_back),
        )
        return new_session, welcome_back

    # === Phase 8: cost budget helpers ===

    def _is_budget_exceeded(self, session_id: int) -> bool:
        """True если session_id уже превысил budget."""
        return self._session_cost.get(session_id, 0.0) > self._session_cost_budget

    def get_session_cost(self, session_id: int) -> float:
        """Текущий накопленный cost (для тестов / отладки)."""
        return self._session_cost.get(session_id, 0.0)

    # === Главный pipeline ===

    async def process_message(
        self,
        client: ClientRow,
        text: str,
        channel: str = "web",
    ) -> CoachResponse:
        """
        Главный entry-point. Crisis-check ПЕРВЫМ.
        Возвращает CoachResponse с text/buttons/state/welcome_back.
        """
        # === 1. CRISIS-DETECTION (инвариант) ===
        matched_pattern = detect_crisis(text)
        if matched_pattern is not None:
            return await self._handle_crisis(client, text, channel, matched_pattern)

        # === 2. Сессия ===
        session, welcome_back = await self.get_or_create_session(client, channel=channel)
        await self._repo.touch_client(client.id)

        # === 3. Диспетчер по состоянию ===
        state = SessionState(session.current_state) if session.current_state else SessionState.S_DIALOG

        if state == SessionState.S_ONBOARD:
            resp = await self._handle_onboarding_dialog(client, session, text)
        elif state == SessionState.S_DIALOG:
            resp = await self._handle_dialog(client, session, text, channel)
        elif state == SessionState.S_DESIRE_DECOMP:
            resp = await self._handle_desire_decomp(client, session, text, channel)
        elif state == SessionState.S_DETECTOR:
            resp = await self._handle_detector(client, session, text, channel)
        elif state == SessionState.S_DECISION:
            resp = await self._handle_decision(client, session, text, channel)
        elif state == SessionState.S_DECOMP:
            resp = await self._handle_decomp(client, session, text, channel)
        elif state == SessionState.S_WORKBOOK:
            resp = await self._handle_workbook(client, session, text)
        elif state == SessionState.S_ACHIEVE:
            resp = await self._handle_achieve(client, session, text)
        elif state == SessionState.S_RELEASE:
            resp = await self._handle_release(client, session)
        elif state in (SessionState.S_IDLE_SAVED, SessionState.S_CRISIS_STOP):
            # Возврат в диалог
            try:
                await self._fsm.transition(session, SessionState.S_DIALOG, reason="auto_resume")
                session = await self._repo.get_session_by_id(session.id) or session
            except InvalidTransitionError:
                pass
            resp = await self._handle_dialog(client, session, text, channel)
        else:
            resp = CoachResponse(text="Что-то пошло не так. Попробуй ещё раз.", state=state)

        # === 4. Persist + arm idle ===
        await self._repo.append_message(session.id, "user", text)
        if resp.text:
            await self._repo.append_message(session.id, "assistant", resp.text)

        # Cost update
        if resp.cost_usd > 0:
            # Phase 8: накопить в budget-аккумулятор
            self._session_cost[session.id] = (
                self._session_cost.get(session.id, 0.0) + resp.cost_usd
            )
            await self._repo.update_session_state(
                session.id, (resp.state or state).value, resp.cost_usd
            )

        # Idle timer
        self._idle.arm(session.id, lambda: self._on_idle(session.id))

        if welcome_back and not resp.welcome_back:
            resp.welcome_back = welcome_back
        if not resp.state:
            resp.state = state

        log.info(
            "session.processed",
            client_id=client.id,
            session_id=session.id,
            state=(resp.state or state).value,
            cost=round(resp.cost_usd, 6),
            crisis=resp.crisis_flag,
        )
        return resp

    # === Handlers по состояниям ===

    async def _handle_crisis(
        self,
        client: ClientRow,
        text: str,
        channel: str,
        matched_pattern: str,
    ) -> CoachResponse:
        session, _ = await self.get_or_create_session(client, channel=channel)
        await self._fsm.transition_to_crisis(session)
        session = await self._repo.get_session_by_id(session.id) or session
        # Помечаем сессию
        await self._repo.update_session_state(
            session.id, SessionState.S_CRISIS_STOP.value
        )
        # Phase 8: явно помечаем crisis_flag=1 (для аналитики / scheduler-а)
        try:
            await self._repo.mark_session_crisis(session.id)
        except Exception:
            log.exception("session.mark_crisis_failed", session_id=session.id)
        # Логируем (только хэш)
        await self._repo.log_crisis(
            client_id=client.id,
            session_id=session.id,
            channel=channel,
            message_hash=hash_message(text),
            matched_pattern=matched_pattern,
        )
        # Сохраняем user-сообщение с пометками
        await self._repo.append_message(
            session.id, "user", text,
            is_crisis=True, excluded_from_training=True,
        )
        await self._repo.append_message(
            session.id, "assistant", CRISIS_RESPONSE,
            is_crisis=True, excluded_from_training=True,
        )
        # Помечаем client.last_seen_at
        await self._repo.touch_client(client.id)
        log.warning(
            "session.crisis_detected",
            client_id=client.id,
            session_id=session.id,
            pattern=matched_pattern,
        )
        return CoachResponse(
            text=CRISIS_RESPONSE,
            state=SessionState.S_CRISIS_STOP,
            crisis_flag=True,
            finished=True,
        )

    async def _handle_onboarding_dialog(
        self, client: ClientRow, session: SessionRow, text: str
    ) -> CoachResponse:
        # На онбординге можно попасть через текст "выбираю тёплый" и т.п.
        # Простое определение по ключевым словам
        text_low = text.lower()
        tone_map = {
            "тёплый": Tone.WARM, "теплый": Tone.WARM, "warm": Tone.WARM, "🫂": Tone.WARM,
            "чёткий": Tone.CLEAR, "четкий": Tone.CLEAR, "clear": Tone.CLEAR, "📊": Tone.CLEAR,
            "смелый": Tone.BOLD, "bold": Tone.BOLD, "⚡": Tone.BOLD,
            "мягкий": Tone.SOFT, "soft": Tone.SOFT, "🌙": Tone.SOFT,
        }
        chosen: Tone | None = None
        for kw, t in tone_map.items():
            if kw in text_low:
                chosen = t
                break
        if chosen is None:
            # Не поняли — просим выбрать кнопкой
            return CoachResponse(
                text=(
                    "Пока я понимаю только выбор тона кнопкой. "
                    "Попробуй нажать одну из 4 кнопок выше."
                ),
                state=SessionState.S_ONBOARD,
            )
        result = await self._onboarding.pick_tone(client, session, chosen, 3)
        return CoachResponse(
            text=result.text,
            buttons=[b.__dict__ for b in result.buttons],
            state=result.state,
        )

    async def _handle_dialog(
        self, client: ClientRow, session: SessionRow, text: str, channel: str
    ) -> CoachResponse:
        # Команды
        text_low = text.strip().lower()
        if text_low.startswith("/tone"):
            return await self._handle_tone_command(client, text)
        if text_low.startswith("/desire add "):
            title = text[len("/desire add "):].strip().strip('"').strip("'")
            return await self._start_desire(client, session, title)
        if text_low in ("/desire", "/desires"):
            return await self._list_desires(client)
        if text_low.startswith("/checkin"):
            return await self._start_checkin(client, session)
        if text_low.startswith("/cancel") or text_low == "/cancel":
            return await self._cancel_session(client, session)
        if text_low in ("/start", "/resume"):
            return CoachResponse(text="Продолжаем!", state=SessionState.S_DIALOG)
        # /detector — допустимо в любом диалоговом состоянии
        if text_low.startswith("/detector"):
            depth_map = {
                "/detector express": DetectorDepth.EXPRESS,
                "/detector standard": DetectorDepth.STANDARD,
                "/detector deep": DetectorDepth.DEEP,
                "/detector": DetectorDepth.EXPRESS,
            }
            for cmd, depth in depth_map.items():
                if text_low.startswith(cmd):
                    return await self._launch_detector(client, session, depth)
        # /decompose <N> — прямой переход в S_DECOMP
        if text_low.startswith("/decompose"):
            return await self._start_decompose(client, session, text)
        # /steps — список шагов текущего desire
        if text_low.startswith("/steps"):
            return await self._list_steps(client, session)
        # /workbook [slug] — список книг / прямой старт воркбука
        if text_low.startswith("/workbook"):
            return await self._handle_workbook_command(client, session, text)

        # Обычный диалог через AI
        return await self._call_ai(client, session, text, channel, mode="dialog")

    async def _handle_tone_command(
        self, client: ClientRow, text: str
    ) -> CoachResponse:
        parts = text.split()
        if len(parts) < 2:
            return CoachResponse(text="Использование: /tone <warm|clear|bold|soft> [1-5]")
        tone_map = {
            "warm": Tone.WARM, "тёплый": Tone.WARM, "теплый": Tone.WARM,
            "clear": Tone.CLEAR, "чёткий": Tone.CLEAR, "четкий": Tone.CLEAR,
            "bold": Tone.BOLD, "смелый": Tone.BOLD,
            "soft": Tone.SOFT, "мягкий": Tone.SOFT,
        }
        tone = tone_map.get(parts[1].lower())
        if tone is None:
            return CoachResponse(text=f"Не знаю тон '{parts[1]}'. Доступные: warm, clear, bold, soft.")
        intensity = 3
        if len(parts) >= 3:
            try:
                intensity = max(1, min(5, int(parts[2])))
            except ValueError:
                pass
        await self._repo.update_client_tone(client.id, tone.value, intensity)
        return CoachResponse(
            text=f"Тон изменён на {tone.value} × {intensity}.",
            state=SessionState.S_DIALOG,
        )

    async def _start_desire(
        self, client: ClientRow, session: SessionRow, title: str
    ) -> CoachResponse:
        if not title:
            return CoachResponse(text="Какое желание разобрать? Напиши: /desire add \"купить MacBook\"")
        await self._repo.create_desire(client_id=client.id, title=title)
        try:
            await self._fsm.transition(session, SessionState.S_DESIRE_DECOMP, reason="user_desire")
        except InvalidTransitionError:
            pass
        return CoachResponse(
            text=(
                f'Сохранил желание: "{title}".\n\n'
                "Хочешь разобрать его детектором (5/12/20 вопросов)? "
                "Или поговорим в диалоге?"
            ),
            state=SessionState.S_DESIRE_DECOMP,
        )

    async def _start_checkin(
        self, client: ClientRow, session: SessionRow
    ) -> CoachResponse:
        # Запускаем express-детектор, привязанный к "общему чекину"
        # В Phase 1 упрощённо: создаём желание-заглушку
        desire = await self._repo.create_desire(
            client_id=client.id, title="Микро-чекин", detector_depth="express"
        )
        detector_state = self._detector.start(
            desire_id=desire.id,
            depth=DetectorDepth.EXPRESS,
            enabled_modules=get_enabled_modules(Tone(client.current_tone), client.tone_intensity),
        )
        self._detector_states[session.id] = detector_state
        try:
            await self._fsm.transition(session, SessionState.S_DETECTOR, reason="checkin")
        except InvalidTransitionError:
            pass
        from agent.core.detector import QUESTIONS
        idx = detector_state.question_indices[0]
        q = QUESTIONS[idx - 1]
        return CoachResponse(
            text=f"Микро-чекин (5 вопросов). Вопрос 1: {q.text}",
            state=SessionState.S_DETECTOR,
        )

    async def _list_desires(self, client: ClientRow) -> CoachResponse:
        desires = await self._repo.get_active_desires(client.id)
        if not desires:
            return CoachResponse(text="У тебя пока нет активных желаний.")
        lines = ["Активные желания:"]
        for d in desires[:10]:
            verdict = d.verdict_label or "—"
            lines.append(f"  #{d.id}: {d.title} ({verdict})")
        return CoachResponse(text="\n".join(lines), state=SessionState.S_DIALOG)

    async def _cancel_session(
        self, client: ClientRow, session: SessionRow
    ) -> CoachResponse:
        try:
            await self._fsm.transition(session, SessionState.S_DIALOG, reason="user_cancel")
        except InvalidTransitionError:
            pass
        return CoachResponse(text="Ок, отменил. Мы в обычном диалоге.", state=SessionState.S_DIALOG)

    async def _handle_desire_decomp(
        self, client: ClientRow, session: SessionRow, text: str, channel: str
    ) -> CoachResponse:
        text_low = text.strip().lower()
        # Команда детектора
        depth_map = {
            "/detector express": DetectorDepth.EXPRESS,
            "/detector standard": DetectorDepth.STANDARD,
            "/detector deep": DetectorDepth.DEEP,
            "/detector": DetectorDepth.EXPRESS,  # default
        }
        for cmd, depth in depth_map.items():
            if text_low.startswith(cmd):
                return await self._launch_detector(client, session, depth)
        # Иначе — продолжаем диалог
        return await self._call_ai(client, session, text, channel, mode="desire_decomp")

    async def _launch_detector(
        self, client: ClientRow, session: SessionRow, depth: DetectorDepth
    ) -> CoachResponse:
        # Берём последнее активное желание или создаём заглушку
        desires = await self._repo.get_active_desires(client.id)
        if desires:
            desire = desires[0]
        else:
            desire = await self._repo.create_desire(
                client_id=client.id, title="Разобрать", detector_depth=depth.value
            )
        tone = Tone(client.current_tone)
        detector_state = self._detector.start(
            desire_id=desire.id,
            depth=depth,
            enabled_modules=get_enabled_modules(tone, client.tone_intensity),
        )
        self._detector_states[session.id] = detector_state
        try:
            await self._fsm.transition(session, SessionState.S_DETECTOR, reason="detector_start")
        except InvalidTransitionError:
            pass
        from agent.core.detector import QUESTIONS
        idx = detector_state.question_indices[0]
        q = QUESTIONS[idx - 1]
        replacement = get_module3_replacement(tone) if q.idx == 9 else None
        if replacement:
            q_text = replacement
        else:
            q_text = q.text
        return CoachResponse(
            text=f"Детектор {depth.value} ({len(detector_state.question_indices)} вопросов). Вопрос 1: {q_text}",
            state=SessionState.S_DETECTOR,
        )

    async def _handle_detector(
        self, client: ClientRow, session: SessionRow, text: str, channel: str
    ) -> CoachResponse:
        detector_state = self._detector_states.get(session.id)
        if detector_state is None:
            # Сброс — нет состояния, выходим в диалог
            return CoachResponse(text="Детектор сбился. Возвращаюсь в диалог.", state=SessionState.S_DIALOG)
        # Записываем ответ
        self._detector.record_answer(detector_state, text)
        # Следующий вопрос
        tone = Tone(client.current_tone)
        next_q = self._detector.next_question(
            detector_state,
            replacement_q9=get_module3_replacement(tone),
        )
        if next_q is None:
            # Детектор закончен
            outcome = self._detector.finalize(detector_state)
            # Обновляем desire
            await self._repo.update_desire_verdict(
                desire_id=detector_state.desire_id,
                kind="mixed" if "mixed" in outcome.verdict_label else (
                    "imposed" if "imposed" in outcome.verdict_label or outcome.verdict_label == "imposed" else "true"
                ),
                score=outcome.score,
                verdict_label=outcome.verdict_label,
                module_scores=outcome.module_scores,
                detector_depth=outcome.depth.value,
                reasoning=outcome.reasoning,
            )
            # Переход в S_DECISION
            try:
                await self._fsm.transition(session, SessionState.S_DECISION, reason="verdict")
            except InvalidTransitionError:
                pass
            self._detector_states.pop(session.id, None)
            return CoachResponse(
                text=(
                    f"Вердикт: {outcome.verdict_label}\n"
                    f"{outcome.reasoning}\n\n"
                    f"Счёт: {outcome.score:.2f} (модули: {outcome.module_scores})"
                ),
                state=SessionState.S_DECISION,
            )
        # Следующий вопрос
        return CoachResponse(
            text=f"Вопрос {len(detector_state.answers) + 1}: {next_q.text}",
            state=SessionState.S_DETECTOR,
        )

    # === /decompose, /steps (Phase 5) ===

    async def _start_decompose(
        self, client: ClientRow, session: SessionRow, text: str
    ) -> CoachResponse:
        """`/decompose <N>` или `/decompose` — переход в S_DECOMP с явным желанием."""
        parts = text.split(maxsplit=1)
        arg = parts[1].strip() if len(parts) > 1 else ""

        desires = await self._repo.get_active_desires(client.id)
        if not desires:
            return CoachResponse(
                text="Нет активного желания. Создай через /desire add «...»",
                state=SessionState.S_DIALOG,
            )

        target: DesireRow | None = None
        if arg.isdigit():
            did = int(arg)
            target = next((d for d in desires if d.id == did), None)
            if target is None:
                return CoachResponse(
                    text=f"Желание #{did} не найдено. Активные: "
                         + ", ".join(f"#{d.id}" for d in desires),
                    state=SessionState.S_DIALOG,
                )
        else:
            target = desires[0]

        self._active_desire[session.id] = target.id
        try:
            await self._fsm.transition(
                session, SessionState.S_DECOMP, reason="decompose_command"
            )
        except InvalidTransitionError:
            pass
        return CoachResponse(
            text=(
                f"🎯 Желание «{target.title}» — выбери горизонт:\n\n"
                "AI предложит 3-7 шагов. Или введи свои."
            ),
            state=SessionState.S_DECOMP,
            buttons=self._decomposer.type_buttons(),
        )

    async def _list_steps(
        self, client: ClientRow, session: SessionRow
    ) -> CoachResponse:
        """`/steps` — список шагов текущего активного желания."""
        desires = await self._repo.get_active_desires(client.id)
        if not desires:
            return CoachResponse(
                text="Нет активного желания.",
                state=SessionState.S_DIALOG,
            )
        desire = desires[0]
        steps = await self._repo.list_steps(desire.id)
        if not steps:
            return CoachResponse(
                text=f"У желания «{desire.title}» пока нет шагов. /decompose — начать.",
                state=SessionState.S_DIALOG,
            )
        lines = [f"📋 Шаги «{desire.title}»:"]
        for i, s in enumerate(steps, 1):
            mark = "✓" if s.status == "done" else ("⏭" if s.status == "skipped" else "☐")
            lines.append(f"  {i}. {mark} {s.title}")
        return CoachResponse(
            text="\n".join(lines),
            state=SessionState.S_DIALOG,
        )

    async def _handle_decision(
        self, client: ClientRow, session: SessionRow, text: str, channel: str
    ) -> CoachResponse:
        text_low = text.strip().lower()
        if text_low in ("принять", "ок", "хорошо", "дальше", "согласен", "согласна"):
            # Куда дальше? Зависит от последнего вердикта
            # Простое правило: imposed/mostly_imposed → S_RELEASE, иначе S_DECOMP
            desires = await self._repo.get_active_desires(client.id)
            last = desires[0] if desires else None
            if last and last.verdict_label and ("imposed" in last.verdict_label):
                try:
                    await self._fsm.transition(session, SessionState.S_RELEASE, reason="verdict:imposed")
                except InvalidTransitionError:
                    pass
                return CoachResponse(
                    text=(
                        "Желание преимущественно навязанное. "
                        "Хочешь отпустить его без вины? "
                        "Я проведу короткий ритуал (Phase 5), а пока — просто признай: "
                        "это не твоё, и это нормально."
                    ),
                    state=SessionState.S_RELEASE,
                )
            else:
                try:
                    await self._fsm.transition(session, SessionState.S_DECOMP, reason="verdict:true")
                except InvalidTransitionError:
                    pass
                return CoachResponse(
                    text=(
                        "Желание идёт изнутри. Декомпозиция на шаги с дедлайнами "
                        "появится в Phase 5. Пока — расскажи подробнее, "
                        "какой первый маленький шаг ты готов сделать?"
                    ),
                    state=SessionState.S_DECOMP,
                )
        if text_low in ("пересмотреть", "не согласен", "не согласна", "ещё раз", "глубже"):
            try:
                await self._fsm.transition(session, SessionState.S_DESIRE_DECOMP, reason="verdict:disagree")
            except InvalidTransitionError:
                pass
            return CoachResponse(
                text="Хорошо, вернёмся к желанию и пройдём детектор глубже.",
                state=SessionState.S_DESIRE_DECOMP,
            )
        return CoachResponse(
            text="Скажи «принять» или «пересмотреть».",
            state=SessionState.S_DECISION,
        )

    # === S_DECOMP handlers (Phase 5) ===

    async def _handle_decomp(
        self, client: ClientRow, session: SessionRow, text: str, channel: str
    ) -> CoachResponse:
        """S_DECOMP — выбор типа дедлайна, генерация/правка шагов, трекинг."""
        # Определяем текущий desire (последний активный)
        desires = await self._repo.get_active_desires(client.id)
        if not desires:
            return CoachResponse(
                text="Нет активного желания. Создай через /desire add «...»",
                state=SessionState.S_DIALOG,
            )
        desire = desires[0]  # MVP: берём первый/последний
        self._active_desire[session.id] = desire.id

        mode = self._decomposer.get_mode(session.id)
        action = self._decomposer.parse_payload(text)

        # 1. Подрежим awaiting_step_text — юзер вводит свой шаг
        if mode == "awaiting_step_text" and action.action == "unknown":
            try:
                await self._decomposer.create_manual_step(
                    desire_id=desire.id, title=text,
                    deadline_type=self._current_deadline_type.get(desire.id, "first_step"),
                )
            except ValueError as e:
                return CoachResponse(
                    text=f"Не получилось: {e}",
                    state=SessionState.S_DECOMP,
                    buttons=self._decomposer.type_buttons(),
                )
            self._decomposer.set_mode(session.id, None)
            return await self._render_decomp_list(client, session, desire)

        # 2. Подрежим awaiting_step_edit:<id>
        if mode and mode.startswith("awaiting_step_edit:") and action.action == "unknown":
            try:
                step_id = int(mode.split(":", 1)[1])
            except (IndexError, ValueError):
                self._decomposer.set_mode(session.id, None)
            else:
                try:
                    await self._decomposer.edit_step(step_id, text)
                except ValueError as e:
                    return CoachResponse(
                        text=f"Не получилось: {e}",
                        state=SessionState.S_DECOMP,
                    )
                self._decomposer.set_mode(session.id, None)
                return await self._render_decomp_list(client, session, desire)

        # 3. Payload-actions
        if action.action == "type":
            # Выбор типа дедлайна → AI-черновик
            self._current_deadline_type[desire.id] = action.deadline_type  # type: ignore[assignment]
            tone = Tone(client.current_tone)
            step_ids = await self._decomposer.propose_steps(
                desire=desire,
                deadline_type=action.deadline_type,  # type: ignore[arg-type]
                tone=tone,
                intensity=client.tone_intensity,
            )
            if not step_ids:
                # AI не ответил — предложить ручной ввод
                self._decomposer.set_mode(session.id, "awaiting_step_text")
                return CoachResponse(
                    text=(
                        f"Горизонт: {days_for(action.deadline_type)} дней.\n\n"  # type: ignore[arg-type]
                        "AI не предложил шаги — введи первый вручную."
                    ),
                    state=SessionState.S_DECOMP,
                    buttons=[self._decomposer.add_own_button()],
                )
            return await self._render_decomp_list(client, session, desire)

        if action.action == "add_own":
            self._decomposer.set_mode(session.id, "awaiting_step_text")
            dt = self._current_deadline_type.get(desire.id, "first_step")
            return CoachResponse(
                text=(
                    f"Ок, введи текст своего шага. "
                    f"Горизонт: {days_for(dt)} дней."
                ),
                state=SessionState.S_DECOMP,
            )

        if action.action == "done":
            await self._decomposer.complete_step(action.step_id)  # type: ignore[arg-type]
            return await self._render_decomp_list(client, session, desire)

        if action.action == "skip":
            await self._decomposer.skip_step(action.step_id)  # type: ignore[arg-type]
            return await self._render_decomp_list(client, session, desire)

        if action.action == "undo_done":
            await self._decomposer.undo_done(action.step_id)  # type: ignore[arg-type]
            return await self._render_decomp_list(client, session, desire)

        if action.action == "undo_skip":
            await self._decomposer.undo_skip(action.step_id)  # type: ignore[arg-type]
            return await self._render_decomp_list(client, session, desire)

        if action.action == "edit":
            self._decomposer.set_mode(session.id, f"awaiting_step_edit:{action.step_id}")
            return CoachResponse(
                text=f"Введи новый текст для шага {action.step_id}.",
                state=SessionState.S_DECOMP,
            )

        if action.action == "new_desire":
            try:
                await self._fsm.transition(
                    session, SessionState.S_DESIRE_DECOMP, reason="new_desire"
                )
            except InvalidTransitionError:
                pass
            return CoachResponse(
                text="Какое новое желание разобрать?",
                state=SessionState.S_DESIRE_DECOMP,
            )

        if action.action == "resume":
            try:
                await self._fsm.transition(
                    session, SessionState.S_DIALOG, reason="user_paused"
                )
            except InvalidTransitionError:
                pass
            return CoachResponse(
                text="Ок, в диалоге. Если что — пиши.",
                state=SessionState.S_DIALOG,
            )

        if action.action == "cancel":
            try:
                await self._fsm.transition(session, SessionState.S_DIALOG, reason="user_cancel")
            except InvalidTransitionError:
                pass
            return CoachResponse(
                text="Ок, отменил декомпозицию. В диалоге.",
                state=SessionState.S_DIALOG,
            )

        # 4. Иначе — рендерим начальный экран (4 кнопки типа)
        self._decomposer.set_mode(session.id, None)
        return CoachResponse(
            text=(
                f"🎯 Желание «{desire.title}» — выбери горизонт:\n\n"
                "AI предложит 3-7 шагов. Или введи свои."
            ),
            state=SessionState.S_DECOMP,
            buttons=self._decomposer.type_buttons(),
        )

    async def _render_decomp_list(
        self, client: ClientRow, session: SessionRow, desire: DesireRow
    ) -> CoachResponse:
        """Отрисовка списка шагов с per-step кнопками + проверка all_done."""
        steps = await self._repo.list_steps(desire.id)
        if not steps:
            return CoachResponse(
                text="Шаги не созданы. Выбери горизонт или введи свой.",
                state=SessionState.S_DECOMP,
                buttons=self._decomposer.type_buttons(),
            )
        lines = [f"📋 Шаги для «{desire.title}»:"]
        all_buttons: list[dict] = []
        for i, s in enumerate(steps, 1):
            mark = "✓" if s.status == "done" else ("⏭" if s.status == "skipped" else "☐")
            lines.append(f"  {i}. {mark} {s.title}")
            # Только pending/done/skipped получают кнопки
            if s.status in ("pending", "done", "skipped"):
                all_buttons.extend(self._decomposer.step_buttons(s.id, s.status))
        # Кнопка «+ свой» всегда в конце
        all_buttons.append(self._decomposer.add_own_button())

        # Проверяем all_done
        if await self._decomposer.all_done(desire.id):
            try:
                await self._fsm.transition(
                    session, SessionState.S_ACHIEVE, reason="all_steps_done"
                )
            except InvalidTransitionError:
                pass
            return CoachResponse(
                text="\n".join(lines) + "\n\n🎉 Все шаги выполнены!",
                state=SessionState.S_ACHIEVE,
                buttons=self._decomposer.achieve_buttons(),
                finished=False,
            )

        return CoachResponse(
            text="\n".join(lines),
            state=SessionState.S_DECOMP,
            buttons=all_buttons,
        )

    # === Workbook: обработчики ===

    async def _handle_workbook_command(
        self, client: ClientRow, session: SessionRow, text: str
    ) -> CoachResponse:
        """`/workbook` или `/workbook <slug>` из S_DIALOG.

        `/workbook`:
        - если есть active run → продолжаем (resume)
        - иначе → показываем список книг (кнопки wb_start:<slug>)
        `/workbook <slug>`:
        - прямой старт выбранной книги
        """
        parts = text.strip().split(maxsplit=1)
        slug = parts[1].strip() if len(parts) > 1 else ""

        if not slug:
            # Сначала пробуем resume активного run (in_progress или paused)
            active = await self._repo.get_resumable_workbook_run(client.id)
            if active is not None:
                try:
                    workbook = self._workbook.load_book(active.book_slug)
                except FileNotFoundError as e:
                    log.warning("workbook.book_missing_on_resume", error=str(e))
                    return CoachResponse(
                        text=(
                            f"Не нашёл книгу «{active.book_slug}» на диске. "
                            "Попробуй /workbook заново."
                        ),
                        state=SessionState.S_DIALOG,
                    )
                step = self._workbook.current_step(active, workbook)
                try:
                    await self._fsm.transition(
                        session, SessionState.S_WORKBOOK, reason="wb_resume"
                    )
                except InvalidTransitionError:
                    pass
                return self._render_workbook_step(
                    workbook=workbook,
                    run=active,
                    step=step,
                    header=(
                        f"📖 Продолжаем «{workbook.title}». "
                        f"Шаг {step.index + 1}/{len(workbook.steps)}: {step.title}"
                    ),
                    state=SessionState.S_WORKBOOK,
                )
            # Нет активного — список книг
            return await self._render_workbook_list(client, session)

        # /workbook <slug> — прямой старт
        return await self._handle_workbook_start(client, session, slug)

    async def _render_workbook_list(
        self, client: ClientRow, session: SessionRow
    ) -> CoachResponse:
        books = self._workbook.list_books()
        if not books:
            return CoachResponse(
                text=(
                    "Воркбуков пока нет на диске. "
                    "Положите `workbook.md` в `workbooks_dir/<slug>/`."
                ),
                state=SessionState.S_DIALOG,
            )
        # Защита от in_progress без явного /workbook (юзер мог потерять кнопки)
        active = await self._repo.get_active_workbook_run(client.id)
        buttons: list[dict] = []
        if active is not None:
            buttons.append(
                {"label": "▶️ Продолжить", "payload": "/workbook", "kind": "wb_resume"}
            )
        for b in books:
            buttons.append(
                {
                    "label": f"📖 {b.title}",
                    "payload": f"/workbook {b.slug}",
                    "kind": "wb_start",
                }
            )
        return CoachResponse(
            text=(
                f"📚 Доступные воркбуки ({len(books)}):\n"
                "Выбери книгу — будем проходить шаг за шагом."
            ),
            state=SessionState.S_DIALOG,
            buttons=buttons,
        )

    async def _handle_workbook_start(
        self, client: ClientRow, session: SessionRow, slug: str
    ) -> CoachResponse:
        """Стартовать run для slug (или возобновить, если уже есть активный)."""
        try:
            run, step, workbook = await self._workbook.start_run(
                client, session, slug
            )
        except FileNotFoundError:
            return CoachResponse(
                text=f"Книга «{slug}» не найдена в воркбуках.",
                state=SessionState.S_DIALOG,
            )
        try:
            await self._fsm.transition(
                session, SessionState.S_WORKBOOK, reason="wb_start"
            )
        except InvalidTransitionError:
            pass
        return self._render_workbook_step(
            workbook=workbook,
            run=run,
            step=step,
            header=(
                f"📖 {workbook.title}. "
                f"Шаг {step.index + 1}/{len(workbook.steps)}: {step.title}"
            ),
            state=SessionState.S_WORKBOOK,
        )

    def _render_workbook_step(
        self,
        workbook: Workbook,
        run: WorkbookRunRow,
        step: WorkbookStep,
        header: str,
        reflection: str | None = None,
        state: SessionState | None = None,
    ) -> CoachResponse:
        body = step.body.strip()
        text_parts = []
        if reflection:
            text_parts.append(reflection)
        text_parts.append(header)
        if body:
            text_parts.append("")
            text_parts.append(body)
        text_parts.append("")
        text_parts.append("Напиши свой ответ — что думаешь, что чувствуешь. /cancel — прервать.")
        return CoachResponse(
            text="\n".join(text_parts),
            state=state if state is not None else SessionState.S_WORKBOOK,
            cost_usd=0.0,
        )

    async def _handle_workbook(
        self, client: ClientRow, session: SessionRow, text: str
    ) -> CoachResponse:
        """Главный диспетчер S_WORKBOOK: list / start / answer / cancel.

        - `wb_start:<slug>` или `/workbook <slug>` → старт
        - `wb_cancel` или `/cancel` → пауза
        - иначе → ответ на текущий шаг (AI-рефлексия)
        """
        payload = text.strip()
        # 1. /workbook без slug → список (юзер мог потерять кнопки)
        if payload.lower() in ("/workbook", "wb_list"):
            return await self._render_workbook_list(client, session)
        # 2. wb_start:<slug> или /workbook <slug>
        if payload.startswith("wb_start:") or payload.lower().startswith("/workbook "):
            slug_raw = payload.split(":", 1)[-1].split(" ", 1)[-1].strip()
            return await self._handle_workbook_start(client, session, slug_raw)
        # 3. wb_cancel / /cancel
        if payload.lower() in ("wb_cancel", "/cancel"):
            return await self._handle_workbook_cancel(client, session)

        # 4. Ответ клиента на текущий шаг
        return await self._handle_workbook_answer(client, session, payload)

    async def _handle_workbook_cancel(
        self, client: ClientRow, session: SessionRow
    ) -> CoachResponse:
        active = await self._repo.get_active_workbook_run(client.id)
        if active is not None:
            await self._repo.mark_workbook_run_completed(active.id, "paused")
        try:
            await self._fsm.transition(
                session, SessionState.S_DIALOG, reason="wb_cancel"
            )
        except InvalidTransitionError:
            pass
        return CoachResponse(
            text=(
                "Прогресс сохранён. /workbook — продолжить с того же шага."
            ),
            state=SessionState.S_DIALOG,
        )

    async def _handle_workbook_answer(
        self, client: ClientRow, session: SessionRow, text: str
    ) -> CoachResponse:
        active = await self._repo.get_active_workbook_run(client.id)
        if active is None:
            return CoachResponse(
                text="Нет активного воркбука. /workbook — выбрать.",
                state=SessionState.S_DIALOG,
            )
        try:
            workbook = self._workbook.load_book(active.book_slug)
        except FileNotFoundError:
            return CoachResponse(
                text=(
                    f"Книга «{active.book_slug}» исчезла с диска. "
                    "Останавливаю прогон."
                ),
                state=SessionState.S_DIALOG,
            )
        try:
            step = self._workbook.current_step(active, workbook)
        except IndexError:
            # run.step_index за границей — закрываем как completed
            await self._repo.mark_workbook_run_completed(active.id, "completed")
            try:
                await self._fsm.transition(
                    session, SessionState.S_DIALOG, reason="wb_completed"
                )
            except InvalidTransitionError:
                pass
            return CoachResponse(
                text=f"🎉 Воркбук «{workbook.title}» пройден.",
                state=SessionState.S_DIALOG,
            )

        answer = text.strip()
        # Защита от пустого / слишком короткого ответа — ДО AI
        if not answer or len(answer) < 3:
            return self._render_workbook_step(
                workbook=workbook,
                run=active,
                step=step,
                header=(
                    f"Шаг {step.index + 1}/{len(workbook.steps)}: "
                    f"{step.title} (пока без ответа)"
                ),
                state=SessionState.S_WORKBOOK,
            )

        # Сохраняем ответ и продвигаем step_index
        next_idx = step.index + 1
        await self._repo.append_workbook_answer(active.id, next_idx, answer)

        # AI-рефлексия (тон клиента)
        tone = Tone(client.current_tone)
        try:
            reflection, cost = await self._workbook.reflect(
                tone=tone,
                intensity=client.tone_intensity,
                book_title=workbook.title,
                step=step,
                answer=answer,
            )
        except Exception:  # noqa: BLE001
            log.exception("workbook.reflect_unexpected")
            reflection, cost = (
                f"Принято: «{answer[:120]}».",
                0.0,
            )

        # Последний шаг — закрываем
        if next_idx >= len(workbook.steps):
            await self._repo.mark_workbook_run_completed(active.id, "completed")
            try:
                await self._fsm.transition(
                    session, SessionState.S_DIALOG, reason="wb_completed"
                )
            except InvalidTransitionError:
                pass
            return CoachResponse(
                text=(
                    f"{reflection}\n\n"
                    f"🎉 Воркбук «{workbook.title}» пройден. "
                    f"{len(workbook.steps)}/{len(workbook.steps)} шагов. "
                    "Что дальше — поговорим?"
                ),
                state=SessionState.S_DIALOG,
                cost_usd=cost,
            )

        # Не последний — рендерим следующий шаг
        next_step = workbook.steps[next_idx]
        return self._render_workbook_step(
            workbook=workbook,
            run=active,
            step=next_step,
            header=(
                f"Шаг {next_step.index + 1}/{len(workbook.steps)}: "
                f"{next_step.title}"
            ),
            reflection=reflection,
            state=SessionState.S_WORKBOOK,
        )

    async def _handle_achieve(
        self, client: ClientRow, session: SessionRow, text: str
    ) -> CoachResponse:
        """S_ACHIEVE — поздравление, кнопки new_desire / в диалог."""
        # Если payload — обработать
        action = self._decomposer.parse_payload(text)
        if action.action == "new_desire":
            try:
                await self._fsm.transition(
                    session, SessionState.S_DESIRE_DECOMP, reason="new_desire"
                )
            except InvalidTransitionError:
                pass
            return CoachResponse(
                text="🎯 Какое новое желание разобрать?",
                state=SessionState.S_DESIRE_DECOMP,
            )
        if action.action == "resume" or action.action == "cancel":
            try:
                await self._fsm.transition(
                    session, SessionState.S_DIALOG, reason="user_paused"
                )
            except InvalidTransitionError:
                pass
            return CoachResponse(
                text="Ок, в диалоге.",
                state=SessionState.S_DIALOG,
            )

        return CoachResponse(
            text=(
                "🎉 Поздравляю! Желание разобрано и шаги выполнены.\n\n"
                "Что дальше?"
            ),
            state=SessionState.S_ACHIEVE,
            buttons=self._decomposer.achieve_buttons(),
        )

    async def _handle_release(self, client: ClientRow, session: SessionRow) -> CoachResponse:
        """S_RELEASE → пометить активный desire как released + вернуться в диалог.

        Если активный desire не найден — graceful fallback в S_DIALOG.
        """
        desire_id = self._active_desire.get(session.id)
        if desire_id is not None:
            try:
                await self._repo.update_desire_status(desire_id, "released")
                log.info(
                    "session.desire_released",
                    client_id=client.id,
                    session_id=session.id,
                    desire_id=desire_id,
                )
                self._active_desire.pop(session.id, None)
            except Exception:
                log.exception(
                    "session.release_desire_failed",
                    desire_id=desire_id,
                    session_id=session.id,
                )
        try:
            await self._fsm.transition(session, SessionState.S_DIALOG, reason="released")
        except InvalidTransitionError:
            pass
        return CoachResponse(
            text="🍃 Желание отпущено. Без вины. Возвращаюсь в обычный диалог.",
            state=SessionState.S_DIALOG,
        )

    # === AI call ===

    async def _call_ai(
        self,
        client: ClientRow,
        session: SessionRow,
        text: str,
        channel: str,
        mode: str,
    ) -> CoachResponse:
        # === Phase 8: cost budget check ===
        if self._is_budget_exceeded(session.id):
            log.warning(
                "session.cost_budget_exceeded",
                session_id=session.id,
                cost_so_far=round(self._session_cost.get(session.id, 0.0), 4),
                budget=self._session_cost_budget,
            )
            return CoachResponse(
                text=(
                    "⏸ AI-бюджет этой сессии исчерпан "
                    f"(>${self._session_cost_budget:.2f}). "
                    "Продолжи завтра — или смени тему через /tone."
                ),
                state=SessionState(session.current_state) if session.current_state else None,
                finished=False,
            )

        try:
            ai = self._ai or get_ai_client(prefer="claude")
        except AIUnconfiguredError:
            log.exception("session.ai_unconfigured")
            return CoachResponse(
                text=(
                    "Коуч сейчас не сконфигурирован. "
                    "Заполните ANTHROPIC_API_KEY или YANDEXGPT_API_KEY в .env. "
                    "Или установите AI_FAKE_MODE=true для dev."
                ),
                state=SessionState(session.current_state) if session.current_state else None,
            )

        # Собираем контекст
        recent = await self._repo.get_recent_messages(session.id, limit=10)
        recent_texts = [f"[{m.role}] {m.content}" for m in recent[-5:]]
        desires = await self._repo.get_active_desires(client.id)
        active_title = desires[0].title if desires else None
        tone = Tone(client.current_tone)
        ctx = ContextBlock(
            active_desire_title=active_title,
            recent_messages=recent_texts,
            channel=channel,
            is_onboarding=client.onboarding_state == "new",
            mode_hint=mode,
        )
        system = build_system_prompt(tone, client.tone_intensity, ctx)
        messages: list[dict] = []
        for m in recent[-10:]:
            messages.append({"role": m.role, "content": m.content})
        messages.append({"role": "user", "content": text})

        try:
            from agent.ai.claude_client import estimate_cost
            resp = await ai.complete(
                system=system,
                messages=messages,
                tools=TOOL_SCHEMAS if ai.supports_tools() else None,
                max_tokens=600,
            )
        except AIError:
            log.exception("session.ai_error")
            # PRD 7.4.1: 5xx → S_IDLE_SAVED с friendly message
            try:
                await self._fsm.transition(session, SessionState.S_IDLE_SAVED, reason="error_recoverable")
                await self._repo.end_session(session.id, "error_recoverable")
            except InvalidTransitionError:
                pass
            return CoachResponse(
                text=(
                    "Извини, у меня техническая пауза. "
                    "Попробуй через минуту, или я сохраню наш разговор — "
                    "ты сможешь продолжить."
                ),
                state=SessionState.S_IDLE_SAVED,
                finished=True,
            )

        from agent.ai.claude_client import estimate_cost
        cost = estimate_cost(resp.model or "claude-sonnet-4-5", resp.input_tokens, resp.output_tokens)
        # Phase 8: накопить в budget-аккумулятор
        self._session_cost[session.id] = (
            self._session_cost.get(session.id, 0.0) + cost
        )

        # Tool dispatch: AI мог предложить add_step / mark_step_done через tool_use
        tool_acks: list[str] = []
        for tc in resp.tool_calls:
            try:
                result = await self._tools.dispatch(tc.name, tc.input)
                if result.get("status") == "ok":
                    if tc.name == "add_step" and "step_id" in result:
                        tool_acks.append(f"+ шаг #{result['step_id']}")
                    elif tc.name == "mark_step_done":
                        tool_acks.append("✓ шаг сделан")
            except Exception:  # noqa: BLE001
                # Phase 8: log.exception сохраняет stacktrace; tool_acks даёт
                # пользователю видимую пометку (без silent failure)
                log.exception("session.tool_dispatch_error", tool=tc.name)
                tool_acks.append(f"⚠️ ошибка tool: {tc.name}")

        text_out = resp.text or "..."
        if tool_acks:
            text_out = (text_out + "\n\n" if resp.text else "") + " ".join(tool_acks)

        return CoachResponse(
            text=text_out,
            state=SessionState(session.current_state) if session.current_state else None,
            cost_usd=cost,
        )

    # === End session ===

    async def end_session(
        self, client: ClientRow, mode: str  # 'save' | 'complete'
    ) -> SessionRow:
        """Завершить сессию: 'save' → user_paused, 'complete' → completed."""
        session = await self._repo.get_active_session(client.id)
        if session is None:
            session = await self._repo.get_last_session(client.id)
        if session is None:
            raise RuntimeError("end_session: no session for client")
        reason = "user_paused" if mode == "save" else "completed"
        # Генерим summary если 'complete' и есть AI
        summary: str | None = None
        if mode == "complete":
            try:
                ai = self._ai or get_ai_client(prefer="yandex")
                recent = await self._repo.get_recent_messages(session.id, limit=20)
                msgs = [{"role": m.role, "content": m.content} for m in recent[-10:]]
                resp = await ai.complete(
                    system="Сделай краткое summary (3-5 предложений) диалога клиента с коучем. На русском.",
                    messages=msgs,
                    max_tokens=300,
                )
                summary = resp.text
            except (AIError, AIUnconfiguredError):
                # Fallback шаблон
                cnt = await self._repo.count_messages(session.id)
                summary = f"Сессия от {session.started_at[:10]}, обработано {cnt} сообщений."
        updated = await self._repo.end_session(session.id, reason=reason, summary=summary)
        # disarm idle
        self._idle.disarm(session.id)
        log.info("session.ended", session_id=session.id, reason=reason, has_summary=bool(summary))
        return updated or session

    # === Onboarding entry (вызывается из API) ===

    async def start_onboarding(self, client: ClientRow) -> CoachResponse:
        session, _ = await self.get_or_create_session(client)
        await self._fsm.transition(session, SessionState.S_ONBOARD, reason="onboarding")
        result = await self._onboarding.start(client, session)
        return CoachResponse(
            text=result.text,
            buttons=[b.__dict__ for b in result.buttons],
            state=result.state,
        )

    # === Change tone (для /tone) ===

    async def change_tone(
        self, client: ClientRow, tone: Tone, intensity: int
    ) -> ClientRow:
        return (await self._repo.update_client_tone(client.id, tone.value, intensity)) or client

    # === Idle handler ===

    async def _on_idle(self, session_id: int) -> None:
        session = await self._repo.get_session_by_id(session_id)
        if session is None or session.ended_at is not None:
            return
        try:
            await self._fsm.transition_to_idle(session)
            await self._repo.end_session(session_id, "idle_15min")
            log.info("session.idle_saved", session_id=session_id)
        except InvalidTransitionError:
            pass


__all__ = ["SessionService", "CoachResponse"]
