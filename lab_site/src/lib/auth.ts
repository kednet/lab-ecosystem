/**
 * Auth state на клиенте.
 * JWT хранится в localStorage. На каждой защищённой странице вызывается
 * `getAuth()` для проверки токена (и при необходимости обновления user-data).
 *
 * Нет сторов, нет React — простые функции + custom event для ре-рендера.
 */

import { authApi, type UserData, type MeResponse } from './api';

const TOKEN_KEY = 'lab_token';
const USER_KEY = 'lab_user';
const AUTH_EVENT = 'lab-auth-changed';

interface StoredAuth {
  token: string;
  user: UserData;
  cachedAt: number; // epoch ms
}

function readStored(): StoredAuth | null {
  if (typeof localStorage === 'undefined') return null;
  const token = localStorage.getItem(TOKEN_KEY);
  const userJson = localStorage.getItem(USER_KEY);
  if (!token || !userJson) return null;
  try {
    const user = JSON.parse(userJson) as UserData;
    return { token, user, cachedAt: 0 };
  } catch {
    return null;
  }
}

function writeStored(token: string, user: UserData): void {
  localStorage.setItem(TOKEN_KEY, token);
  localStorage.setItem(USER_KEY, JSON.stringify(user));
  window.dispatchEvent(new CustomEvent(AUTH_EVENT));
}

function clearStored(): void {
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(USER_KEY);
  window.dispatchEvent(new CustomEvent(AUTH_EVENT));
}

export function getToken(): string | null {
  if (typeof localStorage === 'undefined') return null;
  return localStorage.getItem(TOKEN_KEY);
}

export function getUser(): UserData | null {
  return readStored()?.user ?? null;
}

export function isAuthed(): boolean {
  return getToken() !== null;
}

/**
 * true, если у пользователя есть любая платная подписка (month / half / year).
 * Используется для гейтинга на /wish-map/ (доступ к конкурсу, безлимитные желания).
 */
export function isPremium(): boolean {
  const u = getUser();
  if (!u) return false;
  return u.plan === 'month' || u.plan === 'half' || u.plan === 'year';
}

export async function loginWithCode(email: string, code: string): Promise<UserData> {
  const { token, user } = await authApi.verify(email, code);
  writeStored(token, user);
  return user;
}

export async function requestCode(email: string): Promise<{ devCode?: string; expiresInSec: number }> {
  return authApi.requestCode(email);
}

export async function refreshMe(): Promise<UserData | null> {
  const token = getToken();
  if (!token) return null;
  try {
    const me: MeResponse = await authApi.me(token);
    const stored = readStored();
    if (stored) {
      stored.user = me.user;
      localStorage.setItem(USER_KEY, JSON.stringify(me.user));
      window.dispatchEvent(new CustomEvent(AUTH_EVENT));
    }
    return me.user;
  } catch (err) {
    if ((err as { status?: number }).status === 401) {
      clearStored();
    }
    return null;
  }
}

export function logout(): void {
  const token = getToken();
  if (token) authApi.logout(token).catch(() => {});
  clearStored();
}

export function onAuthChange(handler: () => void): () => void {
  window.addEventListener(AUTH_EVENT, handler);
  // Также слушаем storage event (для кросс-таб синхронизации)
  const storageHandler = (e: StorageEvent) => {
    if (e.key === TOKEN_KEY || e.key === USER_KEY) handler();
  };
  window.addEventListener('storage', storageHandler);
  return () => {
    window.removeEventListener(AUTH_EVENT, handler);
    window.removeEventListener('storage', storageHandler);
  };
}
