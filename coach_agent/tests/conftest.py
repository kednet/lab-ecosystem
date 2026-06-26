"""
Общие фикстуры для тестов Phase 1.

Использует:
- FakeRepository (in-memory реализация)
- FakeAIClient — управляемый AI с очередью ответов
- Реальные FSM/Detector/Crisis — не мокаются (это и есть тестируемая логика)
- FastAPI TestClient с overridden deps (app.state)
"""

from __future__ import annotations

from pathlib import Path

import pytest
from factories import make_client
from fastapi.testclient import TestClient

from agent.ai.factory import reset_clients
from agent.ai.fake_client import FakeAIClient
from agent.api.middleware.ratelimit import RateLimitMiddleware
from agent.core.detector import DetectorService
from agent.core.idle import IdleTimer
from agent.core.message_bus import MessageBus
from agent.core.onboarding import OnboardingService
from agent.core.session import SessionService
from agent.core.state_machine import SessionStateMachine
from agent.storage.models import (
    ClientChannelRow,
    ClientRow,
    CrisisLogRow,
    DesireRow,
    DesireStepRow,
    MessageRow,
    SessionRow,
    WorkbookRunRow,
)


@pytest.fixture(autouse=True)
def _reset_rate_limiter():
    """Autouse: сбрасывает in-memory state RateLimitMiddleware между тестами.

    Phase 8: иначе тесты в одном процессе накапливают счётчик и падают на 429.
    middleware_stack создаётся лениво при первом запросе → инициализируем
    через TestClient, затем чистим _hits у найденного RateLimitMiddleware.
    """
    from fastapi.testclient import TestClient

    from agent.api.middleware.ratelimit import RateLimitMiddleware  # noqa: F401
    from agent.main import app

    # Принудительно инициализируем middleware_stack (один раз на сессию)
    if not hasattr(app, "_mw_stack_initialized"):
        TestClient(app).get("/health/ai")
        app._mw_stack_initialized = True

    # Чистим _hits на RateLimitMiddleware в стэке
    _clear_rl_hits(app.middleware_stack)
    yield
    _clear_rl_hits(app.middleware_stack)


def _clear_rl_hits(middleware) -> None:
    """Рекурсивно очищает _hits во всех RateLimitMiddleware в стэке."""
    if isinstance(middleware, RateLimitMiddleware):
        middleware._hits.clear()
        return
    inner = getattr(middleware, "app", None)
    if inner is not None:
        _clear_rl_hits(inner)

# === Дефолтные моки ===

DEFAULT_CLIENT = make_client(id=1, onboarding_state="new")


# === Repository mock ===

