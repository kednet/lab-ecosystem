"""
Хелперы для тестов: фабрики моделей.
"""

from __future__ import annotations

from agent.storage.models import (
    ClientRow,
    DesireRow,
    MessageRow,
    SessionRow,
)


def make_client(
    id: int = 1,
    email: str | None = None,
    current_tone: str = "warm",
    tone_intensity: int = 3,
    onboarding_state: str = "new",
) -> ClientRow:
    return ClientRow(
        id=id,
        email=email or f"client_{id}@local",
        name=None,
        current_tone=current_tone,
        tone_intensity=tone_intensity,
        timezone="Europe/Moscow",
        push_enabled=1,
        push_time="10:00",
        onboarding_state=onboarding_state,
        created_at="2026-06-10T00:00:00+00:00",
        last_seen_at="2026-06-10T00:00:00+00:00",
        subscription_status="active",
    )


def make_session(
    id: int = 1,
    client_id: int = 1,
    current_state: str = "S_DIALOG",
    tone: str = "warm",
    tone_intensity: int = 3,
    started_at: str = "2026-06-10T00:00:00+00:00",
    ended_at: str | None = None,
    ended_reason: str | None = None,
    total_cost_usd: float = 0.0,
) -> SessionRow:
    return SessionRow(
        id=id,
        client_id=client_id,
        started_at=started_at,
        ended_at=ended_at,
        ended_reason=ended_reason,
        current_state=current_state,
        tone=tone,
        tone_intensity=tone_intensity,
        mode="dialog",
        summary=None,
        crisis_flag=0,
        total_cost_usd=total_cost_usd,
    )


def make_message(
    id: int = 1,
    session_id: int = 1,
    role: str = "user",
    content: str = "",
    ts: str = "2026-06-10T00:00:00+00:00",
    is_crisis: int = 0,
) -> MessageRow:
    return MessageRow(
        id=id,
        session_id=session_id,
        role=role,
        content=content,
        ts=ts,
        is_crisis_message=is_crisis,
        excluded_from_training=0,
    )


def make_desire(
    id: int = 1,
    client_id: int = 1,
    title: str = "Test desire",
    verdict_label: str | None = None,
    score: float | None = None,
    status: str = "active",
) -> DesireRow:
    return DesireRow(
        id=id,
        client_id=client_id,
        title=title,
        kind=None,
        score=score,
        verdict_label=verdict_label,
        module_scores=None,
        detector_depth=None,
        reasoning=None,
        status=status,
        parent_desire_id=None,
        created_at="2026-06-10T00:00:00+00:00",
        updated_at="2026-06-10T00:00:00+00:00",
    )


__all__ = ["make_client", "make_session", "make_message", "make_desire"]
