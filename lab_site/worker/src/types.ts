/**
 * Env — тип окружения для Hono.
 *
 * Содержит и Cloudflare-привязки (для dev в воркере), и Node-поля (для VPS).
 * На Cloudflare Workers `LAB_KV` приходит как `KVNamespace`.
 * На VPS `LAB_KV` создаётся вручную в `server.ts` через `new KvCompat()`,
 * и runtime API совместим (см. kv-sqlite.ts).
 *
 * NB: тип LAB_KV = `any`, потому что сигнатуры `KVNamespace` (Cloudflare) и
 * `KvCompat` (наш) немного отличаются (overload на .get()), хотя runtime
 * идентичен. На тайпчек это влияет только в IDE, не в рантайме.
 */
export interface Env {
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  LAB_KV: any; // KVNamespace | KvCompat

  // Vars (wrangler.toml [vars] / .env файл на VPS)
  ENVIRONMENT: string;
  FRONTEND_ORIGIN: string;
  JWT_SECRET_DEV: string;

  // Secrets (через `wrangler secret put` ИЛИ через .env на VPS)
  JWT_SECRET?: string;
  // SMTP (Яндекс 360)
  SMTP_HOST?: string;
  SMTP_PORT?: string;
  SMTP_USER?: string;
  SMTP_PASS?: string;
  EMAIL_FROM?: string;
  YOOKASSA_SHOP_ID?: string;
  YOOKASSA_SECRET_KEY?: string;
  YOOKASSA_WEBHOOK_SECRET?: string;
  PYTHON_SERVICE_URL?: string;
  PYTHON_SERVICE_TOKEN?: string;

  // Publisher (Фаза 5+) — VK и Telegram
  VK_GROUP_TOKEN?: string;
  VK_GROUP_ID?: string;
  TELEGRAM_BOT_TOKEN?: string;
  TELEGRAM_ADMIN_ID?: string;
  TELEGRAM_CHANNEL_ID?: string;
  /** SOCKS5/HTTP proxy для исходящих запросов к api.telegram.org (нужен на VPS в РФ). */
  TELEGRAM_PROXY_URL?: string;

  // UniSender (email-рассылка подписчикам newsletter)
  UNISENDER_API_KEY?: string;
  UNISENDER_LIST_ID?: string;

  // Admin (защита эндпоинтов модерации: GET /api/experiments, PATCH/DELETE)
  ADMIN_TOKEN?: string;
}

/**
 * Набор CORS-источников для development и production.
 *
 * FRONTEND_ORIGIN может быть:
 *  - одной строкой: `https://app.pulab.online` (старый формат, обратная совместимость)
 *  - CSV: `https://app.pulab.online,https://app.pulab.ru` (новый формат после миграции)
 *
 * В dev добавляется http://127.0.0.1:4321 и http://localhost:4321 автоматически.
 */
export function corsOrigins(env: Env): Set<string> {
  const set = new Set<string>();
  for (const raw of (env.FRONTEND_ORIGIN ?? '').split(',')) {
    const o = raw.trim();
    if (o) set.add(o);
  }
  if (env.ENVIRONMENT !== 'production') {
    set.add('http://127.0.0.1:4321');
    set.add('http://localhost:4321');
  }
  return set;
}

/**
 * Legacy-обёртка для обратной совместимости: возвращает основной origin.
 */
export function corsOrigin(env: Env): string {
  return (env.FRONTEND_ORIGIN ?? '').split(',')[0]?.trim() ?? '';
}

/**
 * Утилита для типизированного ответа.
 */
export function json<T>(data: T, status = 200): Response {
  return new Response(JSON.stringify(data), {
    status,
    headers: { 'Content-Type': 'application/json; charset=utf-8' },
  });
}

export function error(code: string, message: string, status: number, extra?: Record<string, unknown>): Response {
  return json({ error: code, message, ...extra }, status);
}
