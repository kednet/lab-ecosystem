"""
POST /coach/onboarding/tone, /coach/onboarding/start
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from agent.api.deps import get_client_id, get_repository, get_session_service
from agent.api.schemas import ButtonOut, CoachResponse, StartRequest, ToneRequest
from agent.core.session import SessionService
from agent.core.tones import Tone
from agent.storage.repository import Repository

router = APIRouter(prefix="/onboarding", tags=["onboarding"])


@router.post("/tone", response_model=CoachResponse)
async def onboarding_tone(
    req: ToneRequest,
    client_id: int = Depends(get_client_id),
    repo: Repository = Depends(get_repository),
    svc: SessionService = Depends(get_session_service),
) -> CoachResponse:
    """Выбор тона в онбординге."""
    client = await repo.get_client_by_id(client_id)
    if client is None:
        client = await repo.upsert_client(
            email=f"client_{client_id}@local",
            current_tone=req.tone,
            tone_intensity=req.intensity,
        )
    # Создаём/берём сессию
    session, _ = await svc.get_or_create_session(client, channel="web")
    # FSM → S_ONBOARD
    try:
        from agent.core.states import SessionState
        await svc._fsm.transition(session, SessionState.S_ONBOARD, reason="onboarding")
    except Exception:
        pass
    # Перечитываем
    session = await repo.get_session_by_id(session.id) or session
    # pick_tone
    result = await svc._onboarding.pick_tone(
        client, session, Tone(req.tone), req.intensity
    )
    return CoachResponse(
        text=result.text,
        buttons=[ButtonOut(**b.__dict__) for b in result.buttons],
        state=result.state.value if result.state else None,
    )


@router.post("/start", response_model=CoachResponse)
async def onboarding_start(
    req: StartRequest,
    client_id: int = Depends(get_client_id),
    repo: Repository = Depends(get_repository),
    svc: SessionService = Depends(get_session_service),
) -> CoachResponse:
    """Выбор старта в онбординге."""
    client = await repo.get_client_by_id(client_id)
    if client is None:
        raise HTTPException(status_code=404, detail="client not found")
    session = await repo.get_active_session(client_id)
    if session is None:
        session = await repo.get_last_session(client_id)
    if session is None:
        # Создаём
        session, _ = await svc.get_or_create_session(client, channel="web")
    result = await svc._onboarding.pick_start(client, session, req.choice)
    return CoachResponse(
        text=result.text,
        buttons=[ButtonOut(**b.__dict__) for b in result.buttons],
        state=result.state.value if result.state else None,
    )
