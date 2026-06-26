"""
SQL-миграции Cloudflare D1 для WishCoach.

Схема взята из PRD v2.0 раздел 6.1 + дополнения 5.8/7.2/9.2:
- client.onboarding_state, timezone, push_* поля
- client_channel (3 канала)
- desire: kind, score, verdict_label, module_scores (JSON), detector_depth, status
- desire_step: deadline, deadline_type, created/updated
- session: current_state, ended_reason, tone, tone_intensity, mode, crisis_flag, total_cost_usd, summary
- message: is_crisis_message, excluded_from_training
- workbook_run: status
- crisis_log: audit (только хэш, не текст!)

Соглашения:
- Все id — INTEGER (autoincrement D1)
- Timestamps — TEXT в ISO-8601 UTC
- JSON-поля — TEXT (SQLite JSON1 extension в D1 включён по умолчанию)
- Boolean — INTEGER 0/1
"""

from __future__ import annotations

from datetime import UTC

from agent.storage.d1_client import D1Client

# === Версия схемы ===
# При каждом изменении структуры увеличиваем SCHEMA_VERSION
# и добавляем миграцию (CREATE TABLE IF NOT EXISTS спасает только в простых случаях)
SCHEMA_VERSION = "2.0.0"


# === Полный скрипт (все таблицы) ===
# Разбит на CREATE-блоки для читаемости; в D1 отправляется целиком через exec_script

