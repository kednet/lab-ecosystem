"""
POST /coach/message — главный эндпоинт диалога.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends

from agent.api.deps import get_client_id, get_repository, get_session_service
from agent.api.schemas import ButtonOut, CoachResponse, MessageRequest
from agent.core.session import SessionService
from agent.storage.repository import Repository

router = APIRouter(tags=["chat"])


@router.post("/message", response_model=CoachResponse)
async def post_message(
    req: MessageRequest,
    client_id: int = Depends(get_client_id),
    repo: Repository = Depends(get_repository),
    svc: SessionService = Depends(get_session_service),
) -> CoachResponse:
    """Отправить сообщение коучу. Возвращает ответ + кнопки + state.

    Phase 7: `channel` в теле запроса — на будущее (по умолчанию "web").
    VK/TG используют свои эндпоинты и не ходят сюда.
    """
    client = await repo.get_client_by_id(client_id)
    if client is None:
        # Auto-create на лету (Phase 0 без auth)
        client = await repo.upsert_client(email=f"client_{client_id}@local")
    resp = await svc.process_message(
        client=client, text=req.text, channel=req.channel
    )
    return CoachResponse(
        text=resp.text,
        buttons=[ButtonOut(**b) for b in resp.buttons],
        state=resp.state.value if resp.state else None,
        welcome_back=resp.welcome_back,
        crisis_flag=resp.crisis_flag,
        cost_usd=resp.cost_usd,
        finished=resp.finished,
    )
