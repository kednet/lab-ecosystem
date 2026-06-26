/**
 * Chief Agent — DB migrations.
 * Forward-only. On boot:
 *   1) runs schema.sql (CREATE TABLE IF NOT EXISTS — idempotent),
 *   2) applies incremental migrations from MIGRATIONS array.
 * Each migration is a small function so ALTER TABLE can be guarded
 * by column-existence checks (SQLite errors on duplicate ADD COLUMN).
 */
'use strict';

const fs = require('fs');
const path = require('path');
const db = require('./client');

const SCHEMA_PATH = path.join(__dirname, 'schema.sql');

function getAppliedVersion() {
  const row = db.prepare("SELECT v FROM kv_store WHERE k = 'schema_version'").get();
  return row ? parseInt(row.v, 10) : 0;
}

function setAppliedVersion(v) {
  db.prepare(`
    INSERT INTO kv_store (k, v, updated_at)
    VALUES ('schema_version', ?, datetime('now'))
    ON CONFLICT(k) DO UPDATE SET v = excluded.v, updated_at = excluded.updated_at
  `).run(String(v));
}

function hasColumn(table, col) {
  const cols = db.prepare(`PRAGMA table_info(${table})`).all();
  return cols.some(c => c.name === col);
}

function hasIndex(name) {
  const rows = db.prepare(`SELECT name FROM sqlite_master WHERE type='index' AND name=?`).all(name);
  return rows.length > 0;
}

/**
 * Incremental migrations. Each entry: { id, run() }.
 * run() is idempotent — safe to re-apply.
 *
 * v1.0 → v2.0: Chief на VPS + Kednet-агент через WS
 */
const MIGRATIONS = [
  {
    id: '2.0',
    run() {
      db.transaction(() => {
        if (!hasColumn('jobs', 'artifacts_json'))   db.exec(`ALTER TABLE jobs ADD COLUMN artifacts_json TEXT`);
        if (!hasColumn('jobs', 'approved_at'))      db.exec(`ALTER TABLE jobs ADD COLUMN approved_at TEXT`);
        if (!hasColumn('jobs', 'approved_by'))      db.exec(`ALTER TABLE jobs ADD COLUMN approved_by TEXT`);
        if (!hasColumn('jobs', 'rejected_at'))      db.exec(`ALTER TABLE jobs ADD COLUMN rejected_at TEXT`);
        if (!hasColumn('jobs', 'rejection_reason')) db.exec(`ALTER TABLE jobs ADD COLUMN rejection_reason TEXT`);
        if (!hasColumn('jobs', 'transport'))        db.exec(`ALTER TABLE jobs ADD COLUMN transport TEXT`);

        if (!hasIndex('idx_jobs_awaiting')) {
          db.exec(`CREATE INDEX idx_jobs_awaiting ON jobs(status, created_at DESC) WHERE status='awaiting_approval'`);
        }
      })();
    }
  }
];

function run() {
  // 1. Base schema (idempotent CREATE TABLE IF NOT EXISTS).
  const schemaSql = fs.readFileSync(SCHEMA_PATH, 'utf8');
  db.exec(schemaSql);
  // eslint-disable-next-line no-console
  console.log('[chief.db] schema.sql applied (idempotent)');

  // 2. Incremental migrations.
  const applied = getAppliedVersion();
  for (const m of MIGRATIONS) {
    if (parseFloat(m.id) <= applied) continue;
    m.run();
    setAppliedVersion(m.id);
    // eslint-disable-next-line no-console
    console.log('[chief.db] applied migration', m.id);
  }

  // 3. Self-heal: if kv_store says we're at 2.0 but jobs is missing v2 columns,
  //    the schema.sql was bumped before the ALTERs were run (legacy order bug).
  //    Detect this and re-run the v2.0 migration once.
  const appliedNow = getAppliedVersion();
  if (parseFloat(appliedNow) >= 2.0) {
    const needsTransport = !hasColumn('jobs', 'transport');
    if (needsTransport) {
      // eslint-disable-next-line no-console
      console.warn('[chief.db] self-heal: jobs.transport missing at schema_version=2.0, re-running v2.0 migration');
      const m = MIGRATIONS.find(x => x.id === '2.0');
      if (m) m.run();
    }
  }
}

module.exports = { run };
