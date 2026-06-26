"""
GET  /coach/workbook/list      — список воркбуков на диске
POST /coach/workbook/start     — стартовать воркбук (slug)
POST /coach/workbook/answer    — ответ на текущий шаг
GET  /coach/workbook/progress  — текущий прогресс in_progress run
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from agent.api.deps import get_client_id, get_repository, get_session_service
from agent.api.schemas import (
    BookInfo,
    BookListResponse,
    WorkbookAnswerRequest,
    WorkbookAnswerResponse,
    WorkbookProgressResponse,
    WorkbookStartRequest,
    WorkbookStartResponse,
    WorkbookStepOut,
)
from agent.core.session import SessionService
from agent.core.states import SessionState
from agent.storage.repository import Repository

router = APIRouter(prefix="/workbook", tags=["workbook"])


def _step_to_out(step) -> WorkbookStepOut:
    return WorkbookStepOut(
        index=step.index,
        title=step.title,
        body=step.body,
        has_questions=step.has_questions,
    )


def _book_to_info(meta) -> BookInfo:
    return BookInfo(
        slug=meta.slug,
        title=meta.title,
        step_count=meta.step_count,
        has_reflection=meta.has_reflection,
        has_bonus=meta.has_bonus,
    )


@router.get("/list", response_model=BookListResponse)
async def list_workbooks(
    repo: Repository = Depends(get_repository),
    svc: SessionService = Depends(get_session_service),
) -> BookListResponse:
    """Список воркбуков в BOOKS_DIR."""
    metas = svc._workbook.list_books()
    return BookListResponse(items=[_book_to_info(m) for m in metas])


@router.post("/start", response_model=WorkbookStartResponse)
async def start_workbook(
    req: WorkbookStartRequest,
    client_id: int = Depends(get_client_id),
    repo: Repository = Depends(get_repository),
    svc: SessionService = Depends(get_session_service),
) -> WorkbookStartResponse:
    """Создать или возобновить workbook_run для slug."""
    client = await repo.get_client_by_id(client_id)
    if client is None:
        raise HTTPException(status_code=404, detail="client not found")
    session, _ = await svc.get_or_create_session(client, channel="web")
    try:
        run, step, workbook = await svc._workbook.start_run(
            client, session, req.slug
        )
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    try:
        await svc._fsm.transition(
            session, SessionState.S_WORKBOOK, reason="wb_start"
        )
    except Exception:
        pass
    total = len(workbook.steps)
    return WorkbookStartResponse(
        run_id=run.id,
        book_slug=workbook.slug,
        book_title=workbook.title,
        step=_step_to_out(step),
        total_steps=total,
        status=run.status,
        progress_pct=int(step.index / total * 100) if total else 0,
    )


@router.post("/answer", response_model=WorkbookAnswerResponse)
async def answer_workbook(
    req: WorkbookAnswerRequest,
    client_id: int = Depends(get_client_id),
    repo: Repository = Depends(get_repository),
    svc: SessionService = Depends(get_session_service),
) -> WorkbookAnswerResponse:
    """Ответ клиента на текущий шаг воркбука.

    Делает:
    1. Достаёт active run.
    2. Сохраняет ответ.
    3. Зовёт AI-рефлексию.
    4. Возвращает reflection + следующий шаг (или is_last=True).
    """
    client = await repo.get_client_by_id(client_id)
    if client is None:
        raise HTTPException(status_code=404, detail="client not found")
    session, _ = await svc.get_or_create_session(client, channel="web")

    # Делегируем в session._handle_workbook, чтобы переиспользовать всю логику.
    # Но чтобы получить структурный ответ, парсим CoachResponse.
    # Прямой вызов идёт через приватный метод _handle_workbook_answer.
    active = await repo.get_active_workbook_run(client.id)
    if active is None:
        raise HTTPException(status_code=409, detail="no active workbook run")

    # Загружаем книгу
    try:
        workbook = svc._workbook.load_book(active.book_slug)
    except FileNotFoundError as e:
        raise HTTPException(status_code=410, detail=str(e)) from e
    try:
        step = svc._workbook.current_step(active, workbook)
    except IndexError:
        # Уже за пределами — закрываем
        await repo.mark_workbook_run_completed(active.id, "completed")
        raise HTTPException(status_code=409, detail="workbook already completed") from None

    answer = req.text.strip()
    if not answer or len(answer) < 3:
        # Не сохраняем, возвращаем текущий шаг с пометкой
        return WorkbookAnswerResponse(
            run_id=active.id,
            book_title=workbook.title,
            reflection="Пока ответа нет — напиши хотя бы пару предложений.",
            next_step=_step_to_out(step),
            is_last=False,
            status=active.status,
            cost_usd=0.0,
        )

    from agent.core.tones import Tone

    next_idx = step.index + 1
    await repo.append_workbook_answer(active.id, next_idx, answer)
    tone = Tone(client.current_tone)
    reflection, cost = await svc._workbook.reflect(
        tone=tone,
        intensity=client.tone_intensity,
        book_title=workbook.title,
        step=step,
        answer=answer,
    )

    if next_idx >= len(workbook.steps):
        updated = await repo.mark_workbook_run_completed(active.id, "completed")
        try:
            await svc._fsm.transition(
                session, SessionState.S_DIALOG, reason="wb_completed"
            )
        except Exception:
            pass
        return WorkbookAnswerResponse(
            run_id=active.id,
            book_title=workbook.title,
            reflection=reflection,
            next_step=None,
            is_last=True,
            status=updated.status if updated else "completed",
            cost_usd=cost,
        )

    next_step = workbook.steps[next_idx]
    return WorkbookAnswerResponse(
        run_id=active.id,
        book_title=workbook.title,
        reflection=reflection,
        next_step=_step_to_out(next_step),
        is_last=False,
        status=active.status,
        cost_usd=cost,
    )


@router.get("/progress", response_model=WorkbookProgressResponse)
async def workbook_progress(
    client_id: int = Depends(get_client_id),
    repo: Repository = Depends(get_repository),
    svc: SessionService = Depends(get_session_service),
) -> WorkbookProgressResponse:
    """Текущий прогресс клиента (in_progress run). 404 если нет."""
    active = await repo.get_active_workbook_run(client_id)
    if active is None:
        raise HTTPException(status_code=404, detail="no active workbook run")
    try:
        workbook = svc._workbook.load_book(active.book_slug)
    except FileNotFoundError as e:
        raise HTTPException(status_code=410, detail=str(e)) from e
    total = len(workbook.steps)
    last = active.answer
    return WorkbookProgressResponse(
        run_id=active.id,
        book_slug=workbook.slug,
        book_title=workbook.title,
        step_index=active.step_index,
        total_steps=total,
        status=active.status,
        last_answer_preview=(last[:120] + "…") if last and len(last) > 120 else last,
    )
