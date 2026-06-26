/**
 * Publisher: оркестратор публикации книги/эксперта.
 *
 * Поток (для одной сущности, kind=book|expert, slug=...):
 *   1. python-service генерит vk/tg/meta тексты
 *   2. VK publish (через VKAdapter)
 *   3. TG publish в канал (через TelegramAdapter)
 *   4. Уведомление админу в личку с inline-кнопками [Удалить VK] [Удалить TG] [Подтвердить]
 *   5. State → PUBLISHED
 *
 * Dry-run (dryRun=true):
 *   - копирайтер работает
 *   - VK/TG возвращают mock (env без токенов → 'dev-mode' результат)
 *   - state кладётся в publish:dry-run:{kind}:{slug}
 *   - в KV social:vk:{slug} / social:tg:{slug} НЕ пишется
 *
 * Идемпотентность:
 *   - повторный POST без ?force=true на state==PUBLISHED → "всё уже опубликовано"
 */
import { Hono } from 'hono';
import type { MiddlewareHandler } from 'hono';
import type { Env } from '../types';
import { KV_KEYS, getAuthUser } from '../lib/kv';
import {
  getPublish, createPublish, savePublish, transitionPublish, listPublishes,
  type PublishKind,
} from '../lib/publish_state';
import { VKAdapter } from '../lib/social_vk';
import { TelegramAdapter } from '../lib/social_tg';

const app = new Hono<{ Bindings: Env }>({ strict: false });

// ────────────────────────────────────────────────
// Auth: python-сервис ИЛИ авторизованный админ (по email)
// ────────────────────────────────────────────────
const requirePublisherAuth: MiddlewareHandler<{ Bindings: Env }> = async (c, next) => {
  // 1) Python-service token
  const auth = c.req.header('Authorization');
  if (auth && c.env.PYTHON_SERVICE_TOKEN && auth === `Bearer ${c.env.PYTHON_SERVICE_TOKEN}`) {
    await next();
    return;
  }
  // 2) Admin email из ?admin=<email> или X-Admin-Email
  const adminEmail = c.req.query('admin') ?? c.req.header('X-Admin-Email');
  if (adminEmail && c.env.LAB_KV) {
    const user = await getAuthUser(c.env.LAB_KV, adminEmail);
    if (user && user.subscriptionStatus === 'active') {
      await next();
      return;
    }
  }
  return c.json({ error: 'unauthorized', message: 'Нужен PYTHON_SERVICE_TOKEN или admin email' }, 401);
};

app.use('/internal/*', requirePublisherAuth);

// ────────────────────────────────────────────────
// Утилита: копирайтер через python-service
// ────────────────────────────────────────────────
interface CopywriteResponse {
  ok: boolean;
  book_slug: string;
  vk?: string;
  tg?: string;
  meta_description?: string;
  source?: 'ai' | 'fallback';
  error?: string;
}

