/**
 * State-машина публикации для одной сущности (книга / эксперт).
 *
 * NEW → COPIES_GENERATED → VK_POSTED → TG_POSTED → NOTIFIED → PUBLISHED
 * + терминал FAILED (с error в state).
 *
 * Хранится в KV: `publish:{kind}:{slug}` (или `publish:dry-run:{kind}:{slug}` для dry-run).
 * TTL 30 дней — для истории и возможности "переотправить" или "отменить".
 */
import type { KVNamespace } from '@cloudflare/workers-types';
import { KV_KEYS } from './kv';

export type PublishKind = 'book' | 'expert';
export type PublishState =
  | 'NEW'
  | 'COPIES_GENERATED'
  | 'VK_POSTED'
  | 'TG_POSTED'
  | 'NOTIFIED'
  | 'PUBLISHED'
  | 'FAILED';

export interface VkPublishResult {
  post_id: number;
  owner_id?: number;
  url?: string;
  posted_at: string;
  status: 'pending_moderation' | 'published';
}

export interface TgPublishResult {
  message_id: number;
  chat_id: number | string;
  url?: string;
  posted_at: string;
}

export interface PublishRecord {
  kind: PublishKind;
  slug: string;
  state: PublishState;
  createdAt: string;
  updatedAt: string;
  copies?: {
    vk?: string;
    tg?: string;
    meta_description?: string;
    source?: 'ai' | 'fallback';
  };
  vk?: VkPublishResult;
  tg?: TgPublishResult;
  error?: string;
  /** Снимок "кто инициатор" — для аудита. */
  initiatedBy?: string;
  /** Метка dry-run, чтобы случайно не отправить живой пост. */
  dryRun: boolean;
}

const TTL_SECONDS = 30 * 24 * 60 * 60;

function key(kind: PublishKind, slug: string, dryRun: boolean): string {
  return dryRun
    ? KV_KEYS.publishDryRun(kind, slug)
    : KV_KEYS.publish(kind, slug);
}

export async function getPublish(
  kv: KVNamespace,
  kind: PublishKind,
  slug: string,
  dryRun = false,
): Promise<PublishRecord | null> {
  const raw = await kv.get(key(kind, slug, dryRun));
  if (!raw) return null;
  try {
    return JSON.parse(raw) as PublishRecord;
  } catch {
    return null;
  }
}

export async function savePublish(
  kv: KVNamespace,
  record: PublishRecord,
): Promise<void> {
  record.updatedAt = new Date().toISOString();
  await kv.put(key(record.kind, record.slug, record.dryRun), JSON.stringify(record), {
    expirationTtl: TTL_SECONDS,
  });
}

export async function createPublish(
  kv: KVNamespace,
  args: { kind: PublishKind; slug: string; initiatedBy?: string; dryRun?: boolean },
): Promise<PublishRecord> {
  const now = new Date().toISOString();
  const rec: PublishRecord = {
    kind: args.kind,
    slug: args.slug,
    state: 'NEW',
    createdAt: now,
    updatedAt: now,
    initiatedBy: args.initiatedBy,
    dryRun: args.dryRun ?? false,
  };
  await savePublish(kv, rec);
  return rec;
}

/**
 * Список всех "живых" publish-состояний (без dry-run).
 * Используется для дашборда / отчёта.
 */
export async function listPublishes(
  kv: KVNamespace,
  opts: { kind?: PublishKind; state?: PublishState; dryRun?: boolean; limit?: number } = {},
): Promise<PublishRecord[]> {
  const prefix = opts.dryRun ? 'publish:dry-run:' : 'publish:';
  const limit = Math.min(200, opts.limit ?? 100);
  const out: PublishRecord[] = [];
  const list = await kv.list({ prefix, limit });
  for (const k of list.keys) {
    const raw = await kv.get(k.name);
    if (!raw) continue;
    try {
      const rec = JSON.parse(raw) as PublishRecord;
      if (opts.kind && rec.kind !== opts.kind) continue;
      if (opts.state && rec.state !== opts.state) continue;
      out.push(rec);
      if (out.length >= limit) break;
    } catch {
      // skip corrupted
    }
  }
  return out;
}

/** Машина переходов: какие переходы разрешены. */
const TRANSITIONS: Record<PublishState, PublishState[]> = {
  NEW: ['COPIES_GENERATED', 'FAILED'],
  COPIES_GENERATED: ['VK_POSTED', 'FAILED'],
  VK_POSTED: ['TG_POSTED', 'FAILED'],
  TG_POSTED: ['NOTIFIED', 'FAILED'],
  NOTIFIED: ['PUBLISHED', 'FAILED'],
  PUBLISHED: ['FAILED'], // можно "откатить" вручную
  FAILED: ['NEW'], // можно перезапустить
};

export function canTransition(from: PublishState, to: PublishState): boolean {
  if (from === to) return true;
  return TRANSITIONS[from]?.includes(to) ?? false;
}

export async function transitionPublish(
  kv: KVNamespace,
  kind: PublishKind,
  slug: string,
  to: PublishState,
  patch: Partial<PublishRecord> = {},
  dryRun = false,
): Promise<PublishRecord> {
  const rec = await getPublish(kv, kind, slug, dryRun);
  if (!rec) {
    throw new Error(`Publish record ${kind}:${slug} не найден`);
  }
  if (!canTransition(rec.state, to)) {
    throw new Error(`Недопустимый переход ${rec.state} → ${to} для ${kind}:${slug}`);
  }
  Object.assign(rec, patch);
  rec.state = to; // ВАЖНО: присваиваем ПОСЛЕ Object.assign, чтобы patch.state не затёр
  await savePublish(kv, rec);
  return rec;
}
