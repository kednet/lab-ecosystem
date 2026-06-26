"""
POST /coach/desire, GET /coach/desires
"""

from __future__ import annotations

from fastapi import APIRouter, Depends

from agent.api.deps import get_client_id, get_repository
from agent.api.schemas import (
    CoachResponse,
    DesireCreateRequest,
    DesireResponse,
    DesiresListResponse,
)
from agent.storage.repository import Repository

router = APIRouter(tags=["desires"])


@router.post("/desire", response_model=CoachResponse)
async def create_desire(
    req: DesireCreateRequest,
    client_id: int = Depends(get_client_id),
    repo: Repository = Depends(get_repository),
) -> CoachResponse:
    client = await repo.get_client_by_id(client_id)
    if client is None:
        client = await repo.upsert_client(email=f"client_{client_id}@local")
    desire = await repo.create_desire(client_id=client_id, title=req.title)
    return CoachResponse(
        text=f'Сохранил желание #{desire.id}: "{desire.title}".',
        state="S_DESIRE_DECOMP",
    )


@router.get("/desires", response_model=DesiresListResponse)
async def list_desires(
    client_id: int = Depends(get_client_id),
    repo: Repository = Depends(get_repository),
) -> DesiresListResponse:
    desires = await repo.get_active_desires(client_id)
    return DesiresListResponse(
        items=[
            DesireResponse(
                id=d.id,
                title=d.title,
                status=d.status,
                verdict_label=d.verdict_label,
                score=d.score,
            )
            for d in desires
        ]
    )