class FakeRepository:
    """In-memory fake repository для тестов (замена AsyncMock)."""

    def __init__(self) -> None:
        self._clients: dict[int, ClientRow] = {}
        self._sessions: dict[int, SessionRow] = {}
        self._messages: list[MessageRow] = []
        self._desires: dict[int, DesireRow] = {}
        self._steps: dict[int, DesireStepRow] = {}
        self._crisis: list[CrisisLogRow] = []
        self._workbook_runs: dict[int, WorkbookRunRow] = {}
        self._client_channels: list[ClientChannelRow] = []
        self._next_id = {
            "client": 1,
            "session": 1,
            "message": 1,
            "desire": 1,
            "step": 1,
            "crisis": 1,
            "workbook_run": 1,
        }
        self.calls: list[tuple[str, dict]] = []  # (method, kwargs) для проверок

    def _next(self, kind: str) -> int:
        v = self._next_id[kind]
        self._next_id[kind] = v + 1
        return v

    def reset(self) -> None:
        self._clients.clear()
        self._sessions.clear()
        self._messages.clear()
        self._desires.clear()
        self._steps.clear()
        self._crisis.clear()
        self._workbook_runs.clear()
        self._client_channels.clear()
        self._next_id = {
            "client": 1, "session": 1, "message": 1, "desire": 1, "step": 1, "crisis": 1,
            "workbook_run": 1,
        }
        self.calls.clear()

    # --- Client ---

    async def get_client_by_id(self, client_id: int) -> ClientRow | None:
        self.calls.append(("get_client_by_id", {"client_id": client_id}))
        return self._clients.get(client_id)

    async def get_client_by_email(self, email: str) -> ClientRow | None:
        self.calls.append(("get_client_by_email", {"email": email}))
        for c in self._clients.values():
            if c.email == email:
                return c
        return None

    async def upsert_client(
        self,
        email: str,
        name: str | None = None,
        current_tone: str = "warm",
        tone_intensity: int = 3,
    ) -> ClientRow:
        self.calls.append(("upsert_client", {"email": email}))
        for c in self._clients.values():
            if c.email == email:
                c.last_seen_at = "2026-06-10T00:00:00+00:00"
                c.current_tone = current_tone
                c.tone_intensity = tone_intensity
                return c
        cid = self._next("client")
        client = ClientRow(
            id=cid,
            email=email,
            name=name,
            current_tone=current_tone,
            tone_intensity=tone_intensity,
            timezone="Europe/Moscow",
            push_enabled=1,
            push_time="10:00",
            onboarding_state="new",
            created_at="2026-06-10T00:00:00+00:00",
            last_seen_at="2026-06-10T00:00:00+00:00",
            subscription_status="active",
        )
        self._clients[cid] = client
        return client

    async def update_client_tone(
        self, client_id: int, tone: str, intensity: int
    ) -> ClientRow | None:
        self.calls.append(("update_client_tone", {"client_id": client_id, "tone": tone, "intensity": intensity}))
        c = self._clients.get(client_id)
        if c:
            c.current_tone = tone
            c.tone_intensity = intensity
        return c

    async def update_client_onboarding(
        self, client_id: int, onboarding_state: str
    ) -> ClientRow | None:
        self.calls.append(("update_client_onboarding", {"client_id": client_id, "state": onboarding_state}))
        c = self._clients.get(client_id)
        if c:
            c.onboarding_state = onboarding_state
        return c

    async def touch_client(self, client_id: int) -> None:
        self.calls.append(("touch_client", {"client_id": client_id}))

    # --- Session ---

    async def create_session(
        self,
        client_id: int,
        tone: str,
        tone_intensity: int,
        mode: str = "dialog",
    ) -> SessionRow:
        sid = self._next("session")
        s = SessionRow(
            id=sid,
            client_id=client_id,
            started_at="2026-06-10T00:00:00+00:00",
            ended_at=None,
            ended_reason=None,
            current_state="S_DIALOG",
            tone=tone,
            tone_intensity=tone_intensity,
            mode=mode,
            summary=None,
            crisis_flag=0,
            total_cost_usd=0.0,
        )
        self._sessions[sid] = s
        self.calls.append(("create_session", {"client_id": client_id, "tone": tone}))
        return s

    async def get_active_session(self, client_id: int) -> SessionRow | None:
        for s in self._sessions.values():
            if s.client_id == client_id and s.ended_at is None:
                return s
        return None

    async def get_last_session(self, client_id: int) -> SessionRow | None:
        last = None
        for s in self._sessions.values():
            if s.client_id == client_id:
                if last is None or s.id > last.id:
                    last = s
        return last

    async def get_session_by_id(self, session_id: int) -> SessionRow | None:
        return self._sessions.get(session_id)

    async def update_session_state(
        self,
        session_id: int,
        state: str,
        total_cost_usd_delta: float = 0.0,
    ) -> SessionRow | None:
        s = self._sessions.get(session_id)
        if s:
            s.current_state = state
            s.total_cost_usd = (s.total_cost_usd or 0) + total_cost_usd_delta
        self.calls.append(("update_session_state", {"session_id": session_id, "state": state, "delta": total_cost_usd_delta}))
        return s

    async def end_session(
        self,
        session_id: int,
        reason: str,
        summary: str | None = None,
    ) -> SessionRow | None:
        s = self._sessions.get(session_id)
        if s:
            s.ended_at = "2026-06-10T01:00:00+00:00"
            s.ended_reason = reason
            if summary:
                s.summary = summary
        self.calls.append(("end_session", {"session_id": session_id, "reason": reason}))
        return s

    # --- Message ---

    async def append_message(
        self,
        session_id: int,
        role: str,
        content: str,
        is_crisis: bool = False,
        excluded_from_training: bool = False,
    ) -> MessageRow:
        mid = self._next("message")
        m = MessageRow(
            id=mid,
            session_id=session_id,
            role=role,
            content=content,
            ts="2026-06-10T00:00:00+00:00",
            is_crisis_message=1 if is_crisis else 0,
            excluded_from_training=1 if excluded_from_training else 0,
        )
        self._messages.append(m)
        return m

    async def get_recent_messages(
        self, session_id: int, limit: int = 20
    ) -> list[MessageRow]:
        return [m for m in self._messages if m.session_id == session_id][-limit:]

    async def count_messages(self, session_id: int) -> int:
        return sum(1 for m in self._messages if m.session_id == session_id)

    # --- Desire ---

    async def create_desire(
        self,
        client_id: int,
        title: str,
        kind: str | None = None,
        score: float | None = None,
        verdict_label: str | None = None,
        module_scores: dict | None = None,
        detector_depth: str | None = None,
        reasoning: str | None = None,
    ) -> DesireRow:
        did = self._next("desire")
        d = DesireRow(
            id=did,
            client_id=client_id,
            title=title,
            kind=kind,
            score=score,
            verdict_label=verdict_label,
            module_scores=str(module_scores) if module_scores else None,
            detector_depth=detector_depth,
            reasoning=reasoning,
            status="active",
            parent_desire_id=None,
            created_at="2026-06-10T00:00:00+00:00",
            updated_at="2026-06-10T00:00:00+00:00",
        )
        self._desires[did] = d
        self.calls.append(("create_desire", {"client_id": client_id, "title": title}))
        return d

    async def update_desire_verdict(
        self,
        desire_id: int,
        kind: str,
        score: float,
        verdict_label: str,
        module_scores: dict,
        detector_depth: str,
        reasoning: str,
    ) -> DesireRow | None:
        d = self._desires.get(desire_id)
        if d:
            d.kind = kind
            d.score = score
            d.verdict_label = verdict_label
            d.module_scores = str(module_scores)
            d.detector_depth = detector_depth
            d.reasoning = reasoning
        self.calls.append(("update_desire_verdict", {"desire_id": desire_id, "verdict": verdict_label}))
        return d

    async def update_desire_status(
        self, desire_id: int, status: str
    ) -> DesireRow | None:
        d = self._desires.get(desire_id)
        if d:
            d.status = status
        return d

    async def get_active_desires(self, client_id: int) -> list[DesireRow]:
        return [d for d in self._desires.values() if d.client_id == client_id and d.status == "active"]

    async def get_desire_by_id(self, desire_id: int) -> DesireRow | None:
        return self._desires.get(desire_id)

    async def create_desire_step(
        self, desire_id: int, title: str, deadline: str | None = None, deadline_type: str | None = None
    ):
        from agent.storage.models import DesireStepRow
        sid = self._next("step")
        step = DesireStepRow(
            id=sid, desire_id=desire_id, title=title, deadline=deadline, deadline_type=deadline_type,
            status="pending", done_at=None,
            created_at="2026-06-10T00:00:00+00:00",
            updated_at="2026-06-10T00:00:00+00:00",
        )
        self._steps[sid] = step
        return step

    async def list_steps(self, desire_id: int, status: str | None = None) -> list[DesireStepRow]:
        steps = [s for s in self._steps.values() if s.desire_id == desire_id]
        if status is not None:
            steps = [s for s in steps if s.status == status]
        return sorted(steps, key=lambda s: s.id)

    async def get_step_by_id(self, step_id: int) -> DesireStepRow | None:
        return self._steps.get(step_id)

    async def mark_step_done(self, step_id: int) -> DesireStepRow | None:
        step = self._steps.get(step_id)
        if step is None:
            return None
        from agent.storage.models import DesireStepRow
        updated = DesireStepRow(
            id=step.id, desire_id=step.desire_id, title=step.title,
            deadline=step.deadline, deadline_type=step.deadline_type,
            status="done", done_at="2026-06-10T00:01:00+00:00",
            created_at=step.created_at, updated_at="2026-06-10T00:01:00+00:00",
        )
        self._steps[step_id] = updated
        return updated

    async def mark_step_skipped(self, step_id: int) -> DesireStepRow | None:
        step = self._steps.get(step_id)
        if step is None:
            return None
        from agent.storage.models import DesireStepRow
        updated = DesireStepRow(
            id=step.id, desire_id=step.desire_id, title=step.title,
            deadline=step.deadline, deadline_type=step.deadline_type,
            status="skipped", done_at=None,
            created_at=step.created_at, updated_at="2026-06-10T00:01:00+00:00",
        )
        self._steps[step_id] = updated
        return updated

    async def update_step(
        self, step_id: int, title: str | None = None,
        deadline: str | None = None, deadline_type: str | None = None,
    ) -> DesireStepRow | None:
        step = self._steps.get(step_id)
        if step is None:
            return None
        from agent.storage.models import DesireStepRow
        updated = DesireStepRow(
            id=step.id, desire_id=step.desire_id,
            title=title if title is not None else step.title,
            deadline=deadline if deadline is not None else step.deadline,
            deadline_type=deadline_type if deadline_type is not None else step.deadline_type,
            status=step.status, done_at=step.done_at,
            created_at=step.created_at, updated_at="2026-06-10T00:02:00+00:00",
        )
        self._steps[step_id] = updated
        return updated

    async def delete_step(self, step_id: int) -> bool:
        return self._steps.pop(step_id, None) is not None

    async def count_steps_by_status(self, desire_id: int, status: str) -> int:
        return sum(
            1 for s in self._steps.values()
            if s.desire_id == desire_id and s.status == status
        )

    async def set_step_status(
        self, step_id: int, status: str, done_at: str | None = None
    ) -> DesireStepRow | None:
        step = self._steps.get(step_id)
        if step is None:
            return None
        from agent.storage.models import DesireStepRow
        updated = DesireStepRow(
            id=step.id, desire_id=step.desire_id, title=step.title,
            deadline=step.deadline, deadline_type=step.deadline_type,
            status=status, done_at=done_at,
            created_at=step.created_at, updated_at="2026-06-10T00:03:00+00:00",
        )
        self._steps[step_id] = updated
        return updated

    # --- Crisis ---

    async def log_crisis(
        self,
        client_id: int,
        session_id: int,
        channel: str,
        message_hash: str,
        matched_pattern: str,
    ) -> CrisisLogRow:
        cid = self._next("crisis")
        c = CrisisLogRow(
            id=cid,
            client_id=client_id,
            session_id=session_id,
            channel=channel,
            message_hash=message_hash,
            matched_pattern=matched_pattern,
            created_at="2026-06-10T00:00:00+00:00",
            followed_up_at=None,
        )
        self._crisis.append(c)
        return c

    # --- Crisis follow-up (Phase 8) ---

    async def mark_session_crisis(self, session_id: int) -> None:
        s = self._sessions.get(session_id)
        if s:
            s.crisis_flag = 1

    async def list_old_unfollowed_crisis(
        self, before_iso: str, limit: int = 50
    ) -> list[CrisisLogRow]:
        out: list[CrisisLogRow] = []
        for c in self._crisis:
            if c.followed_up_at is not None:
                continue
            if c.created_at < before_iso:
                out.append(c)
            if len(out) >= limit:
                break
        return out

    async def mark_crisis_followed_up(self, log_id: int) -> None:
        from agent.storage.models import CrisisLogRow

        for i, c in enumerate(self._crisis):
            if c.id == log_id:
                self._crisis[i] = CrisisLogRow(
                    id=c.id,
                    client_id=c.client_id,
                    session_id=c.session_id,
                    channel=c.channel,
                    message_hash=c.message_hash,
                    matched_pattern=c.matched_pattern,
                    created_at=c.created_at,
                    followed_up_at="2026-06-10T01:00:00+00:00",
                )
                return

    # --- WorkbookRun ---

    async def create_workbook_run(
        self,
        client_id: int,
        book_slug: str,
        session_id: int | None,
        step_index: int = 0,
    ) -> WorkbookRunRow:
        wid = self._next("workbook_run")
        run = WorkbookRunRow(
            id=wid,
            client_id=client_id,
            book_slug=book_slug,
            session_id=session_id,
            step_index=step_index,
            answer=None,
            status="in_progress",
            created_at="2026-06-10T00:00:00+00:00",
        )
        self._workbook_runs[wid] = run
        self.calls.append(("create_workbook_run", {"client_id": client_id, "book_slug": book_slug}))
        return run

    async def get_active_workbook_run(
        self, client_id: int
    ) -> WorkbookRunRow | None:
        runs = [
            r for r in self._workbook_runs.values()
            if r.client_id == client_id and r.status == "in_progress"
        ]
        if not runs:
            return None
        return max(runs, key=lambda r: r.id)

    async def get_workbook_run_by_id(
        self, run_id: int
    ) -> WorkbookRunRow | None:
        return self._workbook_runs.get(run_id)

    async def append_workbook_answer(
        self,
        run_id: int,
        step_index: int,
        answer: str | None,
    ) -> WorkbookRunRow | None:
        run = self._workbook_runs.get(run_id)
        if run is None:
            return None
        run.step_index = step_index
        if answer is not None:
            run.answer = answer
        return run

    async def mark_workbook_run_completed(
        self,
        run_id: int,
        status: str = "completed",
    ) -> WorkbookRunRow | None:
        if status not in ("completed", "paused"):
            raise ValueError(f"Недопустимый workbook_run status: {status!r}")
        run = self._workbook_runs.get(run_id)
        if run is None:
            return None
        run.status = status
        return run

    async def get_resumable_workbook_run(
        self, client_id: int
    ) -> WorkbookRunRow | None:
        runs = [
            r for r in self._workbook_runs.values()
            if r.client_id == client_id and r.status in ("in_progress", "paused")
        ]
        if not runs:
            return None
        return max(runs, key=lambda r: r.id)

    async def reactivate_paused_run(
        self, run_id: int
    ) -> WorkbookRunRow | None:
        run = self._workbook_runs.get(run_id)
        if run is None or run.status != "paused":
            return run
        run.status = "in_progress"
        return run

    # --- ClientChannel (Phase 7) ---

    async def find_client_by_channel(
        self, channel: str, external_id: str
    ) -> ClientRow | None:
        self.calls.append(
            ("find_client_by_channel", {"channel": channel, "external_id": external_id})
        )
        for cc in self._client_channels:
            if cc.channel == channel and cc.external_id == external_id:
                return self._clients.get(cc.client_id)
        return None

    async def upsert_client_channel(
        self,
        client_id: int,
        channel: str,
        external_id: str,
    ) -> ClientChannelRow:
        self.calls.append(
            ("upsert_client_channel", {"client_id": client_id, "channel": channel, "external_id": external_id})
        )
        for cc in self._client_channels:
            if cc.client_id == client_id and cc.channel == channel:
                cc.external_id = external_id
                cc.last_seen_at = "2026-06-10T00:00:00+00:00"
                cc.verified_at = "2026-06-10T00:00:00+00:00"
                return cc
        # Создаём новую
        cc = ClientChannelRow(
            client_id=client_id,
            channel=channel,
            external_id=external_id,
            verified_at="2026-06-10T00:00:00+00:00",
            last_seen_at="2026-06-10T00:00:00+00:00",
        )
        self._client_channels.append(cc)
        return cc

    async def list_client_channels(
        self, client_id: int
    ) -> list[ClientChannelRow]:
        return [cc for cc in self._client_channels if cc.client_id == client_id]


