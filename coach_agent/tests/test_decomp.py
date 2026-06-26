"""
Тесты Phase 5: декомпозиция на шаги с дедлайнами.

Покрывает:
- decomp.py: константы, compute_deadline, parse_decomp_payload, кнопки
- repository: list/get/skip/update/delete/count для desire_step
- tool_dispatcher.add_step: реально создаёт шаг
- DecomposerService.propose_steps: AI tool_use → step_id[]
- DecomposerService.all_done: проверка завершения
- e2e через TestClient: detector → accept → type → steps → done×N → S_ACHIEVE
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from factories import make_client, make_desire
from fastapi.testclient import TestClient

from agent.ai.factory import ToolCall
from agent.ai.tools import ToolDispatcher
from agent.core.decomp import (
    ADD_OWN_BUTTON,
    DEADLINE_DAYS,
    DECOMP_TYPE_BUTTONS,
    DecompAction,
    compute_deadline,
    days_for,
    parse_decomp_payload,
    step_action_buttons,
)
from agent.core.decomposer import DecomposerService
from agent.core.tones import Tone
from agent.storage.models import ClientRow

HEADERS = {"X-Client-Id": "1"}


def _make_active_client(client_id: int = 1) -> ClientRow:
    return make_client(id=client_id, onboarding_state="tone_picked")


@pytest.fixture
def seeded_app(client: TestClient, fake_repo):
    fake_repo._clients[1] = _make_active_client(1)
    return client


# ============================================================
# decomp.py: константы, вычисления, парсер
# ============================================================

@pytest.mark.parametrize("deadline_type,days", [
    ("micro_test", 3),
    ("first_step", 7),
    ("trial", 14),
    ("mini_project", 30),
])
def test_deadline_days_mapping(deadline_type: str, days: int) -> None:
    assert days_for(deadline_type) == days
    assert DEADLINE_DAYS[deadline_type] == days


def test_days_for_unknown_raises() -> None:
    with pytest.raises(ValueError):
        days_for("invalid_type")


def test_compute_deadline_iso_format() -> None:
    base = datetime(2026, 6, 10, 12, 0, 0, tzinfo=UTC)
    result = compute_deadline("first_step", now=base)
    # ISO 8601 с timezone
    assert "T" in result
    parsed = datetime.fromisoformat(result)
    # +7 дней
    assert parsed == base + timedelta(days=7)


def test_compute_deadline_all_types() -> None:
    base = datetime(2026, 6, 10, tzinfo=UTC)
    for dtype, days in DEADLINE_DAYS.items():
        result = compute_deadline(dtype, now=base)
        parsed = datetime.fromisoformat(result)
        assert (parsed - base).days == days


def test_compute_deadline_unknown_raises() -> None:
    with pytest.raises(ValueError):
        compute_deadline("wrong_type")


@pytest.mark.parametrize("payload,expected", [
    ("decomp_type:micro_test", DecompAction("type", deadline_type="micro_test")),
    ("decomp_type:first_step", DecompAction("type", deadline_type="first_step")),
    ("step_done:5", DecompAction("done", step_id=5)),
    ("step_skip:3", DecompAction("skip", step_id=3)),
    ("step_edit:7", DecompAction("edit", step_id=7)),
    ("step_undo_done:2", DecompAction("undo_done", step_id=2)),
    ("step_undo_skip:9", DecompAction("undo_skip", step_id=9)),
    ("add_own", DecompAction("add_own")),
    ("new_desire", DecompAction("new_desire")),
    ("resume", DecompAction("resume")),
    ("cancel", DecompAction("cancel")),
])
def test_parse_decomp_payload_valid(payload: str, expected: DecompAction) -> None:
    result = parse_decomp_payload(payload)
    assert result == expected


def test_parse_decomp_payload_invalid() -> None:
    assert parse_decomp_payload("").action == "unknown"
    assert parse_decomp_payload("garbage").action == "unknown"
    assert parse_decomp_payload("step_done:abc").action == "unknown"
    assert parse_decomp_payload("decomp_type:invalid").action == "unknown"


def test_decomp_type_buttons_count() -> None:
    assert len(DECOMP_TYPE_BUTTONS) == 4
    payloads = {b["payload"] for b in DECOMP_TYPE_BUTTONS}
    assert "decomp_type:micro_test" in payloads
    assert "decomp_type:first_step" in payloads
    assert "decomp_type:trial" in payloads
    assert "decomp_type:mini_project" in payloads


def test_add_own_button_payload() -> None:
    assert ADD_OWN_BUTTON["payload"] == "add_own"
    assert "label" in ADD_OWN_BUTTON


def test_step_action_buttons_pending() -> None:
    btns = step_action_buttons(5, "pending")
    assert len(btns) == 3
    assert any("✓" in b["label"] for b in btns)
    assert any("edit" in b["payload"] for b in btns)
    assert any("skip" in b["payload"] for b in btns)


def test_step_action_buttons_done() -> None:
    btns = step_action_buttons(5, "done")
    assert len(btns) == 2
    assert any("undo" in b["payload"] for b in btns)


def test_step_action_buttons_skipped() -> None:
    btns = step_action_buttons(5, "skipped")
    assert len(btns) == 2
    assert any("undo_skip" in b["payload"] for b in btns)


# ============================================================
# Repository: list/get/skip/update/delete/count для desire_step
# ============================================================

@pytest.mark.asyncio
async def test_repository_create_and_list_steps(fake_repo) -> None:
    await fake_repo.create_desire_step(1, "Step 1", "2026-06-13", "micro_test")
    await fake_repo.create_desire_step(1, "Step 2", "2026-06-17", "first_step")
    await fake_repo.create_desire_step(2, "Other desire", None, None)
    all_steps = await fake_repo.list_steps(1)
    assert len(all_steps) == 2
    assert {s.title for s in all_steps} == {"Step 1", "Step 2"}


@pytest.mark.asyncio
async def test_repository_list_steps_with_status_filter(fake_repo) -> None:
    await fake_repo.create_desire_step(1, "P", None, "first_step")
    s2 = await fake_repo.create_desire_step(1, "D", None, "first_step")
    await fake_repo.mark_step_done(s2.id)
    pending = await fake_repo.list_steps(1, status="pending")
    done = await fake_repo.list_steps(1, status="done")
    assert len(pending) == 1 and pending[0].title == "P"
    assert len(done) == 1 and done[0].title == "D"


@pytest.mark.asyncio
async def test_repository_mark_step_skipped(fake_repo) -> None:
    s = await fake_repo.create_desire_step(1, "X", None, "first_step")
    result = await fake_repo.mark_step_skipped(s.id)
    assert result is not None
    assert result.status == "skipped"
    assert result.done_at is None
    # updated_at должен измениться
    assert result.updated_at != s.updated_at


@pytest.mark.asyncio
async def test_repository_update_step_partial(fake_repo) -> None:
    s = await fake_repo.create_desire_step(1, "Old", "2026-06-13", "micro_test")
    result = await fake_repo.update_step(s.id, title="New")
    assert result is not None
    assert result.title == "New"
    assert result.deadline == "2026-06-13"  # не тронули
    assert result.deadline_type == "micro_test"  # не тронули


@pytest.mark.asyncio
async def test_repository_delete_step(fake_repo) -> None:
    s = await fake_repo.create_desire_step(1, "X", None, "first_step")
    assert await fake_repo.delete_step(s.id) is True
    assert await fake_repo.get_step_by_id(s.id) is None


@pytest.mark.asyncio
async def test_repository_count_steps_by_status(fake_repo) -> None:
    await fake_repo.create_desire_step(1, "P1", None, "first_step")
    await fake_repo.create_desire_step(1, "P2", None, "first_step")
    s3 = await fake_repo.create_desire_step(1, "D1", None, "first_step")
    await fake_repo.mark_step_done(s3.id)
    assert await fake_repo.count_steps_by_status(1, "pending") == 2
    assert await fake_repo.count_steps_by_status(1, "done") == 1
    assert await fake_repo.count_steps_by_status(1, "skipped") == 0


@pytest.mark.asyncio
async def test_repository_set_step_status_pending(fake_repo) -> None:
    s = await fake_repo.create_desire_step(1, "X", None, "first_step")
    await fake_repo.mark_step_done(s.id)
    undone = await fake_repo.set_step_status(s.id, "pending", done_at=None)
    assert undone is not None
    assert undone.status == "pending"
    assert undone.done_at is None


# ============================================================
# ToolDispatcher: реальный add_step
# ============================================================

@pytest.mark.asyncio
async def test_tool_dispatcher_add_step_creates_row(fake_repo) -> None:
    dispatcher = ToolDispatcher(fake_repo)
    result = await dispatcher.dispatch("add_step", {
        "desire_id": 1,
        "title": "Купить молоко",
        "deadline_type": "micro_test",
    })
    assert result["status"] == "ok"
    assert "step_id" in result
    step = await fake_repo.get_step_by_id(result["step_id"])
    assert step is not None
    assert step.title == "Купить молоко"
    assert step.deadline_type == "micro_test"
    assert step.status == "pending"
    # deadline должен быть выставлен
    assert step.deadline is not None
    assert "T" in step.deadline


@pytest.mark.asyncio
async def test_tool_dispatcher_add_step_invalid_deadline_type(fake_repo) -> None:
    dispatcher = ToolDispatcher(fake_repo)
    result = await dispatcher.dispatch("add_step", {
        "desire_id": 1, "title": "X", "deadline_type": "wrong",
    })
    assert result["status"] == "error"


@pytest.mark.asyncio
async def test_tool_dispatcher_mark_step_done(fake_repo) -> None:
    dispatcher = ToolDispatcher(fake_repo)
    s = await fake_repo.create_desire_step(1, "X", None, "first_step")
    result = await dispatcher.dispatch("mark_step_done", {"step_id": s.id})
    assert result["status"] == "ok"
    assert result["step"]["status"] == "done"


@pytest.mark.asyncio
async def test_tool_dispatcher_save_desire_deferred(fake_repo) -> None:
    dispatcher = ToolDispatcher(fake_repo)
    result = await dispatcher.dispatch("save_desire", {"title": "X"})
    assert result["status"] == "deferred"


# ============================================================
# DecomposerService: propose_steps
# ============================================================

@pytest.mark.asyncio
async def test_decomposer_propose_steps_with_ai_tool_use(
    fake_repo, fake_ai
) -> None:
    """AI возвращает 3 tool_use add_step → 3 step_id."""
    dispatcher = ToolDispatcher(fake_repo)
    decomposer = DecomposerService(fake_repo, fake_ai, dispatcher)
    desire = make_desire(id=1, client_id=1, title="Купить MacBook")
    await fake_repo.create_desire(client_id=1, title="Купить MacBook")

    # AI возвращает 3 tool_use add_step
    fake_ai.set_responses([
        type("R", (), {
            "text": "",
            "tool_calls": [
                ToolCall(name="add_step", input={"desire_id": 1, "title": "Шаг 1", "deadline_type": "first_step"}),
                ToolCall(name="add_step", input={"desire_id": 1, "title": "Шаг 2", "deadline_type": "first_step"}),
                ToolCall(name="add_step", input={"desire_id": 1, "title": "Шаг 3", "deadline_type": "first_step"}),
            ],
            "input_tokens": 100, "output_tokens": 50,
            "model": "fake", "provider": "fake",
        })(),
    ])

    step_ids = await decomposer.propose_steps(desire, "first_step", Tone.WARM, 3)
    assert len(step_ids) == 3
    for sid in step_ids:
        step = await fake_repo.get_step_by_id(sid)
        assert step is not None
        assert step.deadline_type == "first_step"
        assert step.desire_id == 1


@pytest.mark.asyncio
async def test_decomposer_propose_steps_no_ai_returns_empty(fake_repo) -> None:
    """Без AI клиента — пустой список."""
    dispatcher = ToolDispatcher(fake_repo)
    decomposer = DecomposerService(fake_repo, None, dispatcher)
    desire = make_desire(id=1)
    step_ids = await decomposer.propose_steps(desire, "first_step", Tone.WARM, 3)
    assert step_ids == []


@pytest.mark.asyncio
async def test_decomposer_propose_steps_ai_fails_returns_empty(fake_repo) -> None:
    """AI выбрасывает исключение → пустой список, не raise."""
    from agent.ai.factory import AIClient, AIError

    class FailingAI(AIClient):
        @property
        def name(self) -> str: return "failing"
        def supports_tools(self) -> bool: return True
        async def complete(self, **kw):
            raise AIError("network down")

    dispatcher = ToolDispatcher(fake_repo)
    decomposer = DecomposerService(fake_repo, FailingAI(), dispatcher)
    desire = make_desire(id=1)
    step_ids = await decomposer.propose_steps(desire, "first_step", Tone.WARM, 3)
    assert step_ids == []


@pytest.mark.asyncio
async def test_decomposer_create_manual_step(fake_repo) -> None:
    dispatcher = ToolDispatcher(fake_repo)
    decomposer = DecomposerService(fake_repo, None, dispatcher)
    await fake_repo.create_desire(client_id=1, title="D")
    step = await decomposer.create_manual_step(1, "Свой шаг", "trial")
    assert step.title == "Свой шаг"
    assert step.deadline_type == "trial"
    assert step.deadline is not None


@pytest.mark.asyncio
async def test_decomposer_edit_step(fake_repo) -> None:
    dispatcher = ToolDispatcher(fake_repo)
    decomposer = DecomposerService(fake_repo, None, dispatcher)
    s = await fake_repo.create_desire_step(1, "Old", None, "first_step")
    updated = await decomposer.edit_step(s.id, "New text")
    assert updated is not None
    assert updated.title == "New text"


@pytest.mark.asyncio
async def test_decomposer_complete_step(fake_repo) -> None:
    dispatcher = ToolDispatcher(fake_repo)
    decomposer = DecomposerService(fake_repo, None, dispatcher)
    s = await fake_repo.create_desire_step(1, "X", None, "first_step")
    result = await decomposer.complete_step(s.id)
    assert result is not None
    assert result.status == "done"


@pytest.mark.asyncio
async def test_decomposer_skip_step(fake_repo) -> None:
    dispatcher = ToolDispatcher(fake_repo)
    decomposer = DecomposerService(fake_repo, None, dispatcher)
    s = await fake_repo.create_desire_step(1, "X", None, "first_step")
    result = await decomposer.skip_step(s.id)
    assert result is not None
    assert result.status == "skipped"


@pytest.mark.asyncio
async def test_decomposer_all_done_true_when_only_done_and_skipped(fake_repo) -> None:
    dispatcher = ToolDispatcher(fake_repo)
    decomposer = DecomposerService(fake_repo, None, dispatcher)
    s1 = await fake_repo.create_desire_step(1, "A", None, "first_step")
    s2 = await fake_repo.create_desire_step(1, "B", None, "first_step")
    await decomposer.complete_step(s1.id)
    await decomposer.skip_step(s2.id)
    assert await decomposer.all_done(1) is True


@pytest.mark.asyncio
async def test_decomposer_all_done_false_when_pending(fake_repo) -> None:
    dispatcher = ToolDispatcher(fake_repo)
    decomposer = DecomposerService(fake_repo, None, dispatcher)
    s1 = await fake_repo.create_desire_step(1, "A", None, "first_step")
    await fake_repo.create_desire_step(1, "B", None, "first_step")
    await decomposer.complete_step(s1.id)
    # второй шаг — pending
    assert await decomposer.all_done(1) is False


@pytest.mark.asyncio
async def test_decomposer_all_done_false_when_no_done(fake_repo) -> None:
    """Все pending + 1 skipped, но 0 done → not all_done."""
    dispatcher = ToolDispatcher(fake_repo)
    decomposer = DecomposerService(fake_repo, None, dispatcher)
    await fake_repo.create_desire_step(1, "A", None, "first_step")
    s2 = await fake_repo.create_desire_step(1, "B", None, "first_step")
    await decomposer.skip_step(s2.id)
    # A pending, B skipped, 0 done
    assert await decomposer.all_done(1) is False


# ============================================================
# E2E через TestClient
# ============================================================

def test_decomp_via_message_command(seeded_app, fake_repo, fake_ai) -> None:
    """POST /coach/message text='/decompose' → S_DECOMP + 4 кнопки."""
    fake_repo._desires[1] = make_desire(id=1, client_id=1, title="Купить MacBook")
    r = seeded_app.post(
        "/coach/message",
        json={"text": "/decompose"},
        headers=HEADERS,
    )
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["state"] == "S_DECOMP"
    assert "buttons" in data
    payloads = {b["payload"] for b in data["buttons"]}
    assert "decomp_type:micro_test" in payloads
    assert "decomp_type:first_step" in payloads
    assert "decomp_type:trial" in payloads
    assert "decomp_type:mini_project" in payloads
    assert "add_own" in payloads


def test_decomp_via_message_with_index(seeded_app, fake_repo, fake_ai) -> None:
    """POST /coach/message text='/decompose 1' → S_DECOMP."""
    fake_repo._desires[1] = make_desire(id=1, client_id=1, title="X")
    r = seeded_app.post(
        "/coach/message",
        json={"text": "/decompose 1"},
        headers=HEADERS,
    )
    assert r.status_code == 200, r.text
    assert r.json()["state"] == "S_DECOMP"


def test_decomp_choose_type_triggers_ai(seeded_app, fake_repo, fake_ai) -> None:
    """Выбор типа → AI tool_use add_step × 3 → список шагов."""
    fake_repo._desires[1] = make_desire(id=1, client_id=1, title="X")
    # Сначала входим в S_DECOMP
    seeded_app.post("/coach/message", json={"text": "/decompose"}, headers=HEADERS)
    # AI возвращает 3 tool_use
    fake_ai.set_responses([
        type("R", (), {
            "text": "Готово!",
            "tool_calls": [
                ToolCall(name="add_step", input={"desire_id": 1, "title": f"Шаг {i}", "deadline_type": "first_step"})
                for i in range(1, 4)
            ],
            "input_tokens": 100, "output_tokens": 50,
            "model": "fake", "provider": "fake",
        })(),
    ])
    r = seeded_app.post(
        "/coach/message",
        json={"text": "decomp_type:first_step"},
        headers=HEADERS,
    )
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["state"] == "S_DECOMP"
    # 3 шага созданы
    steps = [s for s in fake_repo._steps.values()]
    assert len(steps) == 3
    # Кнопки действий на каждый шаг
    payloads = {b["payload"] for b in data["buttons"]}
    assert "step_done:1" in payloads
    assert "step_done:2" in payloads
    assert "step_done:3" in payloads
    assert "add_own" in payloads


def test_decomp_done_step(seeded_app, fake_repo, fake_ai) -> None:
    """Отметка шага как done → status=done, остальные pending."""
    fake_repo._desires[1] = make_desire(id=1, client_id=1, title="X")
    seeded_app.post("/coach/message", json={"text": "/decompose"}, headers=HEADERS)
    fake_ai.set_responses([
        type("R", (), {
            "text": "",
            "tool_calls": [
                ToolCall(name="add_step", input={"desire_id": 1, "title": "S1", "deadline_type": "first_step"}),
                ToolCall(name="add_step", input={"desire_id": 1, "title": "S2", "deadline_type": "first_step"}),
            ],
            "input_tokens": 50, "output_tokens": 20,
            "model": "fake", "provider": "fake",
        })(),
    ])
    seeded_app.post("/coach/message", json={"text": "decomp_type:first_step"}, headers=HEADERS)
    r = seeded_app.post(
        "/coach/message",
        json={"text": "step_done:1"},
        headers=HEADERS,
    )
    assert r.status_code == 200
    s1 = fake_repo._steps[1]
    assert s1.status == "done"


def test_decomp_full_flow_to_achieve(seeded_app, fake_repo, fake_ai) -> None:
    """E2E: /decompose → type → done × 2 → S_ACHIEVE."""
    fake_repo._desires[1] = make_desire(id=1, client_id=1, title="E2E")
    seeded_app.post("/coach/message", json={"text": "/decompose"}, headers=HEADERS)
    fake_ai.set_responses([
        type("R", (), {
            "text": "",
            "tool_calls": [
                ToolCall(name="add_step", input={"desire_id": 1, "title": "S1", "deadline_type": "first_step"}),
                ToolCall(name="add_step", input={"desire_id": 1, "title": "S2", "deadline_type": "first_step"}),
            ],
            "input_tokens": 50, "output_tokens": 20,
            "model": "fake", "provider": "fake",
        })(),
    ])
    seeded_app.post("/coach/message", json={"text": "decomp_type:first_step"}, headers=HEADERS)
    seeded_app.post("/coach/message", json={"text": "step_done:1"}, headers=HEADERS)
    r2 = seeded_app.post("/coach/message", json={"text": "step_done:2"}, headers=HEADERS)
    assert r2.status_code == 200
    data = r2.json()
    assert data["state"] == "S_ACHIEVE"
    assert "🎉" in data["text"] or "Поздравляю" in data["text"]


def test_decomp_add_own_then_text(seeded_app, fake_repo, fake_ai) -> None:
    """Юзер жмёт + свой, вводит текст → шаг создан."""
    fake_repo._desires[1] = make_desire(id=1, client_id=1, title="X")
    seeded_app.post("/coach/message", json={"text": "/decompose"}, headers=HEADERS)
    # Жмём + свой
    r1 = seeded_app.post("/coach/message", json={"text": "add_own"}, headers=HEADERS)
    assert r1.status_code == 200
    assert "введи" in r1.json()["text"].lower() or "текст" in r1.json()["text"].lower()
    # Вводим текст
    r2 = seeded_app.post(
        "/coach/message",
        json={"text": "Записаться на курс"},
        headers=HEADERS,
    )
    assert r2.status_code == 200
    steps = list(fake_repo._steps.values())
    assert len(steps) == 1
    assert steps[0].title == "Записаться на курс"


def test_decomp_edit_step(seeded_app, fake_repo, fake_ai) -> None:
    """Юзер жмёт редактировать → вводит новый текст → обновление."""
    fake_repo._desires[1] = make_desire(id=1, client_id=1, title="X")
    seeded_app.post("/coach/message", json={"text": "/decompose"}, headers=HEADERS)
    fake_ai.set_responses([
        type("R", (), {
            "text": "",
            "tool_calls": [
                ToolCall(name="add_step", input={"desire_id": 1, "title": "Old", "deadline_type": "first_step"}),
            ],
            "input_tokens": 50, "output_tokens": 20,
            "model": "fake", "provider": "fake",
        })(),
    ])
    seeded_app.post("/coach/message", json={"text": "decomp_type:first_step"}, headers=HEADERS)
    r1 = seeded_app.post("/coach/message", json={"text": "step_edit:1"}, headers=HEADERS)
    assert r1.status_code == 200
    r2 = seeded_app.post("/coach/message", json={"text": "Brand new"}, headers=HEADERS)
    assert r2.status_code == 200
    assert fake_repo._steps[1].title == "Brand new"


def test_decomp_skip_step(seeded_app, fake_repo, fake_ai) -> None:
    """Юзер жмёт пропустить → status=skipped."""
    fake_repo._desires[1] = make_desire(id=1, client_id=1, title="X")
    seeded_app.post("/coach/message", json={"text": "/decompose"}, headers=HEADERS)
    fake_ai.set_responses([
        type("R", (), {
            "text": "",
            "tool_calls": [
                ToolCall(name="add_step", input={"desire_id": 1, "title": "S", "deadline_type": "first_step"}),
            ],
            "input_tokens": 50, "output_tokens": 20,
            "model": "fake", "provider": "fake",
        })(),
    ])
    seeded_app.post("/coach/message", json={"text": "decomp_type:first_step"}, headers=HEADERS)
    r = seeded_app.post("/coach/message", json={"text": "step_skip:1"}, headers=HEADERS)
    assert r.status_code == 200
    assert fake_repo._steps[1].status == "skipped"


def test_decomp_new_desire_from_achieve(seeded_app, fake_repo, fake_ai) -> None:
    """Из S_ACHIEVE нажатие new_desire → S_DESIRE_DECOMP."""
    fake_repo._desires[1] = make_desire(id=1, client_id=1, title="E2E")
    seeded_app.post("/coach/message", json={"text": "/decompose"}, headers=HEADERS)
    fake_ai.set_responses([
        type("R", (), {
            "text": "",
            "tool_calls": [
                ToolCall(name="add_step", input={"desire_id": 1, "title": "S1", "deadline_type": "first_step"}),
                ToolCall(name="add_step", input={"desire_id": 1, "title": "S2", "deadline_type": "first_step"}),
            ],
            "input_tokens": 50, "output_tokens": 20,
            "model": "fake", "provider": "fake",
        })(),
    ])
    seeded_app.post("/coach/message", json={"text": "decomp_type:first_step"}, headers=HEADERS)
    seeded_app.post("/coach/message", json={"text": "step_done:1"}, headers=HEADERS)
    seeded_app.post("/coach/message", json={"text": "step_done:2"}, headers=HEADERS)
    r = seeded_app.post("/coach/message", json={"text": "new_desire"}, headers=HEADERS)
    assert r.status_code == 200
    assert r.json()["state"] == "S_DESIRE_DECOMP"


def test_steps_command_lists_steps(seeded_app, fake_repo, fake_ai) -> None:
    """/steps — список шагов текущего desire."""
    fake_repo._desires[1] = make_desire(id=1, client_id=1, title="X")
    from agent.storage.models import DesireStepRow
    sid = fake_repo._next("step")
    fake_repo._steps[sid] = DesireStepRow(
        id=sid, desire_id=1, title="Шаг 1",
        deadline="2026-06-17", deadline_type="first_step",
        status="pending", done_at=None,
        created_at="2026-06-10T00:00:00+00:00",
        updated_at="2026-06-10T00:00:00+00:00",
    )
    r = seeded_app.post("/coach/message", json={"text": "/steps"}, headers=HEADERS)
    assert r.status_code == 200
    data = r.json()
    assert "Шаг 1" in data["text"]
