import { Hono } from 'hono';
import type { Env } from '../types';
import { requireAuth } from '../middleware/auth';
import { KV_KEYS } from '../lib/kv';
import { getBook } from '../lib/books';

const app = new Hono<{ Bindings: Env }>({ strict: false });

// Все роуты требуют авторизации (JWT)
app.use('/generate/*', requireAuth);

// ────────────────────────────────────────────────
// Типы
// ────────────────────────────────────────────────

export type JobStage =
  | 'queued'
  | 'starting'
  | 'parsing'
  | 'summary'
  | 'workbook'
  | 'tips'
  | 'cover'
  | 'done'
  | 'error';

export interface GenerationJob {
  jobId: string;
  userId: string;
  /** Только URL — поиск по koob.ru унесён в python, нам не нужно угадывать. */
  bookUrl: string;
  status: 'pending' | 'running' | 'done' | 'error';
  stage: JobStage;
  progress: number; // 0..100
  message: string;
  slug?: string;
  /** Метаданные результата, кладём сюда же в KV при done, чтобы GET не дёргал R2. */
  result?: {
    slug: string;
    title: string;
    author: string;
    year?: number | null;
    description?: string;
  };
  error?: string;
  createdAt: string;
  updatedAt: string;
  startedAt?: string;
  finishedAt?: string;
}

function newJobId(): string {
  return crypto.randomUUID().replace(/-/g, '').slice(0, 16);
}

const KOOB_URL_RE = /^https?:\/\/(www\.)?koob\.ru\/[\w\-./?=&%#]+$/i;

function publicJobView(job: GenerationJob, env: Env) {
  return {
    jobId: job.jobId,
    status: job.status,
    stage: job.stage,
    progress: job.progress,
    message: job.message,
    slug: job.slug,
    result: job.result,
    error: job.error,
    createdAt: job.createdAt,
    updatedAt: job.updatedAt,
    startedAt: job.startedAt,
    finishedAt: job.finishedAt,
    bookUrl: env.FRONTEND_ORIGIN.includes(job.bookUrl) ? undefined : undefined, // никогда не отдаём url обратно
  };
}

// ────────────────────────────────────────────────
// POST /generate/jobs
// Body: { bookUrl: string }
// ────────────────────────────────────────────────
app.post('/generate/jobs', async (c) => {
  const user = c.get('user')!;

  let body: { bookUrl?: string };
  try {
    body = await c.req.json();
  } catch {
    return c.json({ error: 'bad_request', message: 'Нужен JSON с полем bookUrl' }, 400);
  }

  const url = (body.bookUrl ?? '').trim();
  if (!url) {
    return c.json({ error: 'bad_request', message: 'Укажите URL книги на koob.ru' }, 400);
  }
  if (!KOOB_URL_RE.test(url)) {
    return c.json({ error: 'bad_request', message: 'Поддерживаются только ссылки на koob.ru' }, 400);
  }
  if (url.length > 500) {
    return c.json({ error: 'bad_request', message: 'Слишком длинный URL' }, 400);
  }

  // Квота: списываем сразу при создании job
  const { incrementGenerationCount, getGenerationCounts } = await import('../lib/kv');
  const counts = await getGenerationCounts(c.env.LAB_KV, user.userId);
  const perDay = user.plan === 'free' ? 1 : user.plan === 'month' ? 5 : 100;
  if (counts.month >= user.generationsLimit) {
    return c.json({
      error: 'quota_exceeded',
      message: `Лимит генераций на месяц: ${user.generationsLimit}. Оформите подписку.`,
      quota: { used: counts.month, limit: user.generationsLimit, plan: user.plan },
      upgradeUrl: '/pricing/',
    }, 403);
  }
  if (counts.day >= perDay) {
    return c.json({
      error: 'quota_exceeded_daily',
      message: `Дневной лимит: ${perDay} генераций. Попробуйте завтра.`,
      quota: { used: counts.day, limit: perDay, plan: user.plan },
    }, 429);
  }

  // Списываем
  await incrementGenerationCount(c.env.LAB_KV, user.userId);

  const now = new Date().toISOString();
  const job: GenerationJob = {
    jobId: newJobId(),
    userId: user.userId,
    bookUrl: url,
    status: 'pending',
    stage: 'queued',
    progress: 0,
    message: 'В очереди',
    createdAt: now,
    updatedAt: now,
  };
  await c.env.LAB_KV.put(KV_KEYS.job(job.jobId), JSON.stringify(job), {
    // TTL 6 часов — за это время генерация уж точно завершится или упадёт
    expirationTtl: 6 * 60 * 60,
  });

  return c.json({ ok: true, job: publicJobView(job, c.env) }, 201);
});

// ────────────────────────────────────────────────
// GET /generate/jobs/:id
// ────────────────────────────────────────────────
app.get('/generate/jobs/:id', async (c) => {
  const user = c.get('user')!;
  const id = c.req.param('id');
  const raw = await c.env.LAB_KV.get(KV_KEYS.job(id));
  if (!raw) {
    return c.json({ error: 'not_found', message: 'Job не найден или истёк' }, 404);
  }
  let job: GenerationJob;
  try {
    job = JSON.parse(raw) as GenerationJob;
  } catch {
    return c.json({ error: 'corrupt_job', message: 'Job повреждён' }, 500);
  }
  if (job.userId !== user.userId) {
    // Чужой jobId — отдаём 404, чтобы не палить существование
    return c.json({ error: 'not_found', message: 'Job не найден' }, 404);
  }
  return c.json({ ok: true, job: publicJobView(job, c.env) });
});

// ────────────────────────────────────────────────
// GET /generate/jobs  (последние job'ы пользователя)
// ────────────────────────────────────────────────
app.get('/generate/jobs', async (c) => {
  const user = c.get('user')!;
  // Листинг по prefix: KV не поддерживает native listing с фильтром,
  // поэтому храним индекс job:user:{userId}:{jobId} — добавим ниже, в done callback.
  // Сейчас — заглушка, чтобы фронт не падал.
  const list = await c.env.LAB_KV.list({ prefix: `job:user:${user.userId}:` });
  const jobs: GenerationJob[] = [];
  for (const k of list.keys.slice(0, 50)) {
    const raw = await c.env.LAB_KV.get(k.name);
    if (!raw) continue;
    try {
      jobs.push(JSON.parse(raw) as GenerationJob);
    } catch {
      /* skip */
    }
  }
  jobs.sort((a, b) => b.createdAt.localeCompare(a.createdAt));
  return c.json({
    ok: true,
    jobs: jobs.map((j) => publicJobView(j, c.env)),
    quota: {
      // Подтянем актуальные цифры
      ...(await (async () => {
        const { getGenerationCounts } = await import('../lib/kv');
        const counts = await getGenerationCounts(c.env.LAB_KV, user.userId);
        return { usedThisMonth: counts.month, limitThisMonth: user.generationsLimit };
      })()),
    },
  });
});

export default app;
