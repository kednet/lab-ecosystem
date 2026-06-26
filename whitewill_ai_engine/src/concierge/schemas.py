"""Pydantic-схемы для модуля консьержа."""

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class ClientLang(str, Enum):
    RU = "ru"
    EN = "en"


class IntentType(str, Enum):
    PERSONAL = "personal"
    INVESTMENT = "investment"
    PRESERVATION = "preservation"
    UNKNOWN = "unknown"


class DialogState(str, Enum):
    WELCOME = "welcome"
    GOAL = "goal"
    BUDGET = "budget"
    DISTRICT = "district"
    TIMELINE = "timeline"
    PAYMENT = "payment"
    DETAILS = "details"
    QUALIFIED = "qualified"
    HANDOFF = "handoff"
    ERROR = "error"


class ChatRequest(BaseModel):
    """Запрос клиента к консьержу."""

    session_id: str = Field(..., description="Уникальный ID сессии (UUID)")
    message: str = Field(..., min_length=1, max_length=2000)
    lang: ClientLang | None = Field(default=None, description="Язык (если None — автодетект)")
    source: str = Field(default="web", description="Канал: web / telegram / whatsapp")


class ChatResponse(BaseModel):
    """Ответ консьержа."""

    session_id: str
    reply: str
    state: DialogState
    is_qualified: bool = False
    score: float = 0.0
    matched_properties: list[dict] = Field(default_factory=list)
    next_question: str | None = None
    crm_lead_id: str | None = None
    cost_rub: float = 0.0
    latency_ms: int = 0


class PropertyMatch(BaseModel):
    """Найденный объект по RAG."""

    id: int
    title: str
    title_en: str
    district: str
    price_rub: int
    area_sqm: float
    rooms: int
    score: float


class QualifiedLead(BaseModel):
    """Qualified lead для передачи в CRM."""

    session_id: str
    client_lang: ClientLang
    intent: IntentType
    budget: str
    district: str
    timeline: str
    payment: str
    details: str = ""
    score: float
    source: str
    matched_properties: list[int] = Field(default_factory=list)
    dialog_summary: str = ""


class HealthResponse(BaseModel):
    status: str
    version: str
    llm_mode: str
    database: str
    timestamp: datetime
