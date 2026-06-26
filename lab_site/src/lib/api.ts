/**
 * Клиент к Cloudflare Worker API.
 * Базовый URL берётся из window.LAB_API_URL (задан в <head> Base.astro)
 * или дефолтного для dev.
 */

declare global {
  interface Window {
    LAB_API_URL?: string;
  }
}

function getBaseUrl(): string {
  if (typeof window !== 'undefined' && window.LAB_API_URL) return window.LAB_API_URL;
  return 'https://api.pulab.ru';
}

export class ApiError extends Error {
  status: number;
  code: string;
  extra?: Record<string, unknown>;
  constructor(status: number, code: string, message: string, extra?: Record<string, unknown>) {
    super(message);
    this.status = status;
    this.code = code;
    this.extra = extra;
  }
}

interface FetchOptions {
  method?: 'GET' | 'POST' | 'PATCH' | 'DELETE';
  body?: unknown;
  token?: string | null;
  signal?: AbortSignal;
}

export async function apiFetch<T>(path: string, opts: FetchOptions = {}): Promise<T> {
  const url = `${getBaseUrl()}${path}`;
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
  };
  if (opts.token) headers['Authorization'] = `Bearer ${opts.token}`;

  const res = await fetch(url, {
    method: opts.method ?? 'GET',
    headers,
    body: opts.body ? JSON.stringify(opts.body) : undefined,
    signal: opts.signal,
  });

  // Пытаемся распарсить JSON даже при ошибке
  let data: unknown = null;
  const text = await res.text();
  if (text) {
    try { data = JSON.parse(text); } catch { /* не JSON */ }
  }

  if (!res.ok) {
    const err = data as { error?: string; message?: string } | null;
    throw new ApiError(
      res.status,
      err?.error ?? 'unknown_error',
      err?.message ?? `HTTP ${res.status}`,
      data as Record<string, unknown> | undefined,
    );
  }

  return data as T;
}

// ────────────────────────────────────────────────
// Типизированные API-методы
// ────────────────────────────────────────────────

export interface UserData {
  email: string;
  userId: string;
  /**
   * 'free'   — бесплатный тариф (без подписки)
   * 'month'  — месячная подписка (590 ₽/мес)
   * 'half'   — подписка на полгода (2 990 ₽/6 мес), экономия 15%
   * 'year'   — годовая подписка (5 900 ₽/год), экономия 17%
   */
  plan: 'free' | 'month' | 'half' | 'year';
  subscriptionStatus: 'none' | 'active' | 'expired' | 'canceled';
  subscriptionExpiresAt: string | null;
  generationsLimit: number;
  wishesLimit: number;
}

export interface MeResponse {
  user: UserData;
  generations: {
    usedThisMonth: number;
    usedToday: number;
    limitThisMonth: number;
    limitPerDay: number;
  };
}

export const authApi = {
  requestCode(email: string): Promise<{ ok: boolean; devCode?: string; expiresInSec: number }> {
    return apiFetch('/auth/code', { method: 'POST', body: { email } });
  },
  verify(email: string, code: string): Promise<{ ok: boolean; token: string; user: UserData }> {
    return apiFetch('/auth/verify', { method: 'POST', body: { email, code } });
  },
  me(token: string): Promise<MeResponse> {
    return apiFetch('/auth/me', { token });
  },
  logout(token: string): Promise<{ ok: boolean }> {
    return apiFetch('/auth/logout', { method: 'POST', token });
  },
};

// ────────────────────────────────────────────────
// Tracker
// ────────────────────────────────────────────────

export interface WishStep {
  id: string;
  text: string;
  done: boolean;
  doneAt?: string;
}

export interface Wish {
  id: string;
  title: string;
  description?: string;
  steps: WishStep[];
  createdAt: string;
  updatedAt: string;
  archivedAt?: string;
}

export interface WishQuota {
  active: number;
  limit: number;
  remaining: number;
  plan: 'free' | 'month' | 'half' | 'year';
}

export interface WishesResponse {
  wishes: Wish[];
  quota: WishQuota;
}

export const trackerApi = {
  list(token: string): Promise<WishesResponse> {
    return apiFetch('/tracker/wishes', { token });
  },
  create(token: string, data: { title: string; description?: string; steps?: { text: string }[] }): Promise<{ ok: boolean; wish: Wish }> {
    return apiFetch('/tracker/wishes', { method: 'POST', body: data, token });
  },
  update(token: string, id: string, data: Partial<{ title: string; description: string; steps: WishStep[]; archived: boolean }>): Promise<{ ok: boolean; wish: Wish }> {
    return apiFetch(`/tracker/wishes/${id}`, { method: 'PATCH', body: data, token });
  },
  remove(token: string, id: string): Promise<{ ok: boolean; removedId: string }> {
    return apiFetch(`/tracker/wishes/${id}`, { method: 'DELETE', token });
  },
  toggleStep(token: string, id: string, stepId: string, done: boolean): Promise<{ ok: boolean; wish: Wish }> {
    return apiFetch(`/tracker/wishes/${id}/toggle`, { method: 'POST', body: { stepId, done }, token });
  },
};
