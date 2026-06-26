/**
 * Chief Agent — SQLite client (better-sqlite3).
 * Synchronous, WAL-mode, single connection per process.
 *
 * Path: $CHIEF_DATA_DIR/chief.db (default /opt/chief-agent/data/chief.db)
 *       On local dev (no systemd), resolves to ./data/chief.db next to package.json.
 */
'use strict';

const path = require('path');
const fs = require('fs');
const Database = require('better-sqlite3');

const DATA_DIR = process.env.CHIEF_DATA_DIR
  || (process.env.NODE_ENV === 'production'
        ? '/opt/chief-agent/data'
        : path.join(__dirname, '..', '..', 'data'));

// Ensure data dir exists (idempotent)
if (!fs.existsSync(DATA_DIR)) {
  fs.mkdirSync(DATA_DIR, { recursive: true });
  // eslint-disable-next-line no-console
  console.log('[chief.db] Created data dir', DATA_DIR);
}

const DB_PATH = path.join(DATA_DIR, 'chief.db');
const db = new Database(DB_PATH);

// WAL = better concurrency for read-heavy workload (UI polls every 5s).
db.pragma('journal_mode = WAL');
db.pragma('synchronous = NORMAL');
db.pragma('foreign_keys = ON');
db.pragma('busy_timeout = 5000');

// eslint-disable-next-line no-console
console.log('[chief.db] Opened', DB_PATH);

module.exports = db;
module.exports.DATA_DIR = DATA_DIR;
