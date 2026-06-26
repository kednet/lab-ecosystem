import type { KVNamespace } from '@cloudflare/workers-types';

/**
 * Типизированный клиент над Cloudflare KV.
 * Все ключи — в одном месте, чтобы избежать опечаток.
 */
export const KV_KEYS = {
  authCode: (email: string) => `auth:code:${email.toLowerCase()}`,
  authUser: (email: string) => `auth:user:${email.toLowerCase()}`,
  // Трекер (Фаза 2)
  trackerWishes: (userId: string) => `tracker:wishes:${userId}`,
  // Генерации (Фаза 3)
  job: (jobId: string) => `job:${jobId}`,
  /** Индекс "job'ы пользователя" для листинга в /generate/jobs */
  jobUser: (userId: string, jobId: string) => `job:user:${userId}:${jobId}`,
  genMonth: (userId: string, ym: string) => `gen:month:${userId}:${ym}`,
  genDay: (userId: string, ymd: string) => `gen:day:${userId}:${ymd}`,
  // Книги (Фаза 3) — без R2
  book: (slug: string) => `book:${slug}`,
  bookFile: (slug: string, name: string) => `book:${slug}:file:${name}`,
  // Email-индекс по userId (для cron)
  userIdToEmail: (userId: string) => `userid:${userId}`,

  // Publisher (Фаза 5+) — состояние публикации и соцсети
  publish: (kind: string, slug: string) => `publish:${kind}:${slug}`,
  publishDryRun: (kind: string, slug: string) => `publish:dry-run:${kind}:${slug}`,
  socialVk: (slug: string) => `social:vk:${slug}`,
  socialTg: (slug: string) => `social:tg:${slug}`,

  // Newsletter (рассылка мини-практик)
  subscribeEmail: (email: string) => `subscribe:email:${email.toLowerCase()}`,
  subscribeRlIp: (ip: string) => `rl:subscribe:ip:${ip}`,
  subscribeRlEmail: (email: string) => `rl:subscribe:email:${email.toLowerCase()}`,
} as const;

/**
 * UserId = SHA-256(email) в hex.
 * Делаем из email стабильный opaque ID, чтобы:
 * 1) Не светить email в логах.
 * 2) Использовать как часть JWT-claim и KV-ключа.
 */
export async function userIdFromEmail(email: string): Promise<string> {
  const data = new TextEncoder().encode(email.toLowerCase().trim());
  const hash = await crypto.subtle.digest('SHA-256', data);
  return Array.from(new Uint8Array(hash))
    .map((b) => b.toString(16).padStart(2, '0'))
    .join('');
}

export interface AuthUser {
  email: string;
  userId: string;
  createdAt: string;
  // Подписка
  plan: 'free' | 'month' | 'half' | 'year';
  subscriptionStatus: 'none' | 'active' | 'expired' | 'canceled';
  subscriptionExpiresAt: string | null;
  // Квоты
  generationsLimit: number;
  wishesLimit: number;
}

export const DEFAULT_FREE_TIER: Pick<AuthUser, 'plan' | 'subscriptionStatus' | 'subscriptionExpiresAt' | 'generationsLimit' | 'wishesLimit'> = {
  plan: 'free',
  subscriptionStatus: 'none',
  subscriptionExpiresAt: null,
  generationsLimit: 3,
  wishesLimit: 3,
};

export async function getAuthUser(kv: KVNamespace, email: string): Promise<AuthUser | null> {
  const raw = await kv.get(KV_KEYS.authUser(email));
  if (!raw) return null;
  return JSON.parse(raw) as AuthUser;
}

export async function setAuthUser(kv: KVNamespace, user: AuthUser): Promise<void> {
  await kv.put(KV_KEYS.authUser(user.email), JSON.stringify(user));
}

