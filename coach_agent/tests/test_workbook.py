"""
Phase 4: Workbook — парсер, сервис, репозиторий, обработчики, e2e.

14+ кейсов:
- 6 парсер
- 4 сервис+репозиторий
- 4 обработчик (включая /workbook list/start, ответ, cancel, empty)
- 2 e2e (полный flow + resume)
"""

from __future__ import annotations

import pytest

# === Парсер ===

def test_parser_extracts_title():
    from agent.core.workbook_parser import parse_workbook
    text = """# ✍️ ВОРКБУК: Тестовая книга

Intro.

## 🔍 Упражнение 1. Шаг первый

- Вопрос?

## 💭 Рефлексия

Done.
"""
    wb = parse_workbook("test_book", text)
    assert wb.title == "Тестовая книга"
    assert wb.slug == "test_book"
    assert len(wb.steps) == 1


def test_parser_extracts_3_steps_with_correct_indices():
    from agent.core.workbook_parser import parse_workbook
    text = """# ✍️ ВОРКБУК: Book

## 🔍 Упражнение 1. A
1. Q

## ✍️ Упражнение 2. B
2. Q

## 🔍 Упражнение 3. C
3. Q
"""
    wb = parse_workbook("b", text)
    assert len(wb.steps) == 3
    assert [s.index for s in wb.steps] == [0, 1, 2]
    assert [s.title for s in wb.steps] == ["A", "B", "C"]


def test_parser_handles_emoji_in_headings():
    from agent.core.workbook_parser import parse_workbook
    text = """# ✍️ ВОРКБУК: Emoji

## 🌱 Упражнение 1. Один
1. Q

## 🎯 Упражнение 2. Два
2. Q
"""
    wb = parse_workbook("emoji", text)
    assert wb.title == "Emoji"
    assert len(wb.steps) == 2
    assert wb.steps[0].title == "Один"
    assert wb.steps[1].title == "Два"


def test_parser_detects_reflection_and_bonus():
    from agent.core.workbook_parser import parse_workbook
    text = """# ✍️ ВОРКБУК: Refl

## 🔍 Упражнение 1. Шаг
1. Q

## 💭 Рефлексия (через 30 дней)

Что изменится?

## 🎁 Бонус: ежедневные микро-привычки

2 минуты медитации.
"""
    wb = parse_workbook("r", text)
    assert wb.reflection is not None
    assert "Что изменится" in wb.reflection
    assert wb.bonus is not None
    assert "медитации" in wb.bonus


def test_parser_skips_bonus_in_steps():
    """`## 🎁 Бонус` НЕ должен попасть в steps."""
    from agent.core.workbook_parser import parse_workbook
    text = """# ✍️ ВОРКБУК: B

## 🔍 Упражнение 1. Шаг
1. Q

## 🎁 Бонус

Текст бонуса.
"""
    wb = parse_workbook("b", text)
    assert len(wb.steps) == 1
    assert all("Бонус" not in s.title for s in wb.steps)


def test_parser_detects_questions():
    from agent.core.workbook_parser import parse_workbook
    text_num = """# ✍️ ВОРКБУК: N

## 🔍 Упражнение 1. Шаг
1. Q
2. Q
"""
    text_check = """# ✍️ ВОРКБУК: C

## 🔍 Упражнение 1. Шаг
- [ ] one
- [ ] two
"""
    text_plain = """# ✍️ ВОРКБУК: P

## 🔍 Упражнение 1. Шаг
Текст без списков.
"""
    assert parse_workbook("n", text_num).steps[0].has_questions is True
    assert parse_workbook("c", text_check).steps[0].has_questions is True
    assert parse_workbook("p", text_plain).steps[0].has_questions is False


def test_parser_raises_without_title():
    from agent.core.workbook_parser import parse_workbook
    with pytest.raises(ValueError, match="заголовок"):
        parse_workbook("x", "## Упражнение 1. Step\n1. Q\n")


def test_parser_raises_without_steps():
    from agent.core.workbook_parser import parse_workbook
    text = "# ✍️ ВОРКБУК: Empty\n\nТекст без шагов.\n"
    with pytest.raises(ValueError, match="ни одного"):
        parse_workbook("e", text)


# === Сервис + Репозиторий ===

