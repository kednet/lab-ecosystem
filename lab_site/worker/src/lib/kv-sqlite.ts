/**
 * worker/src/lib/kv-sqlite.ts
 *
 * Drop-in замена Cloudflare KV для Node.js окружения (VPS Reg.ru).
 *
 * Реализует минимальное подмножество API, которое использует код воркера:
 *   - kv.get(key)                                    → string | null
 *   - kv.get(key, { type: 'arrayBuffer' })           → ArrayBuffer | null
 *   - kv.put(key, value, { expirationTtl?: number }) → void
 *   - kv.delete(key)                                 → void
 *   - kv.list({ prefix?, limit? })                   → { keys: { name: string }[] }
 *
 * Что НЕ реализовано (и не используется в проекте):
 *   - type: 'json' / 'stream' — нет вызовов
 *   - metadata в put/list — нет вызовов
 *   - getWithMetadata — нет вызовов
 *
 * Хранилище: SQLite через встроенный node:sqlite (Node 22.5+ / 23+ stable).
 * Файл по умолчанию /var/lib/lab-site/kv.db (настраивается через SQLITE_PATH).
 * TTL — lazy expiry: при get() записи с истёкшим exp игнорируются, при put() —
 * старые записи перезаписываются. Периодическая чистка — pruneExpired().
 *
 * Зачем SQLite, а не PostgreSQL:
 *   - Один файл → легко бэкапить (rsync), легко мониторить (`ls -la kv.db`)
 *   - На 2 ГБ RAM VPS PostgreSQL бы съел ~150 МБ впустую
 *   - Наш объём: ~10K ключей (auth, wishes, jobs, books), что SQLite щёлкает
 *   - Если проект вырастет → миграция на PG за 1 день
 *
 * Почему node:sqlite, а не better-sqlite3:
 *   - node:sqlite — встроенный, не нужна компиляция нативки
 *   - better-sqlite3 — топ по скорости, но требует node-gyp (сборка нативки)
 *   - На VPS Ubuntu 24.04 + Node 24 — node:sqlite работает «из коробки»
 */
import { DatabaseSync, StatementSync } from 'node:sqlite';
import path from 'node:path';
import fs from 'node:fs';

const DB_PATH = process.env.SQLITE_PATH || '/var/lib/lab-site/kv.db';

export interface KvKey {
  name: string;
  expiration?: number;
}
export interface KvListResult {
  keys: KvKey[];
  list_complete: boolean;
  cursor?: string;
}
export interface KvGetOptions {
  type?: 'text' | 'arrayBuffer' | 'json' | 'stream';
  cacheTtl?: number;
}
export interface KvPutOptions {
  expirationTtl?: number; // seconds
  expiration?: number;   // absolute epoch sec
  metadata?: unknown;
}

let _db: DatabaseSync | null = null;

function getDb(): DatabaseSync {
  if (_db) return _db;
  const dir = path.dirname(DB_PATH);
  fs.mkdirSync(dir, { recursive: true });
  _db = new DatabaseSync(DB_PATH);
  // WAL = много читателей + один писатель (идеально для web-сервера)
  _db.exec('PRAGMA journal_mode = WAL');
  _db.exec('PRAGMA synchronous = NORMAL');
  _db.exec(`
    CREATE TABLE IF NOT EXISTS kv (
      key   TEXT PRIMARY KEY,
      value TEXT NOT NULL,
      exp   INTEGER
    );
    CREATE INDEX IF NOT EXISTS kv_exp_idx ON kv(exp) WHERE exp IS NOT NULL;
  `);
  return _db;
}

/**
 * Совместимый клиент. Имя `KVNamespace` — для совместимости со старым кодом.
 * Реализует те же методы, что и Cloudflare KV (минимальное подмножество).
 */
export class KvCompat {
  private db: DatabaseSync;
  private stmtGet: StatementSync;
  private stmtDelete: StatementSync;
  private stmtUpsert: StatementSync;
  private stmtList: StatementSync;
  private stmtPrune: StatementSync;

