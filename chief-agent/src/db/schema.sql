-- Chief Agent v2.0 — SQLite schema
-- Forward-only: append new migrations, never edit existing ones.
-- Migrations applied by src/db/migrate.js on every boot.

-- ============================================================
-- v1.0 (original)
-- ============================================================
CREATE TABLE IF NOT EXISTS agents (
  id              TEXT PRIMARY KEY,
  display_name    TEXT NOT NULL,
  description     TEXT,
  type            TEXT NOT NULL,        -- subprocess | http | systemd | remote
  enabled         INTEGER NOT NULL DEFAULT 1,
  metadata_json   TEXT,
  created_at      TEXT NOT NULL DEFAULT (datetime('now')),
  updated_at      TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS actions (
  id                       TEXT PRIMARY KEY,
  agent_id                 TEXT NOT NULL REFERENCES agents(id) ON DELETE CASCADE,
  display_name             TEXT NOT NULL,
  params_json              TEXT,
  dry_run_supported        INTEGER NOT NULL DEFAULT 0,
  estimated_duration_sec   INTEGER NOT NULL DEFAULT 60,
  UNIQUE(agent_id, id)
);
CREATE INDEX IF NOT EXISTS idx_actions_agent ON actions(agent_id);

CREATE TABLE IF NOT EXISTS jobs (
  id                  TEXT PRIMARY KEY,
  agent_id            TEXT NOT NULL REFERENCES agents(id),
  action_id           TEXT NOT NULL,
  status              TEXT NOT NULL,               -- queued|running|completed|failed|cancelled|awaiting_approval
  params_json         TEXT,
  stdout              TEXT,
  stderr              TEXT,
  exit_code           INTEGER,
  pid                 INTEGER,
  started_at          TEXT,
  finished_at         TEXT,
  dry_run             INTEGER NOT NULL DEFAULT 0,
  triggered_by        TEXT NOT NULL,
  triggered_by_user   TEXT,
  error_message       TEXT,
  created_at          TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_jobs_agent_created ON jobs(agent_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_jobs_status       ON jobs(status, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_jobs_created      ON jobs(created_at DESC);

CREATE TABLE IF NOT EXISTS heartbeats (
  agent_id              TEXT PRIMARY KEY REFERENCES agents(id) ON DELETE CASCADE,
  status                TEXT NOT NULL,             -- online|offline|degraded|unknown
  last_check_at         TEXT NOT NULL,
  detail_json           TEXT,
  consecutive_failures  INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS audit_log (
  id              INTEGER PRIMARY KEY AUTOINCREMENT,
  ts              TEXT NOT NULL DEFAULT (datetime('now')),
  actor           TEXT,
  action          TEXT NOT NULL,
  target          TEXT,
  params_json     TEXT,
  result          TEXT,
  ip              TEXT,
  user_agent      TEXT
);
CREATE INDEX IF NOT EXISTS idx_audit_ts     ON audit_log(ts DESC);
CREATE INDEX IF NOT EXISTS idx_audit_actor  ON audit_log(actor, ts DESC);

CREATE TABLE IF NOT EXISTS kv_store (
  k              TEXT PRIMARY KEY,
  v              TEXT,
  updated_at     TEXT NOT NULL DEFAULT (datetime('now'))
);

-- ============================================================
-- v2.0 tables (Chief on VPS + Kednet-агент через WS)
-- ALTER TABLE statements are in src/db/migrate.js (idempotent guards).
-- ============================================================

-- Kednet-агент: singleton connection row
CREATE TABLE IF NOT EXISTS kednet_agent (
  id                      INTEGER PRIMARY KEY CHECK (id=1),
  hostname                TEXT,
  os                      TEXT,
  version                 TEXT,
  skills_detected_json    TEXT,                       -- JSON array
  connected               INTEGER NOT NULL DEFAULT 0,
  connected_at            TEXT,
  last_heartbeat_at       TEXT,
  last_error              TEXT
);

-- Approvals: pending TG-push state
CREATE TABLE IF NOT EXISTS approvals (
  job_id            TEXT PRIMARY KEY REFERENCES jobs(id) ON DELETE CASCADE,
  artifact_count    INTEGER NOT NULL DEFAULT 0,
  tg_message_id     INTEGER,
  tg_chat_id        TEXT,
  reminder_count    INTEGER NOT NULL DEFAULT 0,
  created_at        TEXT NOT NULL DEFAULT (datetime('now'))
);

-- TG commands log (slash /start /status /cancel etc.)
CREATE TABLE IF NOT EXISTS tg_commands (
  id              INTEGER PRIMARY KEY AUTOINCREMENT,
  ts              TEXT NOT NULL DEFAULT (datetime('now')),
  chat_id         TEXT,
  user_id         TEXT,
  command         TEXT,
  args_json       TEXT,
  response        TEXT
);
CREATE INDEX IF NOT EXISTS idx_tg_commands_ts ON tg_commands(ts DESC);

-- v2.0 ALTERs (idempotent guards in migrate.js). These columns extend jobs.
-- DO NOT run them inline here: SQLite ALTER is fine, but they must run BEFORE
-- we mark schema_version=2.0. Schema file must remain order-stable for CREATE TABLE IF NOT EXISTS.

-- (no DDL here — see migrate.js MIGRATIONS['2.0'].run())
