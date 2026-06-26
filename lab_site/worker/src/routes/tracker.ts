import { Hono } from 'hono';
import type { Env } from '../types';
import { requireAuth } from '../middleware/auth';
import { KV_KEYS, type AuthUser } from '../lib/kv';

const app = new Hono<{ Bindings: Env }>({ strict: false });

// Все роуты требуют авторизации
app.use('/tracker/*', requireAuth);

// ────────────────────────────────────────────────
// Вспомогательные функции
// ────────────────────────────────────────────────

interface Step {
  id: string;
  text: string;
  done: boolean;
  doneAt?: string;
}

export interface Wish {
  id: string;
  title: string;
  description?: string;
  steps: Step[];
  createdAt: string;
  updatedAt: string;
  archivedAt?: string;
}

function newId(): string {
  // 12 символов base36 (≈ 60 бит энтропии) — достаточно для нашего масштаба
  return crypto.randomUUID().replace(/-/g, '').slice(0, 12);
}

async function loadWishes(kv: KVNamespace, userId: string): Promise<Wish[]> {
  const raw = await kv.get(KV_KEYS.trackerWishes(userId));
  if (!raw) return [];
  try {
    return JSON.parse(raw) as Wish[];
  } catch {
    return [];
  }
}

async function saveWishes(kv: KVNamespace, userId: string, wishes: Wish[]): Promise<void> {
  await kv.put(KV_KEYS.trackerWishes(userId), JSON.stringify(wishes));
}

function activeWishesCount(wishes: Wish[]): number {
  return wishes.filter((w) => !w.archivedAt).length;
}

// ────────────────────────────────────────────────
// GET /tracker/wishes
// Возвращает все желания пользователя + квоты
// ────────────────────────────────────────────────
app.get('/tracker/wishes', async (c) => {
  const user = c.get('user')!;
  const wishes = await loadWishes(c.env.LAB_KV, user.userId);
  // Сортируем: активные сверху (свежие первые), архив в конце
  const sorted = [...wishes].sort((a, b) => {
    if (!!a.archivedAt !== !!b.archivedAt) return a.archivedAt ? 1 : -1;
    return b.createdAt.localeCompare(a.createdAt);
  });
  return c.json({
    wishes: sorted,
    quota: {
      active: activeWishesCount(wishes),
      limit: user.wishesLimit,
      remaining: Math.max(0, user.wishesLimit - activeWishesCount(wishes)),
      plan: user.plan,
    },
  });
});

// ────────────────────────────────────────────────
// POST /tracker/wishes
// Body: { title, description?, steps?: [{text}] }
// ────────────────────────────────────────────────
app.post('/tracker/wishes', async (c) => {
  const user = c.get('user')!;
  let body: { title?: string; description?: string; steps?: { text?: string }[] };
  try {
    body = await c.req.json();
  } catch {
    return c.json({ error: 'bad_request', message: 'Нужен JSON' }, 400);
  }

  const title = (body.title ?? '').trim();
  const description = (body.description ?? '').trim() || undefined;

  if (!title) return c.json({ error: 'bad_request', message: 'Название обязательно' }, 400);
  if (title.length > 100) return c.json({ error: 'bad_request', message: 'Название слишком длинное (макс. 100)' }, 400);
  if (description && description.length > 500) {
    return c.json({ error: 'bad_request', message: 'Описание слишком длинное (макс. 500)' }, 500);
  }

  const wishes = await loadWishes(c.env.LAB_KV, user.userId);
  const active = activeWishesCount(wishes);
  if (active >= user.wishesLimit) {
    return c.json({
      error: 'quota_exceeded',
      message: `Лимит активных желаний: ${user.wishesLimit}. Удали или заархивируй старые, или оформи подписку.`,
      quota: { active, limit: user.wishesLimit },
      upgradeUrl: '/pricing/',
    }, 403);
  }

  // Шаги: максимум 10, текст ≤ 200 символов
  const stepInputs = Array.isArray(body.steps) ? body.steps.slice(0, 10) : [];
  const steps: Step[] = stepInputs
    .map((s) => ({ text: (s?.text ?? '').trim() }))
    .filter((s) => s.text.length > 0)
    .map((s) => {
      if (s.text.length > 200) s.text = s.text.slice(0, 200);
      return { id: newId(), text: s.text, done: false };
    });

  const now = new Date().toISOString();
  const wish: Wish = {
    id: newId(),
    title,
    description,
    steps,
    createdAt: now,
    updatedAt: now,
  };
  wishes.push(wish);
  await saveWishes(c.env.LAB_KV, user.userId, wishes);

  return c.json({ ok: true, wish }, 201);
});

