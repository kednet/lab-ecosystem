/**
 * worker/src/server.ts
 *
 * Node.js-адаптер для Hono-приложения из index-assets.ts.
 *
 * Используется ТОЛЬКО на VPS Reg.ru (production self-hosted).
 * Для Cloudflare Workers по-прежнему работает `wrangler deploy` (index.ts).
 *
 * Что делает:
 *   1. Поднимает HTTP-сервер на 127.0.0.1:8787 (через @hono/node-server).
 *   2. Собирает c.env из process.env.
 *   3. Подсовывает c.env.LAB_KV = новый KvCompat() (SQLite-обёртка).
 *   4. Логирует запросы в stdout в JSON (journald-friendly).
 *
 * Запуск:
 *   node --env-file=.env dist/server.js
 * или
 *   pm2 start dist/server.js --name lab-api
 *
 * Переменные окружения (см. deploy/lab-api.env.example):
 *   ENVIRONMENT, FRONTEND_ORIGIN, JWT_SECRET, JWT_SECRET_DEV, SQLITE_PATH,
 *   SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASS, EMAIL_FROM,
 *   PYTHON_SERVICE_URL, PYTHON_SERVICE_TOKEN,
 *   VK_GROUP_TOKEN, VK_GROUP_ID,
 *   TELEGRAM_BOT_TOKEN, TELEGRAM_ADMIN_ID, TELEGRAM_CHANNEL_ID,
 *   YOOKASSA_SHOP_ID, YOOKASSA_SECRET_KEY, YOOKASSA_WEBHOOK_SECRET,
 *   PORT, HOST
 */
import { serve } from '@hono/node-server';
import { Hono } from 'hono';
import app from './index-assets';
import { KvCompat } from './lib/kv-sqlite';
import type { Env } from './types';

// ────────────────────────────────────────────────
// Сборка c.env из process.env (один раз при старте)
// ────────────────────────────────────────────────
const globalEnv: Env = {
  LAB_KV: new KvCompat(),

  ENVIRONMENT: process.env.ENVIRONMENT || 'development',
  FRONTEND_ORIGIN: process.env.FRONTEND_ORIGIN || 'http://127.0.0.1:4321',
  JWT_SECRET_DEV: process.env.JWT_SECRET_DEV || 'dev-secret-change-me',

  JWT_SECRET: process.env.JWT_SECRET,
  SMTP_HOST: process.env.SMTP_HOST,
  SMTP_PORT: process.env.SMTP_PORT,
  SMTP_USER: process.env.SMTP_USER,
  SMTP_PASS: process.env.SMTP_PASS,
  EMAIL_FROM: process.env.EMAIL_FROM,
  YOOKASSA_SHOP_ID: process.env.YOOKASSA_SHOP_ID,
  YOOKASSA_SECRET_KEY: process.env.YOOKASSA_SECRET_KEY,
  YOOKASSA_WEBHOOK_SECRET: process.env.YOOKASSA_WEBHOOK_SECRET,
  PYTHON_SERVICE_URL: process.env.PYTHON_SERVICE_URL,
  PYTHON_SERVICE_TOKEN: process.env.PYTHON_SERVICE_TOKEN,

  VK_GROUP_TOKEN: process.env.VK_GROUP_TOKEN,
  VK_GROUP_ID: process.env.VK_GROUP_ID,
  TELEGRAM_BOT_TOKEN: process.env.TELEGRAM_BOT_TOKEN,
  TELEGRAM_ADMIN_ID: process.env.TELEGRAM_ADMIN_ID,
  TELEGRAM_CHANNEL_ID: process.env.TELEGRAM_CHANNEL_ID,
  TELEGRAM_PROXY_URL: process.env.TELEGRAM_PROXY_URL,

  UNISENDER_API_KEY: process.env.UNISENDER_API_KEY,
  UNISENDER_LIST_ID: process.env.UNISENDER_LIST_ID,

  ADMIN_TOKEN: process.env.ADMIN_TOKEN,
};

// Sanity: предупреждаем, если забыли prod-секрет
if (globalEnv.ENVIRONMENT === 'production' && !process.env.JWT_SECRET) {
  process.stderr.write(
    '[lab-api] WARNING: JWT_SECRET is not set in production! ' +
    'Falling back to JWT_SECRET_DEV (insecure).\n',
  );
}

// ────────────────────────────────────────────────
// Wrapper: инжектит env в c.env + логирует запросы
// ────────────────────────────────────────────────
const wrapper = new Hono<{ Bindings: Env }>();

// 1) Инжект env (Hono на Node не имеет c.env по умолчанию)
wrapper.use('*', async (c, next) => {
  // c.env в Hono — это ContextualEnvironment; можно присваивать
  (c as any).env = globalEnv;
  await next();
});

// 2) Логгер запросов (после обработки, со статусом и временем)
wrapper.use('*', async (c, next) => {
  const t0 = Date.now();
  await next();
  const path = c.req.path;
  // Пропускаем health-check (часто дёргается мониторингом)
  if (path === '/health') return;
  const entry = {
    t: new Date().toISOString(),
    method: c.req.method,
    path,
    status: c.res.status,
    ms: Date.now() - t0,
  };
  process.stdout.write(JSON.stringify(entry) + '\n');
});

// 3) Монтируем основной app
wrapper.route('/', app);

// ────────────────────────────────────────────────
// Запуск HTTP-сервера
// ────────────────────────────────────────────────
const port = parseInt(process.env.PORT || '8787', 10);
const host = process.env.HOST || '127.0.0.1';

const server = serve(
  {
    fetch: wrapper.fetch,
    port,
    hostname: host,
  },
  (info) => {
    process.stdout.write(
      `[lab-api] listening on http://${info.address}:${info.port} (env=${globalEnv.ENVIRONMENT})\n`,
    );
  },
);

// ────────────────────────────────────────────────
// Graceful shutdown
// ────────────────────────────────────────────────
function shutdown(signal: string) {
  process.stdout.write(`[lab-api] received ${signal}, closing...\n`);
  server.close(() => {
    process.stdout.write('[lab-api] closed cleanly\n');
    process.exit(0);
  });
  setTimeout(() => {
    process.stderr.write('[lab-api] forced exit after 10s\n');
    process.exit(1);
  }, 10_000).unref();
}

process.on('SIGTERM', () => shutdown('SIGTERM'));
process.on('SIGINT', () => shutdown('SIGINT'));
process.on('uncaughtException', (err) => {
  process.stderr.write(`[lab-api] uncaughtException: ${err.stack || err.message}\n`);
});
process.on('unhandledRejection', (reason) => {
  process.stderr.write(`[lab-api] unhandledRejection: ${reason}\n`);
});
