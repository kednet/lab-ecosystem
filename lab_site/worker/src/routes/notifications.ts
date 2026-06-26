/**
 * Telegram callback webhook — обработка нажатий inline-кнопок.
 *
 * Вызывается через секретный URL: POST /internal/tg/callback
 * Telegram отправляет update с callback_query.
 *
 * ВАЖНО: в проде нужно проверять X-Telegram-Bot-Api-Secret-Token,
 * но т.к. эндпоинт internal — закрываем PYTHON_SERVICE_TOKEN
 * (Telegram сам не сможет дёрнуть, нам нужно вручную проксировать
 *  через python-service или Cloudflare Worker relay).
 */
import { Hono } from 'hono';
import type { MiddlewareHandler } from 'hono';
import type { Env } from '../types';
import { TelegramAdapter } from '../lib/social_tg';
import { VKAdapter } from '../lib/social_vk';
import {
  getPublish, transitionPublish, savePublish, type PublishKind,
} from '../lib/publish_state';
import { KV_KEYS } from '../lib/kv';

const app = new Hono<{ Bindings: Env }>({ strict: false });

const requireInternalAuth: MiddlewareHandler<{ Bindings: Env }> = async (c, next) => {
  const auth = c.req.header('Authorization');
  if (auth && c.env.PYTHON_SERVICE_TOKEN && auth === `Bearer ${c.env.PYTHON_SERVICE_TOKEN}`) {
    await next();
    return;
  }
  // Для callback'ов от Telegram (если они дойдут напрямую) — проверим secret-token
  const secret = c.req.header('X-Telegram-Bot-Api-Secret-Token');
  if (secret && secret === c.env.TELEGRAM_BOT_TOKEN?.slice(-16)) {
    await next();
    return;
  }
  return c.json({ error: 'unauthorized' }, 401);
};

app.use('/internal/*', requireInternalAuth);

interface TgCallbackUpdate {
  update_id: number;
  callback_query?: {
    id: string;
    from: { id: number; is_bot?: boolean; first_name?: string; username?: string };
    message?: { message_id: number; chat: { id: number | string; type?: string } };
    data?: string;
  };
}

app.post('/internal/tg/callback', async (c) => {
  let update: TgCallbackUpdate;
  try {
    update = await c.req.json();
  } catch {
    return c.json({ ok: false, error: 'bad_request' }, 400);
  }

  const cb = update.callback_query;
  if (!cb || !cb.data) {
    return c.json({ ok: true, skipped: true });
  }

  const tg = new TelegramAdapter(c.env);

  // ── Парсим action
  // Формат: "del_vk:book:slug-123" / "del_tg:expert:slug" / "confirm:book:slug"
  const parts = cb.data.split(':');
  if (parts.length < 3) {
    await tg.answerCallback(cb.id, 'Неизвестная команда', true);
    return c.json({ ok: true });
  }
  const [action, kindRaw, ...rest] = parts;
  const kind = kindRaw as PublishKind;
  const slug = rest.join(':');

  const record = await getPublish(c.env.LAB_KV, kind, slug, false);
  if (!record) {
    await tg.answerCallback(cb.id, `Запись ${kind}:${slug} не найдена`, true);
    return c.json({ ok: true });
  }

  try {
    if (action === 'del_vk' && record.vk && record.vk.post_id && record.vk.owner_id) {
      const vk = new VKAdapter(c.env);
      const ok = await vk.deletePost(record.vk.post_id, record.vk.owner_id);
      if (ok) {
        record.vk = undefined;
        await c.env.LAB_KV.delete(KV_KEYS.socialVk(slug));
        await tg.answerCallback(cb.id, 'VK пост удалён');
      } else {
        await tg.answerCallback(cb.id, 'Не удалось удалить VK', true);
      }
    } else if (action === 'del_tg' && record.tg) {
      const ok = await tg.deleteMessage(record.tg.chat_id, record.tg.message_id);
      if (ok) {
        record.tg = undefined;
        await c.env.LAB_KV.delete(KV_KEYS.socialTg(slug));
        await tg.answerCallback(cb.id, 'TG сообщение удалено');
      } else {
        await tg.answerCallback(cb.id, 'Не удалось удалить TG', true);
      }
    } else if (action === 'confirm') {
      await transitionPublish(c.env.LAB_KV, kind, slug, 'PUBLISHED', record);
      await tg.answerCallback(cb.id, 'Подтверждено ✅');
    } else {
      await tg.answerCallback(cb.id, 'Действие не применимо', true);
    }

    // Обновить кнопки: если оба поста удалены → FAILED
    if (!record.vk && !record.tg) {
      await transitionPublish(c.env.LAB_KV, kind, slug, 'FAILED', { error: 'Удалено вручную через TG callback' });
    } else {
      await savePublish(c.env.LAB_KV, record);
    }

    return c.json({ ok: true });
  } catch (e) {
    const message = e instanceof Error ? e.message : String(e);
    await tg.answerCallback(cb.id, `Ошибка: ${message}`, true);
    return c.json({ ok: false, error: message }, 500);
  }
});

export default app;