def test_workbook_service_lists_books_from_fixtures(
    temp_workbooks_dir, fake_repo, fake_ai
):
    from agent.core.workbook import WorkbookService
    ws = WorkbookService(fake_repo, fake_ai)
    books = ws.list_books()
    assert len(books) == 3
    slugs = {b.slug for b in books}
    assert slugs == {"atomic_habits", "deep_work", "mindset"}


def test_workbook_service_loads_book(temp_workbooks_dir, fake_repo, fake_ai):
    from agent.core.workbook import WorkbookService
    ws = WorkbookService(fake_repo, fake_ai)
    wb = ws.load_book("atomic_habits")
    assert wb.title == "Атомные привычки"
    assert len(wb.steps) == 3
    assert wb.steps[0].title == "Триггер"
    assert wb.reflection is not None
    assert wb.bonus is not None


def test_workbook_service_load_missing_raises(temp_workbooks_dir, fake_repo, fake_ai):
    from agent.core.workbook import WorkbookService
    ws = WorkbookService(fake_repo, fake_ai)
    with pytest.raises(FileNotFoundError):
        ws.load_book("nonexistent")


def test_workbook_service_rejects_path_traversal(fake_repo, fake_ai):
    from agent.core.workbook import WorkbookService
    ws = WorkbookService(fake_repo, fake_ai)
    for bad in ("../etc", "foo/bar", "foo\\bar", ".."):
        with pytest.raises(ValueError, match="Недопустимый slug"):
            ws.load_book(bad)


@pytest.mark.asyncio
async def test_repository_create_workbook_run_returns_row(fake_repo):
    from agent.storage.models import WorkbookRunRow
    run = await fake_repo.create_workbook_run(
        client_id=42, book_slug="atomic_habits", session_id=10
    )
    assert isinstance(run, WorkbookRunRow)
    assert run.id > 0
    assert run.client_id == 42
    assert run.book_slug == "atomic_habits"
    assert run.status == "in_progress"
    assert run.step_index == 0


@pytest.mark.asyncio
async def test_repository_get_active_finds_in_progress(fake_repo):
    await fake_repo.create_workbook_run(
        client_id=1, book_slug="a", session_id=1
    )
    await fake_repo.create_workbook_run(
        client_id=1, book_slug="b", session_id=1
    )
    active = await fake_repo.get_active_workbook_run(1)
    assert active is not None
    assert active.book_slug in ("a", "b")  # последний по id


@pytest.mark.asyncio
async def test_repository_get_active_ignores_completed(fake_repo):
    run = await fake_repo.create_workbook_run(
        client_id=1, book_slug="a", session_id=1
    )
    await fake_repo.mark_workbook_run_completed(run.id, "completed")
    active = await fake_repo.get_active_workbook_run(1)
    assert active is None


@pytest.mark.asyncio
async def test_repository_append_answer_updates_step(fake_repo):
    run = await fake_repo.create_workbook_run(
        client_id=1, book_slug="a", session_id=1, step_index=0
    )
    updated = await fake_repo.append_workbook_answer(run.id, 1, "мой ответ")
    assert updated is not None
    assert updated.step_index == 1
    assert updated.answer == "мой ответ"


@pytest.mark.asyncio
async def test_repository_append_answer_advances_index_only(fake_repo):
    run = await fake_repo.create_workbook_run(
        client_id=1, book_slug="a", session_id=1, step_index=0
    )
    updated = await fake_repo.append_workbook_answer(run.id, 1, None)
    assert updated.step_index == 1
    assert updated.answer is None  # answer не перезаписан


@pytest.mark.asyncio
async def test_repository_mark_completed_changes_status(fake_repo):
    run = await fake_repo.create_workbook_run(
        client_id=1, book_slug="a", session_id=1
    )
    updated = await fake_repo.mark_workbook_run_completed(run.id, "paused")
    assert updated is not None
    assert updated.status == "paused"


@pytest.mark.asyncio
async def test_repository_mark_completed_rejects_bad_status(fake_repo):
    run = await fake_repo.create_workbook_run(
        client_id=1, book_slug="a", session_id=1
    )
    with pytest.raises(ValueError, match="Недопустимый"):
        await fake_repo.mark_workbook_run_completed(run.id, "bogus")


# === Сервисный слой (reflect, start_run) ===