# === Фикстуры ===

@pytest.fixture
def fake_repo() -> FakeRepository:
    repo = FakeRepository()
    return repo


@pytest.fixture
def fake_ai() -> FakeAIClient:
    reset_clients()
    return FakeAIClient()


@pytest.fixture
def state_machine(fake_repo: FakeRepository) -> SessionStateMachine:
    return SessionStateMachine(fake_repo)


@pytest.fixture
def onboarding(fake_repo: FakeRepository, state_machine: SessionStateMachine) -> OnboardingService:
    return OnboardingService(fake_repo, state_machine)


@pytest.fixture
def onboarding_with_workbook(fake_repo: FakeRepository, state_machine: SessionStateMachine) -> OnboardingService:
    from agent.core.workbook import WorkbookService
    wb = WorkbookService(fake_repo, None)
    return OnboardingService(fake_repo, state_machine, wb)


@pytest.fixture
def detector() -> DetectorService:
    return DetectorService()


@pytest.fixture
def idle_timer() -> IdleTimer:
    return IdleTimer(timeout_sec=2)  # быстрый для тестов


@pytest.fixture
def session_service(
    fake_repo: FakeRepository,
    state_machine: SessionStateMachine,
    onboarding: OnboardingService,
    detector: DetectorService,
    idle_timer: IdleTimer,
    fake_ai: FakeAIClient,
) -> SessionService:
    return SessionService(
        repository=fake_repo,
        state_machine=state_machine,
        onboarding=onboarding,
        detector=detector,
        idle_timer=idle_timer,
        ai_client=fake_ai,
    )