  constructor(dbPath?: string) {
    if (dbPath) {
      const dir = path.dirname(dbPath);
      fs.mkdirSync(dir, { recursive: true });
      this.db = new DatabaseSync(dbPath);
    } else {
      this.db = getDb();
    }
    this.stmtGet = this.db.prepare('SELECT value, exp FROM kv WHERE key = ?');
    this.stmtDelete = this.db.prepare('DELETE FROM kv WHERE key = ?');
    this.stmtUpsert = this.db.prepare(
      `INSERT INTO kv (key, value, exp) VALUES (?, ?, ?)
       ON CONFLICT(key) DO UPDATE SET value = excluded.value, exp = excluded.exp`,
    );
    this.stmtList = this.db.prepare(
      `SELECT key FROM kv
       WHERE key LIKE ? ESCAPE '\\'
         AND (exp IS NULL OR exp > ?)
       ORDER BY key
       LIMIT ?`,
    );
    this.stmtPrune = this.db.prepare('DELETE FROM kv WHERE exp IS NOT NULL AND exp < ?');
  }

  async get(key: string, opts?: KvGetOptions): Promise<any> {
    const row = this.stmtGet.get(key) as { value: string; exp: number | null } | undefined;
    if (!row) return null;
    if (row.exp && row.exp < Date.now()) {
      this.stmtDelete.run(key);
      return null;
    }
    if (opts?.type === 'arrayBuffer') {
      // value хранится как base64
      const bin = Buffer.from(row.value, 'base64');
      return bin.buffer.slice(bin.byteOffset, bin.byteOffset + bin.byteLength);
    }
    if (opts?.type === 'json') {
      return JSON.parse(row.value);
    }
    return row.value; // string по умолчанию
  }

  async put(key: string, value: string | ArrayBuffer | Uint8Array, opts?: KvPutOptions): Promise<void> {
    let stored: string;
    if (typeof value === 'string') {
      stored = value;
    } else {
      const buf = value instanceof Uint8Array ? Buffer.from(value) : Buffer.from(value);
      stored = buf.toString('base64');
    }
    let exp: number | null = null;
    if (opts?.expirationTtl) {
      exp = Date.now() + opts.expirationTtl * 1000;
    } else if (opts?.expiration) {
      exp = opts.expiration * 1000;
    }
    this.stmtUpsert.run(key, stored, exp);
  }

  async delete(key: string): Promise<void> {
    this.stmtDelete.run(key);
  }

  async list(opts?: { prefix?: string; limit?: number; cursor?: string }): Promise<KvListResult> {
    const limit = Math.min(1000, opts?.limit ?? 1000);
    const prefix = opts?.prefix ?? '';
    const escaped = prefix.replace(/[\\%_]/g, (m) => '\\' + m);
    const rows = this.stmtList.all(escaped + '%', Date.now(), limit) as { key: string }[];
    return {
      keys: rows.map((r) => ({ name: r.key })),
      list_complete: rows.length < limit,
      cursor: undefined,
    };
  }

  /**
   * Заглушка: в коде проекта не используется, но требуется для совместимости
   * с типом KVNamespace. Возвращает значение + пустые metadata.
   */
  async getWithMetadata<T = unknown>(
    key: string,
    _type?: 'text' | 'arrayBuffer' | 'json' | 'stream',
  ): Promise<{ value: any; metadata: T | null }> {
    const value = await this.get(key, _type as any);
    return { value, metadata: null };
  }

  /**
   * Удалить все истёкшие записи. Запускать по cron раз в сутки.
   * Возвращает количество удалённых.
   */
  pruneExpired(): number {
    const r = this.stmtPrune.run(Date.now());
    return Number(r.changes ?? 0);
  }

  /**
   * Размер БД в байтах (для мониторинга).
   */
  size(): number {
    const r = this.db
      .prepare('SELECT page_count * page_size as s FROM pragma_page_count(), pragma_page_size()')
      .get() as { s: number };
    return Number(r.s);
  }
}

// ────────────────────────────────────────────────
// Type alias для совместимости
// ────────────────────────────────────────────────

/**
 * Старый код в роутах импортирует `KVNamespace` из @cloudflare/workers-types.
 * Runtime API идентичен. Если в каком-то файле нужен явный каст:
 *
 *   const kv: KVNamespace = new KvCompat() as unknown as KVNamespace;
 */
export type { KvCompat as KVNamespace };

/**
 * Фабрика для инжекта в Hono через c.env.
 */
export function makeKv(): KvCompat {
  return new KvCompat();
}
