"""
FastAPI dependencies.

Phase 1: client_id берётся из заголовка X-Client-Id.
Phase 0 lab_site: после внедрения magic-link заменим на JWT-валидацию.
"""

from __future__ import annotations

from fastapi import Header, HTTPException, Request

from agent.ai.factory import get_ai_client as _get_ai_client
from agent.core.session import SessionService
from agent.storage.repository import Repository


def get_repository(request: Request) -> Repository:
    repo = getattr(request.app.state, "repository", None)
    if repo is None:
        raise HTTPException(status_code=503, detail="repository not initialized")
    return repo


def get_session_service(request: Request) -> SessionService:
    svc = getattr(request.app.state, "session_service", None)
    if svc is None:
        raise HTTPException(status_code=503, detail="session_service not initialized")
    return svc


def get_client_id(x_client_id: int = Header(..., ge=1, alias="X-Client-Id")) -> int:
    """Идентификация клиента через заголовок. Phase 0."""
    return x_client_id


def get_ai_client():
    """DI-обёртка для AI-клиента (с lazy init)."""
    return _get_ai_client(prefer="claude")


__all__ = ["get_repository", "get_session_service", "get_client_id", "get_ai_client"]