async function callCopywriter(
  env: Env,
  bookSlug: string,
  fallbackOnly = false,
): Promise<CopywriteResponse> {
  if (!env.PYTHON_SERVICE_URL) {
    return {
      ok: false,
      book_slug: bookSlug,
      error: 'PYTHON_SERVICE_URL не задан',
    };
  }
  const url = `${env.PYTHON_SERVICE_URL.replace(/\/$/, '')}/internal/copywrite`;
  const res = await fetch(url, {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${env.PYTHON_SERVICE_TOKEN ?? ''}`,
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ bookSlug, fallbackOnly }),
  });
  if (!res.ok) {
    return { ok: false, book_slug: bookSlug, error: `python-service ${res.status}: ${await res.text()}` };
  }
  return res.json() as Promise<CopywriteResponse>;
}

// ────────────────────────────────────────────────
// POST /internal/publish
// Тело: { kind: 'book' | 'expert', slug: string, dryRun?: bool, force?: bool }
// ────────────────────────────────────────────────
app.post('/internal/publish', async (c) => {
  let body: { kind?: PublishKind; slug?: string; dryRun?: boolean; force?: boolean; initiatedBy?: string };
  try {
    body = await c.req.json();
  } catch {
    return c.json({ error: 'bad_request', message: 'Нужен JSON' }, 400);
  }

  const kind = (body.kind ?? '').trim() as PublishKind;
  const slug = (body.slug ?? '').trim();
  const dryRun = body.dryRun ?? false;
  const force = body.force ?? false;

  if (!['book', 'expert'].includes(kind) || !slug) {
    return c.json({ error: 'bad_request', message: 'kind ∈ {book,expert} и slug обязательны' }, 400);
  }

  // Идемпотентность
  const existing = await getPublish(c.env.LAB_KV, kind, slug, dryRun);
  if (existing && existing.state === 'PUBLISHED' && !force) {
    return c.json({
      ok: true,
      skipped: true,
      message: 'Уже опубликовано. Используйте ?force=true для повтора.',
      record: existing,
    });
  }
  if (existing && existing.state === 'FAILED' && !force) {
    return c.json({
      ok: false,
      message: 'Предыдущая попытка упала. Используйте ?force=true для повтора.',
      record: existing,
    }, 409);
  }

  // 1) Создать или пересоздать record
  let record = existing ?? await createPublish(c.env.LAB_KV, {
    kind, slug, dryRun, initiatedBy: body.initiatedBy,
  });
  if (force && existing) {
    record.state = 'NEW';
    record.error = undefined;
    record.vk = undefined;
    record.tg = undefined;
    await savePublish(c.env.LAB_KV, record);
  }

  const steps: string[] = [];

  try {
    // 2) Копирайтер
    if (record.state === 'NEW') {
      const copies = await callCopywriter(c.env, slug, dryRun);
      if (!copies.ok || !copies.vk || !copies.tg) {
        await transitionPublish(c.env.LAB_KV, kind, slug, 'FAILED', {
          error: copies.error ?? 'Копирайтер не вернул vk/tg',
        }, dryRun);
        return c.json({ ok: false, error: 'copywriter_failed', message: copies.error }, 500);
      }
      record.copies = {
        vk: copies.vk,
        tg: copies.tg,
        meta_description: copies.meta_description,
        source: copies.source,
      };
      record = await transitionPublish(c.env.LAB_KV, kind, slug, 'COPIES_GENERATED', record, dryRun);
      steps.push('COPIES_GENERATED');
    }

    // 3) VK
    if (record.state === 'COPIES_GENERATED' && record.copies?.vk) {
      const vk = new VKAdapter(c.env);
      const linkUrl = c.env.FRONTEND_ORIGIN
        + (kind === 'book' ? `/library/${slug}/` : `/experts/${slug}/`);
      const result = await vk.publishPost({
        message: record.copies.vk,
        link: { url: linkUrl },
      });
      const vkRec = {
        post_id: result.post_id,
        owner_id: result.owner_id,
        url: result.url,
        posted_at: new Date().toISOString(),
        status: 'pending_moderation' as const,
      };
      record.vk = vkRec;
      record = await transitionPublish(c.env.LAB_KV, kind, slug, 'VK_POSTED', record, dryRun);
      if (!dryRun) {
        await c.env.LAB_KV.put(KV_KEYS.socialVk(slug), JSON.stringify(vkRec), {
          expirationTtl: 30 * 24 * 60 * 60,
        });
      }
      steps.push('VK_POSTED');
    }

    // 4) TG (в канал)
    if (record.state === 'VK_POSTED' && record.copies?.tg) {
      const tg = new TelegramAdapter(c.env);
      const linkUrl = c.env.FRONTEND_ORIGIN
        + (kind === 'book' ? `/library/${slug}/` : `/experts/${slug}/`);
      const result = await tg.sendToChannel(record.copies.tg);
      const tgRec = {
        message_id: result.message_id,
        chat_id: result.chat.id,
        url: result.url,
        posted_at: new Date().toISOString(),
      };
      record.tg = tgRec;
      record = await transitionPublish(c.env.LAB_KV, kind, slug, 'TG_POSTED', record, dryRun);
      if (!dryRun) {
        await c.env.LAB_KV.put(KV_KEYS.socialTg(slug), JSON.stringify(tgRec), {
          expirationTtl: 30 * 24 * 60 * 60,
        });
      }
      steps.push('TG_POSTED');
    }

    // 5) Уведомление админу с inline-кнопками
    if (record.state === 'TG_POSTED') {
      const tg = new TelegramAdapter(c.env);
      const lines: string[] = [];
      lines.push('✅ <b>Опубликовано</b>');
      lines.push('');
      lines.push(`<b>${kind === 'book' ? '📚' : '👤'} ${slug}</b>`);
      if (record.copies?.meta_description) {
        lines.push(`<i>${escapeHtml(record.copies.meta_description)}</i>`);
      }
      lines.push('');
      if (record.vk?.url) lines.push(`VK: <a href="${record.vk.url}">${record.vk.url}</a>`);
      if (record.tg?.url) lines.push(`TG: <a href="${record.tg.url}">${record.tg.url}</a>`);
      const buttons: { text: string; callback_data: string }[][] = [
        [
          { text: '🗑 Удалить VK', callback_data: `del_vk:${kind}:${slug}` },
          { text: '🗑 Удалить TG', callback_data: `del_tg:${kind}:${slug}` },
        ],
        [
          { text: '✅ Подтвердить', callback_data: `confirm:${kind}:${slug}` },
        ],
      ];
      await tg.sendToAdmin(lines.join('\n'), buttons);
      record = await transitionPublish(c.env.LAB_KV, kind, slug, 'NOTIFIED', record, dryRun);
      steps.push('NOTIFIED');
    }

    // 6) Если dryRun — сразу PUBLISHED (нет модерации)
    if (dryRun && record.state === 'NOTIFIED') {
      record = await transitionPublish(c.env.LAB_KV, kind, slug, 'PUBLISHED', record, dryRun);
      steps.push('PUBLISHED (dry-run)');
    }

    return c.json({
      ok: true,
      dryRun,
      steps,
      record: await getPublish(c.env.LAB_KV, kind, slug, dryRun),
    });
  } catch (e) {
    const message = e instanceof Error ? e.message : String(e);
    console.error('[publish:error]', kind, slug, message);
    try {
      await transitionPublish(c.env.LAB_KV, kind, slug, 'FAILED', { error: message }, dryRun);
    } catch {
      // ignore
    }
    return c.json({ ok: false, error: 'publish_failed', message }, 500);
  }
});

// ────────────────────────────────────────────────
// POST /internal/publish/confirm
// Тело: { kind, slug, action: 'confirm' | 'del_vk' | 'del_tg' }
// ────────────────────────────────────────────────
app.post('/internal/publish/confirm', async (c) => {
  let body: { kind?: PublishKind; slug?: string; action?: 'confirm' | 'del_vk' | 'del_tg' };
  try {
    body = await c.req.json();
  } catch {
    return c.json({ error: 'bad_request', message: 'Нужен JSON' }, 400);
  }
  const { kind, slug, action } = body;
  if (!kind || !slug || !action) {
    return c.json({ error: 'bad_request', message: 'kind/slug/action обязательны' }, 400);
  }

  const record = await getPublish(c.env.LAB_KV, kind, slug, false);
  if (!record) {
    return c.json({ error: 'not_found', message: 'Запись не найдена' }, 404);
  }
  if (record.dryRun) {
    return c.json({ error: 'conflict', message: 'Нельзя подтвердить dry-run запись' }, 409);
  }

  const results: string[] = [];
  try {
    if (action === 'del_vk' && record.vk && record.vk.post_id && record.vk.owner_id) {
      const vk = new VKAdapter(c.env);
      const ok = await vk.deletePost(record.vk.post_id, record.vk.owner_id);
      results.push(`VK delete: ${ok ? 'ok' : 'failed'}`);
      if (ok) {
        record.vk = undefined;
        await c.env.LAB_KV.delete(KV_KEYS.socialVk(slug));
      }
    }
    if (action === 'del_tg' && record.tg) {
      const tg = new TelegramAdapter(c.env);
      const ok = await tg.deleteMessage(record.tg.chat_id, record.tg.message_id);
      results.push(`TG delete: ${ok ? 'ok' : 'failed'}`);
      if (ok) {
        record.tg = undefined;
        await c.env.LAB_KV.delete(KV_KEYS.socialTg(slug));
      }
    }
    if (action === 'confirm') {
      await transitionPublish(c.env.LAB_KV, kind, slug, 'PUBLISHED', record);
      results.push('→ PUBLISHED');
      return c.json({ ok: true, results, record: await getPublish(c.env.LAB_KV, kind, slug, false) });
    }
    // Если удалили VK/TG — если оба пусты, переходим в FAILED
    if (!record.vk && !record.tg) {
      await transitionPublish(c.env.LAB_KV, kind, slug, 'FAILED', { error: 'Удалено вручную' });
      results.push('→ FAILED (всё удалено)');
    } else {
      await savePublish(c.env.LAB_KV, record);
    }
    return c.json({ ok: true, results, record: await getPublish(c.env.LAB_KV, kind, slug, false) });
  } catch (e) {
    const message = e instanceof Error ? e.message : String(e);
    return c.json({ ok: false, error: 'confirm_failed', message }, 500);
  }
});

// ────────────────────────────────────────────────
// GET /internal/publish/status?kind=book&slug=...
// GET /internal/publish/list?kind=book&state=PUBLISHED
// ────────────────────────────────────────────────
app.get('/internal/publish/status', async (c) => {
  const kind = c.req.query('kind') as PublishKind | undefined;
  const slug = c.req.query('slug');
  const dryRun = c.req.query('dryRun') === 'true';
  if (!kind || !slug) {
    return c.json({ error: 'bad_request', message: 'kind+slug обязательны' }, 400);
  }
  const rec = await getPublish(c.env.LAB_KV, kind, slug, dryRun);
  return c.json({ ok: true, record: rec });
});

app.get('/internal/publish/list', async (c) => {
  const kind = c.req.query('kind') as PublishKind | undefined;
  const state = c.req.query('state') as any;
  const dryRun = c.req.query('dryRun') === 'true';
  const limit = Math.min(200, parseInt(c.req.query('limit') ?? '50', 10));
  const records = await listPublishes(c.env.LAB_KV, { kind, state, dryRun, limit });
  return c.json({ ok: true, total: records.length, records });
});

// ────────────────────────────────────────────────
// Утилита
// ────────────────────────────────────────────────
function escapeHtml(s: string): string {
  return s
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

export default app;