@pytest.mark.asyncio
async def test_workbook_service_start_run_creates_run(
    temp_workbooks_dir, fake_repo, fake_ai
):
    from agent.core.workbook import WorkbookService
    ws = WorkbookService(fake_repo, fake_ai)
    client = await fake_repo.upsert_client(email="c@x")
    session = await fake_repo.create_session(
        client_id=client.id, tone="warm", tone_intensity=3
    )
    run, step, wb = await ws.start_run(client, session, "atomic_habits")
    assert run.client_id == client.id
    assert run.book_slug == "atomic_habits"
    assert step.index == 0
    assert step.title == "Триггер"
    assert wb.title == "Атомные привычки"


@pytest.mark.asyncio
async def test_workbook_service_start_run_resumes_existing(
    temp_workbooks_dir, fake_repo, fake_ai
):
    from agent.core.workbook import WorkbookService
    ws = WorkbookService(fake_repo, fake_ai)
    client = await fake_repo.upsert_client(email="c@x")
    session = await fake_repo.create_session(
        client_id=client.id, tone="warm", tone_intensity=3
    )
    run1, _, _ = await ws.start_run(client, session, "atomic_habits")
    # Имитируем прогресс
    await fake_repo.append_workbook_answer(run1.id, 1, "answer")
    # Повторный start — должен вернуть ТОТ ЖЕ run с step_index=1
    run2, step2, _ = await ws.start_run(client, session, "atomic_habits")
    assert run2.id == run1.id
    assert step2.index == 1


@pytest.mark.asyncio
async def test_workbook_service_reflect_with_fake_ai(
    temp_workbooks_dir, fake_repo, fake_ai
):
    from agent.core.tones import Tone
    from agent.core.workbook import WorkbookService
    fake_ai.push_response("Это здорово осознано.")
    ws = WorkbookService(fake_repo, fake_ai)
    client = await fake_repo.upsert_client(email="c@x")
    session = await fake_repo.create_session(
        client_id=client.id, tone="warm", tone_intensity=3
    )
    run, step, wb = await ws.start_run(client, session, "atomic_habits")
    text, cost = await ws.reflect(
        tone=Tone.WARM,
        intensity=3,
        book_title=wb.title,
        step=step,
        answer="Вечером, на запах сладкого",
    )
    assert "здорово" in text
    assert cost >= 0.0
    assert fake_ai.call_count > 0  # AI был вызван


# === Обработчики (session._handle_*) ===

@pytest.mark.asyncio
async def test_workbook_list_command_shows_books(
    session_service, fake_repo
):
    """`/workbook` (без slug) → список книг в buttons."""
    # Подменяем books_dir
    from agent.config import settings
    settings.workbooks_dir = "tests/fixtures/workbooks"
    client = await fake_repo.upsert_client(email="c@x")
    session = await fake_repo.create_session(
        client_id=client.id, tone="warm", tone_intensity=3
    )
    resp = await session_service._handle_workbook_command(client, session, "/workbook")
    assert "Доступные воркбуки" in resp.text
    assert len(resp.buttons) == 3
    slugs = [b["payload"] for b in resp.buttons]
    assert any("atomic_habits" in s for s in slugs)
    assert resp.state.value == "S_DIALOG"


@pytest.mark.asyncio
async def test_workbook_start_creates_run_and_transitions(
    session_service, fake_repo
):
    from agent.config import settings
    settings.workbooks_dir = "tests/fixtures/workbooks"
    client = await fake_repo.upsert_client(email="c@x")
    session = await fake_repo.create_session(
        client_id=client.id, tone="warm", tone_intensity=3
    )
    # Сетапим S_DIALOG
    resp = await session_service._handle_workbook_command(
        client, session, "/workbook atomic_habits"
    )
    assert "Атомные привычки" in resp.text
    assert "Триггер" in resp.text
    assert resp.state.value == "S_WORKBOOK"
    # Run создан
    active = await fake_repo.get_active_workbook_run(client.id)
    assert active is not None
    assert active.book_slug == "atomic_habits"


@pytest.mark.asyncio
async def test_workbook_empty_answer_rejected_no_ai_call(
    session_service, fake_repo, fake_ai
):
    from agent.config import settings
    settings.workbooks_dir = "tests/fixtures/workbooks"
    client = await fake_repo.upsert_client(email="c@x")
    session = await fake_repo.create_session(
        client_id=client.id, tone="warm", tone_intensity=3
    )
    # Стартуем
    await session_service._handle_workbook_command(
        client, session, "/workbook atomic_habits"
    )
    # Пустой ответ
    resp = await session_service._handle_workbook(client, session, "")
    assert "Пока ответа нет" in resp.text or "пока без ответа" in resp.text.lower()
    # AI не вызывался
    assert fake_ai.call_count == 0
    # run не двинулся
    active = await fake_repo.get_active_workbook_run(client.id)
    assert active.step_index == 0


