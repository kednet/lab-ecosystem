"""
POST /coach/tone — смена тона в любой момент.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends

from agent.api.deps import get_client_id, get_repository
from agent.api.schemas import CoachResponse, ToneRequest
from agent.storage.repository import Repository

router = APIRouter(tags=["tones"])


@router.post("/tone", response_model=CoachResponse)
async def change_tone(
    req: ToneRequest,
    client_id: int = Depends(get_client_id),
    repo: Repository = Depends(get_repository),
) -> CoachResponse:
    client = await repo.get_client_by_id(client_id)
    if client is None:
        client = await repo.upsert_client(
            email=f"client_{client_id}@local",
            current_tone=req.tone,
            tone_intensity=req.intensity,
        )
    else:
        client = await repo.update_client_tone(client_id, req.tone, req.intensity) or client
    return CoachResponse(
        text=f"Тон изменён на {req.tone} × {req.intensity}.",
        state="S_DIALOG",
    )
