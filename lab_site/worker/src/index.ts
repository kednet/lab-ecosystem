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

const app = new Hono<{ Bindings: Env }>();

// Глобальный обработчик ошибок — возвращает JSON, а не HTML
app.onError((err, c) => {
  console.error('[worker-error]', err.message, err.stack);
  return c.json({ error: 'internal_error', message: 'Что-то пошло не так' }, 500);
});

// 404 в JSON
app.notFound((c) => c.json({ error: 'not_found', message: 'Роут не найден' }, 404));

// ────────────────────────────────────────────────
// Middleware (порядок важен: сначала auth, потом CORS)
// ────────────────────────────────────────────────
app.use('*', optionalAuth);

app.use('*', async (c, next) => {
  // Preflight
  if (c.req.method === 'OPTIONS') {
    return new Response(null, { status: 204, headers: corsHeaders(c.env, c.req.raw) });
  }
  await next();
  return applyCors(c.res, c.env, c.req.raw);
});

// ────────────────────────────────────────────────
// Публичные роуты
// ────────────────────────────────────────────────
app.get('/health', (c) => {
  return c.json({
    status: 'ok',
    environment: c.env.ENVIRONMENT,
    timestamp: new Date().toISOString(),
    version: '0.4.0',
  });
});

app.get('/', (c) => {
  return c.json({
    name: 'lab-site-api',
    docs: 'https://app.pulab.online',
    version: '0.4.0',
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
    ],
  });
});

// ────────────────────────────────────────────────
// Auth роуты
// ────────────────────────────────────────────────
app.route('/', authRoutes);

// ────────────────────────────────────────────────
// Tracker роуты (требуют JWT)
// ────────────────────────────────────────────────
app.route('/', trackerRoutes);

// ────────────────────────────────────────────────
// Генерация (Фаза 3) — требует JWT
// ────────────────────────────────────────────────
app.route('/', generateRoutes);

// ────────────────────────────────────────────────
// Публичная отдача файлов книг из KV (без auth — книги публичны по URL)
// ────────────────────────────────────────────────
app.route('/', publicBooksRouter);

// ────────────────────────────────────────────────
// Internal роуты (защищены PYTHON_SERVICE_TOKEN — см. routes/internal.ts)
// ────────────────────────────────────────────────
app.route('/', internalRoutes);

// ────────────────────────────────────────────────
// Publisher (Фаза 5+): анонсы в VK + TG, уведомления админу
// ────────────────────────────────────────────────
app.route('/', socialRoutes);
app.route('/', notificationsRoutes);

// Заглушка для будущих фаз
app.all('/checkout/*', (c) => c.json({ error: 'not_implemented', message: 'Checkout появится в Фазе 4' }, 501));
app.all('/webhook/*', (c) => c.json({ error: 'not_implemented', message: 'Webhooks появятся в Фазе 4' }, 501));

export default app;