// ────────────────────────────────────────────────
// PATCH /tracker/wishes/:id
// Body: { title?, description?, steps? }
// Полная замена полей. steps заменяет весь массив.
// ────────────────────────────────────────────────
app.patch('/tracker/wishes/:id', async (c) => {
  const user = c.get('user')!;
  const id = c.req.param('id');
  let body: { title?: string; description?: string; steps?: { id?: string; text?: string; done?: boolean }[]; archived?: boolean };
  try {
    body = await c.req.json();
  } catch {
    return c.json({ error: 'bad_request', message: 'Нужен JSON' }, 400);
  }

  const wishes = await loadWishes(c.env.LAB_KV, user.userId);
  const wish = wishes.find((w) => w.id === id);
  if (!wish) return c.json({ error: 'not_found', message: 'Желание не найдено' }, 404);

  if (typeof body.title === 'string') {
    const title = body.title.trim();
    if (!title) return c.json({ error: 'bad_request', message: 'Название не может быть пустым' }, 400);
    if (title.length > 100) return c.json({ error: 'bad_request', message: 'Название слишком длинное' }, 400);
    wish.title = title;
  }

  if (typeof body.description === 'string') {
    const desc = body.description.trim();
    if (desc.length > 500) return c.json({ error: 'bad_request', message: 'Описание слишком длинное' }, 400);
    wish.description = desc || undefined;
  }

  if (Array.isArray(body.steps)) {
    const newSteps: Step[] = body.steps.slice(0, 10).map((s) => {
      const text = (s?.text ?? '').trim().slice(0, 200);
      const stepId = s?.id && wishes.find((w) => w.steps.some((x) => x.id === s.id)) ? s.id : newId();
      const done = !!s?.done;
      return {
        id: stepId,
        text,
        done,
        doneAt: done ? (wishes.find((w) => w.steps.find((x) => x.id === stepId))?.steps.find((x) => x.id === stepId)?.doneAt ?? new Date().toISOString()) : undefined,
      };
    }).filter((s) => s.text.length > 0);
    wish.steps = newSteps;
  }

  if (typeof body.archived === 'boolean') {
    wish.archivedAt = body.archived ? new Date().toISOString() : undefined;
  }

  wish.updatedAt = new Date().toISOString();
  await saveWishes(c.env.LAB_KV, user.userId, wishes);
  return c.json({ ok: true, wish });
});

// ────────────────────────────────────────────────
// DELETE /tracker/wishes/:id
// ────────────────────────────────────────────────
app.delete('/tracker/wishes/:id', async (c) => {
  const user = c.get('user')!;
  const id = c.req.param('id');
  const wishes = await loadWishes(c.env.LAB_KV, user.userId);
  const idx = wishes.findIndex((w) => w.id === id);
  if (idx === -1) return c.json({ error: 'not_found', message: 'Желание не найдено' }, 404);
  const [removed] = wishes.splice(idx, 1);
  await saveWishes(c.env.LAB_KV, user.userId, wishes);
  return c.json({ ok: true, removedId: removed.id });
});

// ────────────────────────────────────────────────
// POST /tracker/wishes/:id/toggle  (быстрый чекбокс шага)
// Body: { stepId: string, done: boolean }
// ────────────────────────────────────────────────
app.post('/tracker/wishes/:id/toggle', async (c) => {
  const user = c.get('user')!;
  const id = c.req.param('id');
  let body: { stepId?: string; done?: boolean };
  try {
    body = await c.req.json();
  } catch {
    return c.json({ error: 'bad_request', message: 'Нужен JSON' }, 400);
  }
  const stepId = (body.stepId ?? '').trim();
  if (!stepId) return c.json({ error: 'bad_request', message: 'Нужен stepId' }, 400);
  const done = !!body.done;

  const wishes = await loadWishes(c.env.LAB_KV, user.userId);
  const wish = wishes.find((w) => w.id === id);
  if (!wish) return c.json({ error: 'not_found', message: 'Желание не найдено' }, 404);
  const step = wish.steps.find((s) => s.id === stepId);
  if (!step) return c.json({ error: 'not_found', message: 'Шаг не найден' }, 404);

  step.done = done;
  step.doneAt = done ? new Date().toISOString() : undefined;
  wish.updatedAt = new Date().toISOString();
  await saveWishes(c.env.LAB_KV, user.userId, wishes);
  return c.json({ ok: true, wish });
});

export default app;
