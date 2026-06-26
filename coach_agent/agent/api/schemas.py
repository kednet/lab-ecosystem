"""
Pydantic-схемы для API.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

# === Кнопки (отображение) ===

class ButtonOut(BaseModel):
    label: str
    payload: str
    kind: str


# === Главный ответ коуча ===

class CoachResponse(BaseModel):
    text: str
    buttons: list[ButtonOut] = Field(default_factory=list)
    state: str | None = None
    welcome_back: str | None = None
    crisis_flag: bool = False
    cost_usd: float = 0.0
    finished: bool = False


# === Запросы ===

class MessageRequest(BaseModel):
    text: str = Field(min_length=1, max_length=2000)
    channel: str = Field(default="web", pattern="^(web|telegram|vk)$")


class ToneRequest(BaseModel):
    tone: Literal["warm", "clear", "bold", "soft"]
    intensity: int = Field(default=3, ge=1, le=5)


class StartRequest(BaseModel):
    choice: Literal["talk", "checkin", "desire", "workbook", "unsure"]


class EndRequest(BaseModel):
    mode: Literal["save", "complete"]


class DesireCreateRequest(BaseModel):
    title: str = Field(min_length=1, max_length=200)


# === Ответы на остальные эндпоинты ===

class SessionStateResponse(BaseModel):
    session_id: int
    current_state: str | None
    tone: str | None
    tone_intensity: int | None
    mode: str | None
    message_count: int
    active_desire_id: int | None = None
    onboarding_state: str
    total_cost_usd: float


class EndResponse(BaseModel):
    session_id: int
    ended_reason: str | None
    summary: str | None = None


class DesireResponse(BaseModel):
    id: int
    title: str
    status: str
    verdict_label: str | None = None
    score: float | None = None


class DesiresListResponse(BaseModel):
    items: list[DesireResponse]


# === Workbook (Phase 4) ===

class BookInfo(BaseModel):
    slug: str
    title: str
    step_count: int
    has_reflection: bool
    has_bonus: bool


class BookListResponse(BaseModel):
    items: list[BookInfo]


class WorkbookStepOut(BaseModel):
    index: int
    title: str
    body: str
    has_questions: bool


class WorkbookStartRequest(BaseModel):
    slug: str = Field(min_length=1, max_length=200)


class WorkbookStartResponse(BaseModel):
    run_id: int
    book_slug: str
    book_title: str
    step: WorkbookStepOut
    total_steps: int
    status: str
    progress_pct: int


class WorkbookAnswerRequest(BaseModel):
    text: str = Field(min_length=1, max_length=2000)


class WorkbookAnswerResponse(BaseModel):
    run_id: int
    book_title: str
    reflection: str
    next_step: WorkbookStepOut | None
    is_last: bool
    status: str
    cost_usd: float


class WorkbookProgressResponse(BaseModel):
    run_id: int
    book_slug: str
    book_title: str
    step_index: int
    total_steps: int
    status: str
    last_answer_preview: str | None = None


__all__ = [
    "ButtonOut",
    "CoachResponse",
    "MessageRequest",
    "ToneRequest",
    "StartRequest",
    "EndRequest",
    "DesireCreateRequest",
    "SessionStateResponse",
    "EndResponse",
    "DesireResponse",
    "DesiresListResponse",
    "BookInfo",
    "BookListResponse",
    "WorkbookStepOut",
    "WorkbookStartRequest",
    "WorkbookStartResponse",
    "WorkbookAnswerRequest",
    "WorkbookAnswerResponse",
    "WorkbookProgressResponse",
]
