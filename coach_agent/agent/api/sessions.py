"""
GET /coach/session, POST /coach/end
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from agent.api.deps import get_client_id, get_repository, get_session_service
from agent.api.schemas import EndRequest, EndResponse, SessionStateResponse
from agent.core.session import SessionService
from agent.storage.repository import Repository

router = APIRouter(tags=["sessions"])


@router.get("/session", response_model=SessionStateResponse)
async def get_session(
    client_id: int = Depends(get_client_id),
    repo: Repository = Depends(get_repository),
) -> SessionStateResponse:
    client = await repo.get_client_by_id(client_id)
    if client is None:
        raise HTTPException(status_code=404, detail="client not found")
    session = await repo.get_active_session(client_id) or await repo.get_last_session(client_id)
    if session is None:
        return SessionStateResponse(
            session_id=0,
            current_state=None,
            tone=client.current_tone,
            tone_intensity=client.tone_intensity,
            mode=None,
            message_count=0,
            onboarding_state=client.onboarding_state,
            total_cost_usd=0.0,
        )
    msg_count = await repo.count_messages(session.id)
    desires = await repo.get_active_desires(client_id)
    return SessionStateResponse(
        session_id=session.id,
        current_state=session.current_state,
        tone=session.tone or client.current_tone,
        tone_intensity=session.tone_intensity or client.tone_intensity,
        mode=session.mode,
        message_count=msg_count,
        active_desire_id=desires[0].id if desires else None,
        onboarding_state=client.onboarding_state,
        total_cost_usd=session.total_cost_usd,
    )


@router.post("/end", response_model=EndResponse)
async def end_session(
    req: EndRequest,
    client_id: int = Depends(get_client_id),
    repo: Repository = Depends(get_repository),
    svc: SessionService = Depends(get_session_service),
) -> EndResponse:
    client = await repo.get_client_by_id(client_id)
    if client is None:
        raise HTTPException(status_code=404, detail="client not found")
    session = await svc.end_session(client, req.mode)
    return EndResponse(
        session_id=session.id,
        ended_reason=session.ended_reason,
        summary=session.summary,
    )