MIGRATION_001 = """
-- ============================================================
-- Migration 001: initial schema (Phase 0)
-- Версия: 2.0.0
-- Источник: PRD v2.0 раздел 6.1 + 5.8 + 7.2
-- ============================================================

-- --- Meta ---
CREATE TABLE IF NOT EXISTS schema_meta (
  key TEXT PRIMARY KEY,
  value TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

-- --- 1. client ---
CREATE TABLE IF NOT EXISTS client (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  email TEXT UNIQUE NOT NULL,
  name TEXT,
  current_tone TEXT NOT NULL DEFAULT 'warm',         -- 'warm' | 'clear' | 'bold' | 'soft'
  tone_intensity INTEGER NOT NULL DEFAULT 3,         -- 1..5
  timezone TEXT NOT NULL DEFAULT 'Europe/Moscow',
  push_enabled INTEGER NOT NULL DEFAULT 1,           -- 0/1
  push_time TEXT NOT NULL DEFAULT '10:00',
  onboarding_state TEXT NOT NULL DEFAULT 'new',       -- 'new' | 'tone_picked' | 'first_session_done'
  created_at TEXT NOT NULL,
  last_seen_at TEXT NOT NULL,
  subscription_status TEXT NOT NULL DEFAULT 'active'  -- 'active' | 'paused' | 'canceled' | 'expired'
);

CREATE INDEX IF NOT EXISTS idx_client_email ON client(email);
CREATE INDEX IF NOT EXISTS idx_client_subscription ON client(subscription_status);

-- --- 2. client_channel ---
CREATE TABLE IF NOT EXISTS client_channel (
  client_id INTEGER NOT NULL,
  channel TEXT NOT NULL,                             -- 'web' | 'telegram' | 'vk'
  external_id TEXT,                                  -- tg_chat_id / vk_user_id / NULL для web
  verified_at TEXT,
  last_seen_at TEXT,
  PRIMARY KEY (client_id, channel),
  FOREIGN KEY (client_id) REFERENCES client(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_channel_external ON client_channel(channel, external_id);

-- --- 3. desire ---
CREATE TABLE IF NOT EXISTS desire (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  client_id INTEGER NOT NULL,
  title TEXT NOT NULL,
  kind TEXT,                                         -- 'imposed' | 'true' | 'mixed'
  score REAL,                                        -- 0.0..1.0
  verdict_label TEXT,                                -- 6 подписей: imposed/mostly_imposed/mixed_low/mixed_high/mostly_true/true
  module_scores TEXT,                                -- JSON: { "m1": 0.6, "m2": 0.3, "m3": 0.8, ... }
  detector_depth TEXT,                               -- 'express' | 'standard' | 'deep'
  reasoning TEXT,                                    -- 2-3 предложения от коуча
  status TEXT NOT NULL DEFAULT 'active',             -- 'active' | 'released' | 'achieved' | 'paused'
  parent_desire_id INTEGER,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  FOREIGN KEY (client_id) REFERENCES client(id) ON DELETE CASCADE,
  FOREIGN KEY (parent_desire_id) REFERENCES desire(id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_desire_client ON desire(client_id);
CREATE INDEX IF NOT EXISTS idx_desire_status ON desire(client_id, status);
CREATE INDEX IF NOT EXISTS idx_desire_kind ON desire(kind);

-- --- 4. desire_step ---
CREATE TABLE IF NOT EXISTS desire_step (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  desire_id INTEGER NOT NULL,
  title TEXT NOT NULL,
  deadline TEXT,                                     -- ISO date
  deadline_type TEXT,                                -- 'micro_test' | 'first_step' | 'trial' | 'mini_project'
  status TEXT NOT NULL DEFAULT 'pending',            -- 'pending' | 'done' | 'skipped'
  done_at TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  FOREIGN KEY (desire_id) REFERENCES desire(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_step_desire ON desire_step(desire_id);
CREATE INDEX IF NOT EXISTS idx_step_status ON desire_step(desire_id, status);

-- --- 5. session ---
CREATE TABLE IF NOT EXISTS session (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  client_id INTEGER NOT NULL,
  started_at TEXT NOT NULL,
  ended_at TEXT,
  ended_reason TEXT,                                -- 'user_paused' | 'completed' | 'user_cancel' | 'idle_15min' | 'crisis_stop' | 'error_recoverable'
  current_state TEXT,                                -- 11 состояний state machine
  tone TEXT,                                         -- дубликат client.current_tone на момент сессии (для аналитики)
  tone_intensity INTEGER,                            -- 1..5
  mode TEXT,                                         -- 'checkin' | 'dialog' | 'decompose' | 'workbook' | 'detector'
  summary TEXT,                                      -- YandexGPT 3-5 предложений
  crisis_flag INTEGER NOT NULL DEFAULT 0,            -- 0/1
  total_cost_usd REAL NOT NULL DEFAULT 0,            -- для метрики cost per mode
  FOREIGN KEY (client_id) REFERENCES client(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_session_client ON session(client_id);
CREATE INDEX IF NOT EXISTS idx_session_started ON session(started_at);
CREATE INDEX IF NOT EXISTS idx_session_crisis ON session(crisis_flag);
CREATE INDEX IF NOT EXISTS idx_session_state ON session(current_state);

-- --- 6. message ---
CREATE TABLE IF NOT EXISTS message (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  session_id INTEGER NOT NULL,
  role TEXT NOT NULL,                                -- 'user' | 'assistant' | 'system'
  content TEXT NOT NULL,
  ts TEXT NOT NULL,
  is_crisis_message INTEGER NOT NULL DEFAULT 0,      -- 0/1
  excluded_from_training INTEGER NOT NULL DEFAULT 0, -- 0/1
  FOREIGN KEY (session_id) REFERENCES session(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_message_session ON message(session_id, ts);
CREATE INDEX IF NOT EXISTS idx_message_crisis ON message(is_crisis_message);

-- --- 7. workbook_run ---
CREATE TABLE IF NOT EXISTS workbook_run (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  client_id INTEGER NOT NULL,
  book_slug TEXT NOT NULL,
  session_id INTEGER,
  step_index INTEGER NOT NULL,
  answer TEXT,
  status TEXT NOT NULL DEFAULT 'in_progress',        -- 'in_progress' | 'paused' | 'completed'
  created_at TEXT NOT NULL,
  FOREIGN KEY (client_id) REFERENCES client(id) ON DELETE CASCADE,
  FOREIGN KEY (session_id) REFERENCES session(id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_workbook_client ON workbook_run(client_id);
CREATE INDEX IF NOT EXISTS idx_workbook_slug ON workbook_run(client_id, book_slug);
CREATE INDEX IF NOT EXISTS idx_workbook_status ON workbook_run(status);

-- --- 8. crisis_log (только хэш, НЕ текст!) ---
CREATE TABLE IF NOT EXISTS crisis_log (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  client_id INTEGER,
  session_id INTEGER,
  channel TEXT,                                      -- 'web' | 'telegram' | 'vk'
  message_hash TEXT NOT NULL,                        -- SHA-256 (только хэш, исходное сообщение НЕ сохраняем)
  matched_pattern TEXT NOT NULL,                     -- какой из 4 regex сработал
  created_at TEXT NOT NULL,
  followed_up_at TEXT                                -- через 24ч мягкий follow-up
);

CREATE INDEX IF NOT EXISTS idx_crisis_client ON crisis_log(client_id);
CREATE INDEX IF NOT EXISTS idx_crisis_created ON crisis_log(created_at);

-- --- 9. tone_profile (для A/B-тестов тонов, Phase 2+) ---
-- Пока пустая, но в PRD v2.0 зарезервирована
CREATE TABLE IF NOT EXISTS tone_profile (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  client_id INTEGER NOT NULL,
  assigned_tone TEXT NOT NULL,
  assigned_at TEXT NOT NULL,
  source TEXT,                                       -- 'manual' | 'ab_test'
  FOREIGN KEY (client_id) REFERENCES client(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_tone_client ON tone_profile(client_id);
"""


