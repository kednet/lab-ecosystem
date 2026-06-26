import { Hono } from 'hono';
import type { MiddlewareHandler } from 'hono';
import type { Env } from '../types';
import { KV_KEYS } from '../lib/kv';
import { uploadBook, getBookFile, fileBlobToBytes, type BookFileMeta } from '../lib/books';
import type { GenerationJob, JobStage } from './generate';

const app = new Hono<{ Bindings: Env }>({ strict: false });

// ────────────────────────────────────────────────
// Auth: проверка Bearer PYTHON_SERVICE_TOKEN
// ────────────────────────────────────────────────
const requirePythonAuth: MiddlewareHandler<{ Bindings: Env }> = async (c, next) => {
  const auth = c.req.header('Authorization');
  const expected = c.env.PYTHON_SERVICE_TOKEN;
  if (!expected) {
    return c.json({ error: 'server_misconfigured', message: 'PYTHON_SERVICE_TOKEN не задан' }, 500);
  }
  if (auth !== `Bearer ${expected}`) {
    return c.json({ error: 'unauthorized', message: 'Bad token' }, 401);
  }
  await next();
};

app.use('/internal/*', requirePythonAuth);

// ────────────────────────────────────────────────
// Утилиты
// ────────────────────────────────────────────────

async function loadJob(env: Env, jobId: string): Promise<GenerationJob | null> {
  const raw = await env.LAB_KV.get(KV_KEYS.job(jobId));
  if (!raw) return null;
  try {
    return JSON.parse(raw) as GenerationJob;
  } catch {
    return null;
  }
}

async function saveJob(env: Env, job: GenerationJob): Promise<void> {
  job.updatedAt = new Date().toISOString();
  await env.LAB_KV.put(KV_KEYS.job(job.jobId), JSON.stringify(job), {
    expirationTtl: 6 * 60 * 60,
  });
}

async function markIndex(env: Env, userId: string, jobId: string): Promise<void> {
  await env.LAB_KV.put(KV_KEYS.jobUser(userId, jobId), jobId, {
    expirationTtl: 30 * 24 * 60 * 60,
  });
}

// ────────────────────────────────────────────────
// GET /internal/jobs/pending
// python-сервис поллит каждые 2 сек, отдаём pending → running.
// ────────────────────────────────────────────────
app.get('/internal/jobs/pending', async (c) => {
  const limit = Math.min(20, Math.max(1, parseInt(c.req.query('limit') ?? '5', 10)));
  const list = await c.env.LAB_KV.list({ prefix: 'job:' });
  const pending: GenerationJob[] = [];
  for (const k of list.keys) {
    if (k.name.startsWith('job:user:')) continue;
    const raw = await c.env.LAB_KV.get(k.name);
    if (!raw) continue;
    let job: GenerationJob;
    try {
      job = JSON.parse(raw) as GenerationJob;
    } catch {
      continue;
    }
    if (job.status !== 'pending') continue;
    job.status = 'running';
    job.startedAt = job.startedAt ?? new Date().toISOString();
    job.stage = 'starting';
    job.message = 'Приняли в работу';
    await saveJob(c.env, job);
    pending.push(job);
    if (pending.length >= limit) break;
  }
  return c.json({
    ok: true,
    jobs: pending.map((j) => ({
      jobId: j.jobId,
      userId: j.userId,
      bookQuery: j.bookUrl,
      queryType: 'url',
    })),
  });
});

// ────────────────────────────────────────────────
// POST /internal/jobs/:id/progress
// ────────────────────────────────────────────────
app.post('/internal/jobs/:id/progress', async (c) => {
  const id = c.req.param('id');
  let body: { stage?: string; progress?: number; message?: string; userId?: string };
  try {
    body = await c.req.json();
  } catch {
    return c.json({ error: 'bad_request', message: 'Нужен JSON' }, 400);
  }

  const job = await loadJob(c.env, id);
  if (!job) {
    return c.json({ ok: true, expired: true });
  }

  const stage = (body.stage ?? 'starting') as JobStage;
  const progress = Math.max(0, Math.min(100, Math.floor(body.progress ?? 0)));
  job.stage = stage;
  job.progress = progress;
  if (typeof body.message === 'string') job.message = body.message;
  if (stage === 'error') {
    job.status = 'error';
    job.error = body.message ?? 'Unknown error';
    job.finishedAt = new Date().toISOString();
  }
  await saveJob(c.env, job);
  return c.json({ ok: true });
});

