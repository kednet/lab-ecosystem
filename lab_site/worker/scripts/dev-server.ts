/**
 * Smoke-test сервер для Publisher.
 *
 * Запускает те же роуты (social, notifications) через @hono/node-server,
 * чтобы можно было прогнать пайплайн без wrangler-dev (который глючит в Windows).
 *
 * Запуск: npx tsx scripts/dev-server.ts
 */
import { serve } from '@hono/node-server';
import { Hono } from 'hono';
import { cors } from 'hono/cors';
import { corsHeaders, applyCors } from '../src/middleware/cors';
import { optionalAuth } from '../src/middleware/auth';
import authRoutes from '../src/routes/auth';
import trackerRoutes from '../src/routes/tracker';
import generateRoutes from '../src/routes/generate';
import internalRoutes, { publicBooksRouter } from '../src/routes/internal';
import socialRoutes from '../src/routes/social';
import notificationsRoutes from '../src/routes/notifications';
import type { Env } from '../src/types';

// Простой mock для LAB_KV
const kvStore = new Map<string, string>();
const mockKV = {
  get: async (key: string) => kvStore.get(key) ?? null,
  put: async (key: string, value: string, opts?: { expirationTtl?: number }) => {
    kvStore.set(key, value);
  },
  delete: async (key: string) => {
    kvStore.delete(key);
  },
  list: async ({ prefix }: { prefix: string }) => {
    const keys = [...kvStore.keys()].filter((k) => k.startsWith(prefix));
    return { keys: keys.map((name) => ({ name })) };
  },
};

const env: Env = {
  LAB_KV: mockKV as any,
  ENVIRONMENT: 'development',
  FRONTEND_ORIGIN: process.env.FRONTEND_ORIGIN ?? 'http://127.0.0.1:4321',
  JWT_SECRET_DEV: 'dev-secret-change-me-in-production-please-make-it-long-and-random',
  JWT_SECRET: 'dev-jwt-secret',
  PYTHON_SERVICE_URL: process.env.PYTHON_SERVICE_URL ?? 'http://127.0.0.1:8790',
  PYTHON_SERVICE_TOKEN: process.env.PYTHON_SERVICE_TOKEN ?? 'dev-token-change-me',
  // Publisher (без токенов → dev-mode)
  VK_GROUP_TOKEN: undefined,
  VK_GROUP_ID: undefined,
  TELEGRAM_BOT_TOKEN: undefined,
  TELEGRAM_ADMIN_ID: undefined,
  TELEGRAM_CHANNEL_ID: undefined,
};

const app = new Hono<{ Bindings: Env }>();

app.onError((err, c) => {
  console.error('[error]', err.message, err.stack);
  return c.json({ error: 'internal_error', message: err.message }, 500);
});

app.use('*', async (c, next) => {
  // Подменяем env
  Object.assign(c.env, env);
  await next();
});

app.route('/', socialRoutes);
app.route('/', notificationsRoutes);

const port = parseInt(process.env.PORT ?? '8800', 10);
console.log(`[dev-server] starting on http://127.0.0.1:${port}`);
console.log(`[dev-server] KV mock state: ${kvStore.size} keys`);

serve({ fetch: app.fetch, port });