@pytest.fixture
def message_bus(session_service: SessionService, fake_repo: FakeRepository) -> MessageBus:
    return MessageBus(session_service, fake_repo)


@pytest.fixture
def seeded_repo(fake_repo: FakeRepository):
    """Repo с заранее созданным client id=1, onboarding_state='new'."""
    fake_repo._clients[1] = DEFAULT_CLIENT
    return fake_repo


# === FastAPI app ===

@pytest.fixture
def app_with_fakes(
    fake_repo: FakeRepository,
    session_service: SessionService,
    message_bus: MessageBus,
    monkeypatch,
):
    """Подменяет deps на fake-версии через app.state."""
    from agent.main import app

    app.state.repository = fake_repo
    app.state.session_service = session_service
    app.state.message_bus = message_bus
    app.state.fsm = session_service._fsm
    app.state.idle = session_service._idle
    app.state.ai_client = session_service._ai
    return app


@pytest.fixture
def client(app_with_fakes) -> TestClient:
    return TestClient(app_with_fakes)


# === Workbook fixtures ===

@pytest.fixture
def temp_workbooks_dir(tmp_path, monkeypatch):
    """Подменяет settings.workbooks_dir на копию `tests/fixtures/workbooks`.

    Используется в тестах воркбуков: кладём туда 3 .md файла
    (atomic_habits / deep_work / mindset) и проверяем сервис.
    """
    import shutil

    from agent.config import settings as real_settings
    src = Path(__file__).parent / "fixtures" / "workbooks"
    dst = tmp_path / "workbooks"
    shutil.copytree(src, dst)
    monkeypatch.setattr(real_settings, "workbooks_dir", str(dst))
    return dst
