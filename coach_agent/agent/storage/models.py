"""
Pydantic v2 модели для строк D1.

Соответствуют таблицам из agent/storage/migrations.py (PRD v2.0 раздел 6.1).

Конвенции:
- Все id — int (D1 autoincrement)
- Timestamps — str в ISO-8601 UTC (парсятся в datetime при необходимости)
- JSON-поля — str, парсятся через json.loads (D1 SQLite JSON1)
- Boolean — int 0/1, конвертируется в bool на границе API
- Optional — Optional[T] = None для nullable колонок
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict


class D1Row(BaseModel):
    """Базовая модель для строки D1."""

    model_config = ConfigDict(from_attributes=True, extra="ignore")

    @classmethod
    def from_d1_row(cls, row: dict[str, Any]) -> D1Row:
        """Парсит строку из D1 (dict) в модель.

        D1 возвращает bool как 0/1, datetime как ISO-8601 строки.
        """
        return cls.model_validate(row)


# === Client ===

class ClientRow(D1Row):
    id: int
    email: str
    name: str | None = None
    current_tone: str = "warm"
    tone_intensity: int = 3
    timezone: str = "Europe/Moscow"
    push_enabled: int = 1
    push_time: str = "10:00"
    onboarding_state: str = "new"  # 'new' | 'tone_picked' | 'first_session_done'
    created_at: str
    last_seen_at: str
    subscription_status: str = "active"  # 'active' | 'paused' | 'canceled' | 'expired'


# === ClientChannel ===

class ClientChannelRow(D1Row):
    client_id: int
    channel: str  # 'web' | 'telegram' | 'vk'
    external_id: str | None = None
    verified_at: str | None = None
    last_seen_at: str | None = None


# === Session ===

class SessionRow(D1Row):
    id: int
    client_id: int
    started_at: str
    ended_at: str | None = None
    ended_reason: str | None = None
    # 'user_paused' | 'completed' | 'user_cancel' | 'idle_15min' | 'crisis_stop' | 'error_recoverable'
    current_state: str | None = None
    tone: str | None = None
    tone_intensity: int | None = None
    mode: str | None = None  # 'checkin' | 'dialog' | 'decompose' | 'workbook' | 'detector'
    summary: str | None = None
    crisis_flag: int = 0
    total_cost_usd: float = 0.0


# === Message ===

class MessageRow(D1Row):
    id: int
    session_id: int
    role: str  # 'user' | 'assistant' | 'system'
    content: str
    ts: str
    is_crisis_message: int = 0
    excluded_from_training: int = 0


# === Desire ===

class DesireRow(D1Row):
    id: int
    client_id: int
    title: str
    kind: str | None = None  # 'imposed' | 'true' | 'mixed'
    score: float | None = None  # 0.0..1.0
    # 6 подписей: 'imposed' | 'mostly_imposed' | 'mixed_low' | 'mixed_high' | 'mostly_true' | 'true'
    verdict_label: str | None = None
    module_scores: str | None = None  # JSON
    detector_depth: str | None = None  # 'express' | 'standard' | 'deep'
    reasoning: str | None = None
    status: str = "active"  # 'active' | 'released' | 'achieved' | 'paused'
    parent_desire_id: int | None = None
    created_at: str
    updated_at: str


# === DesireStep ===

class DesireStepRow(D1Row):
    id: int
    desire_id: int
    title: str
    deadline: str | None = None
    deadline_type: str | None = None
    # 'micro_test' (3д) | 'first_step' (7д) | 'trial' (14д) | 'mini_project' (30д)
    status: str = "pending"  # 'pending' | 'done' | 'skipped'
    done_at: str | None = None
    created_at: str
    updated_at: str


# === CrisisLog (только хэш, не текст!) ===

class CrisisLogRow(D1Row):
    id: int
    client_id: int | None = None
    session_id: int | None = None
    channel: str | None = None
    message_hash: str  # SHA-256
    matched_pattern: str
    created_at: str
    followed_up_at: str | None = None


# === WorkbookRun ===

class WorkbookRunRow(D1Row):
    id: int
    client_id: int
    book_slug: str
    session_id: int | None = None
    step_index: int
    answer: str | None = None
    status: str = "in_progress"  # 'in_progress' | 'paused' | 'completed'
    created_at: str


# === ToneProfile ===

class ToneProfileRow(D1Row):
    id: int
    client_id: int
    assigned_tone: str
    assigned_at: str
    source: str | None = None  # 'manual' | 'ab_test'


__all__ = [
    "D1Row",
    "ClientRow",
    "ClientChannelRow",
    "SessionRow",
    "MessageRow",
    "DesireRow",
    "DesireStepRow",
    "CrisisLogRow",
    "WorkbookRunRow",
    "ToneProfileRow",
]