// ────────────────────────────────────────────────
// POST /internal/jobs/:id/done  (multipart/form-data)
//
// Fields:
//   result (JSON string): { slug, title, author, year, description }
//   files[summary|workbook|tips|cover] (file)
//
// Кладёт файлы в KV (base64) и метаданные в KV book:{slug}.
// ────────────────────────────────────────────────
app.post('/internal/jobs/:id/done', async (c) => {
  const id = c.req.param('id');
  const job = await loadJob(c.env, id);
  if (!job) {
    return c.json({ error: 'not_found', message: 'Job не найден или истёк' }, 404);
  }

  let form: FormData;
  try {
    form = await c.req.formData();
  } catch {
    return c.json({ error: 'bad_request', message: 'Ожидаем multipart/form-data' }, 400);
  }

  const resultRaw = form.get('result');
  if (typeof resultRaw !== 'string') {
    return c.json({ error: 'bad_request', message: 'Нет поля result' }, 400);
  }
  let result: { slug?: string; title?: string; author?: string; year?: number | null; description?: string };
  try {
    result = JSON.parse(resultRaw);
  } catch {
    return c.json({ error: 'bad_request', message: 'result — невалидный JSON' }, 400);
  }

  const slug = (result.slug ?? '').trim();
  const title = (result.title ?? '').trim();
  const author = (result.author ?? '').trim();
  if (!slug || !title || !author) {
    return c.json({ error: 'bad_request', message: 'slug/title/author обязательны' }, 400);
  }

  const files: { kind: BookFileMeta['kind']; name: string; body: ArrayBuffer }[] = [];
  for (const [fieldName, value] of form.entries()) {
    if (!fieldName.startsWith('files[')) continue;
    if (typeof value === 'string') continue;
    const fileValue = value as File;
    const kind = (fieldName.match(/^files\[(\w+)\]$/)?.[1] ?? 'other') as BookFileMeta['kind'];
    const filename = fileValue.name || `${kind}.bin`;
    const body = await fileValue.arrayBuffer();
    files.push({ kind, name: filename, body });
  }

  if (files.length === 0) {
    return c.json({ error: 'bad_request', message: 'Нет файлов в files[]' }, 400);
  }

  try {
    const book = await uploadBook(c.env, {
      slug,
      title,
      author,
      year: result.year ?? null,
      description: result.description ?? '',
      files: files.map((f) => ({ kind: f.kind, name: f.name, body: f.body })),
      generatedBy: job.userId,
      generatedByJob: job.jobId,
    });

    job.status = 'done';
    job.stage = 'done';
    job.progress = 100;
    job.message = `Готово: ${title}`;
    job.slug = slug;
    job.result = {
      slug,
      title,
      author,
      year: result.year ?? null,
      description: result.description ?? '',
    };
    job.finishedAt = new Date().toISOString();
    await saveJob(c.env, job);
    await markIndex(c.env, job.userId, job.jobId);

    return c.json({
      ok: true,
      slug,
      bookUrl: `${c.env.FRONTEND_ORIGIN}/library/${slug}/`,
      files: book.files,
    });
  } catch (e) {
    console.error('[internal/done] upload failed', e);
    job.status = 'error';
    job.stage = 'error';
    job.error = e instanceof Error ? e.message : String(e);
    job.finishedAt = new Date().toISOString();
    await saveJob(c.env, job);
    return c.json({ error: 'upload_failed', message: job.error }, 500);
  }
});

export default app;

// ────────────────────────────────────────────────
// Публичная отдача файлов книги (без python-токена)
// GET /books/:slug/:filename
//
// Достаёт base64 из KV, декодирует, отдаёт с правильным content-type.
// Cloudflare CDN сам закеширует на 1 час (Cache-Control: public, max-age=3600).
// ────────────────────────────────────────────────
const publicBooksRouter = new Hono<{ Bindings: Env }>();

publicBooksRouter.get('/books/:slug/:filename', async (c) => {
  const slug = c.req.param('slug');
  const filename = c.req.param('filename');
  const blob = await getBookFile(c.env, slug, filename);
  if (!blob) {
    return c.json({ error: 'not_found', message: 'Файл не найден' }, 404);
  }
  const bytes = fileBlobToBytes(blob);
  const headers = new Headers();
  headers.set('Content-Type', blob.contentType);
  headers.set('Content-Length', String(bytes.byteLength));
  headers.set('Cache-Control', 'public, max-age=3600');
  return new Response(bytes, { headers });
});

publicBooksRouter.get('/books/:slug', async (c) => {
  const slug = c.req.param('slug');
  const { getBook } = await import('../lib/books');
  const book = await getBook(c.env, slug);
  if (!book) return c.json({ error: 'not_found', message: 'Книга не найдена' }, 404);
  return c.json({ ok: true, book });
});

export { publicBooksRouter };
