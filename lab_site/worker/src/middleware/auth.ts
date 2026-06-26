import type { Context, MiddlewareHandler } from 'hono';
import type { Env } from '../types';
import { verifyJWT, getJWTSecret } from '../lib/jwt';
import { getAuthUser } from '../lib/kv';
import type { AuthUser } from '../lib/kv';

declare module 'hono' {
  interface ContextVariableMap {
    user: AuthUser | null;
    userId: string | null;
    email: string | null;
  }
}

/**
 * Опциональная авторизация: если токен есть — кладёт user в c.var, иначе null.
 * Не падает на отсутствии токена — это делает `requireAuth`.
 */
export const optionalAuth: MiddlewareHandler<{ Bindings: Env }> = async (c, next) => {
  const auth = c.req.header('Authorization');
  if (!auth?.startsWith('Bearer ')) {
    c.set('user', null);
    c.set('userId', null);
    c.set('email', null);
    await next();
    return;
  }

  const token = auth.slice('Bearer '.length).trim();
  try {
    const payload = await verifyJWT(token, getJWTSecret(c.env));
    if (!payload) throw new Error('invalid token');
    const user = await getAuthUser(c.env.LAB_KV, payload.email);
    if (!user) throw new Error('user not found');
    c.set('user', user);
    c.set('userId', user.userId);
    c.set('email', user.email);
  } catch (err) {
    console.warn('[auth] invalid token', err);
    c.set('user', null);
    c.set('userId', null);
    c.set('email', null);
  }
  await next();
};

/**
 * Строгая авторизация: возвращает 401, если токена нет или он невалиден.
 * Использовать для всех защищённых эндпоинтов.
 */
export const requireAuth: MiddlewareHandler<{ Bindings: Env }> = async (c, next) => {
  const user = c.get('user');
  if (!user) {
    return c.json({ error: 'unauthorized', message: 'Нужен вход по email' }, 401);
  }
  await next();
};