export async function ensureAuthUser(kv: KVNamespace, email: string): Promise<AuthUser> {
  const existing = await getAuthUser(kv, email);
  if (existing) return existing;
  const userId = await userIdFromEmail(email);
  const now = new Date().toISOString();
  const fresh: AuthUser = {
    email: email.toLowerCase().trim(),
    userId,
    createdAt: now,
    ...DEFAULT_FREE_TIER,
  };
  await setAuthUser(kv, fresh);
  // Индекс для cron (поиск по userId → email)
  await kv.put(KV_KEYS.userIdToEmail(userId), fresh.email);
  return fresh;
}

// ────────────────────────────────────────────────
// Коды подтверждения (TTL 10 мин)
// ────────────────────────────────────────────────
export interface AuthCode {
  code: string;
  email: string;
  expiresAt: number; // epoch ms
  attempts: number;
}

export async function setAuthCode(kv: KVNamespace, email: string, code: string): Promise<AuthCode> {
  const payload: AuthCode = {
    code,
    email: email.toLowerCase().trim(),
    expiresAt: Date.now() + 10 * 60 * 1000,
    attempts: 0,
  };
  // TTL в секундах
  await kv.put(KV_KEYS.authCode(payload.email), JSON.stringify(payload), {
    expirationTtl: 10 * 60,
  });
  return payload;
}

export async function getAuthCode(kv: KVNamespace, email: string): Promise<AuthCode | null> {
  const raw = await kv.get(KV_KEYS.authCode(email));
  if (!raw) return null;
  return JSON.parse(raw) as AuthCode;
}

export async function deleteAuthCode(kv: KVNamespace, email: string): Promise<void> {
  await kv.delete(KV_KEYS.authCode(email));
}

/**
 * Простая защита от брутфорса: максимум 5 попыток на код.
 */
export async function recordFailedAttempt(kv: KVNamespace, email: string): Promise<AuthCode | null> {
  const code = await getAuthCode(kv, email);
  if (!code) return null;
  code.attempts += 1;
  if (code.attempts >= 5) {
    await deleteAuthCode(kv, email);
    return null;
  }
  await kv.put(KV_KEYS.authCode(email), JSON.stringify(code), {
    expirationTtl: Math.max(60, Math.floor((code.expiresAt - Date.now()) / 1000)),
  });
  return code;
}

// ────────────────────────────────────────────────
// Лимиты генераций
// ────────────────────────────────────────────────
export async function incrementGenerationCount(kv: KVNamespace, userId: string): Promise<{ month: number; day: number }> {
  const now = new Date();
  const ym = `${now.getUTCFullYear()}-${String(now.getUTCMonth() + 1).padStart(2, '0')}`;
  const ymd = `${ym}-${String(now.getUTCDate()).padStart(2, '0')}`;

  const [monthRaw, dayRaw] = await Promise.all([
    kv.get(KV_KEYS.genMonth(userId, ym)),
    kv.get(KV_KEYS.genDay(userId, ymd)),
  ]);

  const month = parseInt(monthRaw ?? '0', 10) + 1;
  const day = parseInt(dayRaw ?? '0', 10) + 1;

  // 30 дней для месячного, 2 дня для дневного (с запасом)
  await kv.put(KV_KEYS.genMonth(userId, ym), String(month), { expirationTtl: 35 * 24 * 60 * 60 });
  await kv.put(KV_KEYS.genDay(userId, ymd), String(day), { expirationTtl: 3 * 24 * 60 * 60 });

  return { month, day };
}

export async function getGenerationCounts(kv: KVNamespace, userId: string): Promise<{ month: number; day: number }> {
  const now = new Date();
  const ym = `${now.getUTCFullYear()}-${String(now.getUTCMonth() + 1).padStart(2, '0')}`;
  const ymd = `${ym}-${String(now.getUTCDate()).padStart(2, '0')}`;

  const [monthRaw, dayRaw] = await Promise.all([
    kv.get(KV_KEYS.genMonth(userId, ym)),
    kv.get(KV_KEYS.genDay(userId, ymd)),
  ]);

  return {
    month: parseInt(monthRaw ?? '0', 10),
    day: parseInt(dayRaw ?? '0', 10),
  };
}
