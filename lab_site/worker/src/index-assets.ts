/**
 * worker/src/index-assets.ts
 *
 * Универсальный Hono app: работает и на Cloudflare Workers, и на Node.js.
 *
 * С Cloudflare-варианта (`index-assets.ts` — "assets" = static из KV) убрана
 * логика отдачи статики, потому что на VPS её отдаёт Nginx.
 *
 * С KV — единый интерфейс: на Cloudflare это `KVNamespace`, на Node —
 * `KvCompat` (см. lib/kv-sqlite.ts). Все роуты используют `c.env.LAB_KV`
 * без изменений.
 */
import { Hono } from 'hono';
import type { Env } from './types';
import { corsHeaders, applyCors } from './middleware/cors';
import { optionalAuth } from './middleware/auth';
import authRoutes from './routes/auth';
import trackerRoutes from './routes/tracker';
import generateRoutes from './routes/generate';
import internalRoutes, { publicBooksRouter } from './routes/internal';
import socialRoutes from './routes/social';
import notificationsRoutes from './routes/notifications';
import subscribeRoutes from './routes/subscribe';
import payRoutes from './routes/pay';
import experimentsRoutes from './routes/experiments';

const app = new Hono<{ Bindings: Env }>();

// Глобальный обработчик ошибок
app.onError((err, c) => {
  console.error('[worker-error]', err.message, err.stack);
  return c.json({ error: 'internal_error', message: 'Что-то пошло не так' }, 500);
});

app.notFound((c) => c.json({ error: 'not_found', message: 'Роут не найден' }, 404));

// ────────────────────────────────────────────────
// Middleware: auth → CORS
// ────────────────────────────────────────────────
app.use('*', optionalAuth);

app.use('*', async (c, next) => {
  if (c.req.method === 'OPTIONS') {
    return new Response(null, { status: 204, headers: corsHeaders(c.env, c.req.raw) });
  }
  await next();
  return applyCors(c.res, c.env, c.req.raw);
});

// ────────────────────────────────────────────────
// Базовые роуты
// ────────────────────────────────────────────────
app.get('/health', (c) => {
  return c.json({
    status: 'ok',
    environment: c.env.ENVIRONMENT,
    timestamp: new Date().toISOString(),
    version: '0.6.0',
  });
});

app.get('/api', (c) => {
  return c.json({
    name: 'lab-site-api',
    docs: 'https://app.pulab.online',
    version: '0.6.0',
    endpoints: [
      'GET  /health',
      'POST /auth/code',
      'POST /auth/verify',
      'GET  /auth/me',
      'POST /auth/logout',
      'GET    /tracker/wishes',
      'POST   /tracker/wishes',
      'PATCH  /tracker/wishes/:id',
      'DELETE /tracker/wishes/:id',
      'POST   /tracker/wishes/:id/toggle',
      'POST /generate/jobs',
      'GET  /generate/jobs',
      'GET  /generate/jobs/:id',
      'GET  /internal/jobs/pending',
      'POST /internal/jobs/:id/progress',
      'POST /internal/jobs/:id/done',
      'GET  /books/:slug',
      'GET  /books/:slug/:filename',
      'POST /internal/publish',
      'POST /internal/publish/confirm',
      'GET  /internal/publish/status',
      'GET  /internal/publish/list',
      'POST /internal/tg/callback',
      'POST /api/subscribe',
      'POST /api/pay/create',
      'POST /api/pay/webhook',
      'GET  /api/members/access',
      'GET  /api/members/me',
      'POST /api/members/logout',
      'POST /api/experiments',
      'GET  /api/experiments',
      'GET  /api/experiments/count',
    ],
  });
});

app.route('/', authRoutes);
app.route('/', trackerRoutes);
app.route('/', generateRoutes);
app.route('/', publicBooksRouter);
app.route('/', internalRoutes);
app.route('/', socialRoutes);
app.route('/', notificationsRoutes);
app.route('/', subscribeRoutes);
app.route('/', payRoutes);
app.route('/', experimentsRoutes);

// Заглушки для будущих фаз
app.all('/checkout/*', (c) => c.json({ error: 'not_implemented', message: 'Checkout появится в Фазе 4' }, 501));
app.all('/webhook/*', (c) => c.json({ error: 'not_implemented', message: 'Webhooks появятся в Фазе 4' }, 501));

export default app;
