/**
 * unisender.ts — минимальный клиент UniSender API v3.
 *
 * Использует только два эндпоинта:
 *   - POST /ru/api/subscribe  — добавление email в список (с double opt-in)
 *   - POST /ru/api/unsubscribe — отписка
 *
 * ВАЖНО: UniSender принимает `api_key` в form-data, не в заголовке.
 * На Cloudflare Workers access-логи не светят исходящие запросы, поэтому
 * api_key в теле запроса не утекает за пределы нашей инфраструктуры.
 *
 * Dev-режим: если UNISENDER_API_KEY не задан, функции возвращают
 * `{ ok: true, devMode: true }` — для локальной разработки без сети.
 */

export interface UnisenderEnv {
  UNISENDER_API_KEY?: string;
  UNISENDER_LIST_ID?: string;
}

export interface SubscribeParams {
  email: string;
  listId?: string;
  doubleOptin?: 0 | 1;
  extra?: Record<string, string>; // имя, телефон и т.п.
}

export interface UnisenderResult {
  ok: boolean;
  devMode?: boolean;
  status?: string;       // 'new' | 'updated' | 'confirmed' и т.п.
  error?: string;
  code?: string;          // 'invalid_email', 'rate_limit', 'auth', ...
}

const ENDPOINT = 'https://api.unisender.com/ru/api';

// Универсальный вызов POST с form-encoded телом.
// Cloudflare Workers fetch — не передаёт agent/tls-флаги; сертификаты CF проверяет сам.
async function call(
  env: UnisenderEnv,
  method: 'subscribe' | 'unsubscribe',
  params: Record<string, string>,
): Promise<UnisenderResult> {
  if (!env.UNISENDER_API_KEY) {
    console.log(`[unisender:dev] ${method}`, JSON.stringify(params));
    return { ok: true, devMode: true, status: 'dev' };
  }

  const body = new URLSearchParams({ api_key: env.UNISENDER_API_KEY, ...params });
  try {
    const resp = await fetch(`${ENDPOINT}/${method}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
      body: body.toString(),
    });
    const data = (await resp.json().catch(() => ({}))) as {
      result?: { status?: string };
      error?: string;
      code?: string;
    };

    if (!resp.ok || data.error) {
      // Популярные коды: 'invalid_email', 'unsubscribed', 'list_not_found', 'auth_failed'
      console.error(`[unisender:${method}:error]`, data.error, data.code);
      return { ok: false, error: data.error ?? 'unknown', code: data.code };
    }

    return { ok: true, status: data.result?.status };
  } catch (err) {
    const msg = err instanceof Error ? err.message : String(err);
    console.error(`[unisender:${method}:fetch_error]`, msg);
    return { ok: false, error: msg, code: 'network' };
  }
}

export async function subscribe(env: UnisenderEnv, p: SubscribeParams): Promise<UnisenderResult> {
  const listId = p.listId ?? env.UNISENDER_LIST_ID;
  if (!listId) {
    return { ok: false, error: 'UNISENDER_LIST_ID not configured', code: 'config' };
  }
  return call(env, 'subscribe', {
    list_ids: listId,
    'fields[email]': p.email,
    double_optin: String(p.doubleOptin ?? 0), // 0 = UniSender шлёт confirm-письмо (ответ поддержки 2026-06-21)
    overwrite: '2',                            // 2 = обновлять, не дублировать
    ...(p.extra ?? {}),
  });
}

export async function unsubscribe(env: UnisenderEnv, email: string, listId?: string): Promise<UnisenderResult> {
  const lid = listId ?? env.UNISENDER_LIST_ID;
  if (!lid) return { ok: false, error: 'UNISENDER_LIST_ID not configured', code: 'config' };
  return call(env, 'unsubscribe', {
    list_ids: lid,
    'fields[email]': email,
  });
}