@pytest.mark.asyncio
async def test_workbook_answer_advances_and_calls_ai(
    session_service, fake_repo, fake_ai
):
    from agent.config import settings
    settings.workbooks_dir = "tests/fixtures/workbooks"
    fake_ai.push_response("Хороший триггер — теперь подумай о сигнале.")
    client = await fake_repo.upsert_client(email="c@x")
    session = await fake_repo.create_session(
        client_id=client.id, tone="warm", tone_intensity=3
    )
    await session_service._handle_workbook_command(
        client, session, "/workbook atomic_habits"
    )
    resp = await session_service._handle_workbook(
        client, session, "Вечером, на запах пирога"
    )
    assert "Хороший триггер" in resp.text
    assert "Шаг 2" in resp.text  # следующий шаг
    assert resp.state.value == "S_WORKBOOK"
    assert fake_ai.call_count > 0  # AI вызван
    active = await fake_repo.get_active_workbook_run(client.id)
    assert active.step_index == 1


@pytest.mark.asyncio
async def test_workbook_cancel_pauses_run(session_service, fake_repo):
    from agent.config import settings
    settings.workbooks_dir = "tests/fixtures/workbooks"
    client = await fake_repo.upsert_client(email="c@x")
    session = await fake_repo.create_session(
        client_id=client.id, tone="warm", tone_intensity=3
    )
    await session_service._handle_workbook_command(
        client, session, "/workbook atomic_habits"
    )
    resp = await session_service._handle_workbook(client, session, "/cancel")
    assert "Прогресс сохранён" in resp.text
    assert resp.state.value == "S_DIALOG"
    active = await fake_repo.get_active_workbook_run(client.id)
    assert active is None  # теперь paused, не in_progress


# === E2E ===

@pytest.mark.asyncio
async def test_workbook_e2e_through_all_steps(
    session_service, fake_repo, fake_ai
):
    from agent.config import settings
    settings.workbooks_dir = "tests/fixtures/workbooks"
    # deep_work = 2 шага
    for _ in range(2):
        fake_ai.push_response("Рефлексия.")
    client = await fake_repo.upsert_client(email="c@x")
    session = await fake_repo.create_session(
        client_id=client.id, tone="warm", tone_intensity=3
    )
    # Старт
    await session_service._handle_workbook_command(
        client, session, "/workbook deep_work"
    )
    # Шаг 1
    r1 = await session_service._handle_workbook(client, session, "ответ 1")
    assert r1.state.value == "S_WORKBOOK"
    # Шаг 2 (последний)
    r2 = await session_service._handle_workbook(client, session, "ответ 2")
    assert r2.state.value == "S_DIALOG"
    assert "пройден" in r2.text
    assert fake_ai.call_count == 2
    # run закрыт
    active = await fake_repo.get_active_workbook_run(client.id)
    assert active is None  # completed


@pytest.mark.asyncio
async def test_workbook_resume_after_cancel(
    session_service, fake_repo, fake_ai
):
    from agent.config import settings
    settings.workbooks_dir = "tests/fixtures/workbooks"
    client = await fake_repo.upsert_client(email="c@x")
    session = await fake_repo.create_session(
        client_id=client.id, tone="warm", tone_intensity=3
    )
    # Старт + шаг 1
    await session_service._handle_workbook_command(
        client, session, "/workbook atomic_habits"
    )
    fake_ai.push_response("ok")
    await session_service._handle_workbook(client, session, "ответ 1")
    # Ответили на шаг 1, теперь run in_progress на шаге 1
    # (atomic_habits: 0 -> 1, итого step_index=1 = "Действие")
    # Cancel
    await session_service._handle_workbook(client, session, "/cancel")
    # Resume
    resp = await session_service._handle_workbook_command(
        client, session, "/workbook"
    )
    # Должны быть в S_WORKBOOK с продолжением шага 2 (index 1 = "Действие")
    assert resp.state.value == "S_WORKBOOK"
    assert "Действие" in resp.text