# === Хелпер: проверка и применение миграций ===

MIGRATIONS: list[str] = [
    ("001_initial", MIGRATION_001),
]


def apply_migrations(client: D1Client | None = None) -> dict[str, str]:
    """
    Применить все миграции. Идемпотентно (CREATE TABLE IF NOT EXISTS).

    Возвращает dict {version: "applied"|"skipped"}.
    """
    from datetime import datetime

    from agent.utils import get_logger

    log = get_logger("migrations")
    own = client is None
    client = client or D1Client()
    applied: dict[str, str] = {}

    try:
        # 1. Создаём meta-таблицу (если её нет — MIGRATION_001 создаст)
        #    Здесь мы сначала пушим MIGRATION_001, она содержит schema_meta.
        for name, sql in MIGRATIONS:
            log.info("migrations.apply", name=name)
            client.exec_script(sql)
            applied[name] = "applied"

        # 2. Записываем текущую версию
        now = datetime.now(UTC).isoformat()
        try:
            client.execute(
                "INSERT OR REPLACE INTO schema_meta (key, value, updated_at) VALUES (?, ?, ?)",
                ["schema_version", SCHEMA_VERSION, now],
            )
        except Exception as e:
            # Если INSERT не сработал из-за UNIQUE на key — ок, перезаписываем
            log.warning("migrations.meta_insert_failed", error=str(e))
            client.execute(
                "UPDATE schema_meta SET value = ?, updated_at = ? WHERE key = ?",
                [SCHEMA_VERSION, now, "schema_version"],
            )
    finally:
        if own:
            client.close()

    return applied


def get_current_version(client: D1Client | None = None) -> str | None:
    """Вернуть текущую применённую версию схемы (None если ничего не применено)."""
    own = client is None
    client = client or D1Client()
    try:
        row = client.fetch_one("SELECT value FROM schema_meta WHERE key = 'schema_version'")
        return row["value"] if row else None
    except Exception:
        return None
    finally:
        if own:
            client.close()


__all__ = [
    "MIGRATIONS",
    "MIGRATION_001",
    "SCHEMA_VERSION",
    "apply_migrations",
    "get_current_version",
]
