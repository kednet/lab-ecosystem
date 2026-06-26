import { Hono } from 'hono';
import type { Env } from '../types';
import { KV_KEYS } from '../lib/kv';
import { subscribe as unisenderSubscribe, unsubscribe as unisenderUnsubscribe } from '../lib/unisender';

const app = new Hono<{ Bindings: Env }>();

// Простая валидация email — та же, что в /auth/code
const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

// Лимиты антиспама
const RL_IP_LIMIT = 5;        // 5 сабмитов с одного IP в час
const RL_IP_TTL_SEC = 3600;
const RL_EMAIL_LIMIT = 1;     // 1 повтор в сутки (повтор — отправим письмо ещё раз)
const RL_EMAIL_TTL_SEC = 86400;

function clientIp(c: { req: { raw: Request } }): string {
  const r = c.req.raw;
  return (
    r.headers.get('cf-connecting-ip') ??
    (r.headers.get('x-forwarded-for') ?? '').split(',')[0].trim() ??
    r.headers.get('x-real-ip') ??
    'unknown'
  );
}

// ────────────────────────────────────────────────
// POST /api/subscribe
// Body: { email, consent?: bool, hp?: string, source?: string }
//
// Подписка через UniSender (API v3):
//   - список: UNISENDER_LIST_ID (env)
//   - double_optin=0: UniSender сам шлёт confirmation-письмо с кнопкой "подтвердить"
//     (контринтуитивно, но по ответу их поддержки 2026-06-21: 0 = слать confirm-письмо,
//      1 = не слать; см. https://www.unisender.com/ru/support/api/contacts/subscribe/)
//   - overwrite=2: повторный submit обновит запись (не дубль)
//
// Локальный rate-limit (KV) защищает от ботов ДО обращения к UniSender.
// В KV пишем факт подписки (для счётчика и аналитики), но источник правды — UniSender.
// ────────────────────────────────────────────────
app.post('/api/subscribe', async (c) => {
  let body: { email?: string; consent?: boolean; hp?: string; source?: string };
  try {
    body = await c.req.json();
  } catch {
    return c.json({ error: 'bad_request', message: 'Нужен JSON' }, 400);
  }

  // Honeypot: если скрытое поле заполнено — это бот. Молча вернём 200 без записи.
  if (body.hp && body.hp.trim() !== '') {
    console.log('[subscribe] honeypot triggered, ip=', clientIp(c));
    return c.json({ ok: true });
  }

  const email = (body.email ?? '').trim().toLowerCase();
  if (!email || !EMAIL_RE.test(email) || email.length > 254) {
    return c.json({ error: 'invalid_email', message: 'Похоже, email указан неверно' }, 400);
  }

  // Согласие на обработку ПД (152-ФЗ). Чекбокс обязателен.
  if (body.consent !== true) {
    return c.json({ error: 'consent_required', message: 'Нужно согласие на обработку email' }, 400);
  }

  const ip = clientIp(c);

  // Rate-limit по IP (5/час)
  const ipKey = KV_KEYS.subscribeRlIp(ip);
  const ipCountRaw = await c.env.LAB_KV.get(ipKey);
  const ipCount = parseInt(ipCountRaw ?? '0', 10);
  if (ipCount >= RL_IP_LIMIT) {
    return c.json(
      { error: 'rate_limited', message: 'Слишком много попыток с этого IP. Попробуйте через час.' },
      429,
    );
  }

  // Rate-limit по email (1/сутки) — но не блокируем повторный сабмит.
  const emailKey = KV_KEYS.subscribeRlEmail(email);
  const emailCountRaw = await c.env.LAB_KV.get(emailKey);
  const emailCount = parseInt(emailCountRaw ?? '0', 10);

  // Записываем в KV (идемпотентно — обновляем updatedAt, но createdAt первый раз).
  const subKey = KV_KEYS.subscribeEmail(email);
  const existing = await c.env.LAB_KV.get(subKey);
  const isNew = !existing;

  const record = {
    email,
    source: body.source ?? 'homepage',
    createdAt: existing ? (JSON.parse(existing).createdAt as string) : new Date().toISOString(),
    updatedAt: new Date().toISOString(),
    ip,
    confirmedAt: null as string | null,
  };
  await c.env.LAB_KV.put(subKey, JSON.stringify(record));

  // Обновляем rate-limit счётчики
  await c.env.LAB_KV.put(ipKey, String(ipCount + 1), { expirationTtl: RL_IP_TTL_SEC });
  if (emailCount < RL_EMAIL_LIMIT) {
    await c.env.LAB_KV.put(emailKey, String(emailCount + 1), { expirationTtl: RL_EMAIL_TTL_SEC });
  }

  // Подписываем в UniSender. По их API v3, double_optin=0 — слать confirmation-письмо
  // пользователю (1 — не слать; ответ поддержки 2026-06-21).
  const result = await unisenderSubscribe(c.env, {
    email,
    doubleOptin: 0,
  });

  if (!result.ok) {
    console.error('[subscribe] unisender_failed', result.error, result.code, 'email=', email);
    // Запись в KV оставили, но UniSender не принял.
    // Спец-кейсы — даём понятный ответ.
    if (result.code === 'invalid_email') {
      return c.json({ error: 'invalid_email', message: 'Email не прошёл проверку' }, 400);
    }
    return c.json(
      { error: 'subscribe_failed', message: 'Не удалось оформить подписку. Попробуйте позже.' },
      502,
    );
  }

  // devMode — UniSender не настроен, но KV запись сделали.
  if (result.devMode) {
    console.log('[subscribe:dev] uni not configured, only KV updated');
  }

  return c.json({
    ok: true,
    isNew,
    devMode: result.devMode === true,
    message: isNew
      ? 'Проверьте почту — мы отправили письмо для подтверждения подписки'
      : 'Письмо отправлено повторно',
  });
});

// ────────────────────────────────────────────────
// POST /api/unsubscribe
// Body: { email } или { token } — отписка.
//
// Если нет UniSender-конфига (dev), помечаем в KV как unsubscribed.
// ────────────────────────────────────────────────
app.post('/api/unsubscribe', async (c) => {
  let body: { email?: string };
  try {
    body = await c.req.json();
  } catch {
    return c.json({ error: 'bad_request', message: 'Нужен JSON' }, 400);
  }
  const email = (body.email ?? '').trim().toLowerCase();
  if (!email || !EMAIL_RE.test(email)) {
    return c.json({ error: 'invalid_email', message: 'Email указан неверно' }, 400);
  }

  const subKey = KV_KEYS.subscribeEmail(email);
  const existing = await c.env.LAB_KV.get(subKey);
  if (!existing) {
    return c.json({ error: 'not_found', message: 'Этот email не подписан' }, 404);
  }

  // Отписываем в UniSender
  const result = await unisenderUnsubscribe(c.env, email);

  // Помечаем в KV (в любом случае — чтобы не показывать как активного)
  const record = JSON.parse(existing);
  record.unsubscribedAt = new Date().toISOString();
  await c.env.LAB_KV.put(subKey, JSON.stringify(record));

  if (!result.ok && !result.devMode) {
    console.error('[unsubscribe] unisender_failed', result.error, 'email=', email);
    // KV обновили, но UniSender не принял. Сообщим пользователю по-человечески,
    // но 200 — он больше не в нашей базе.
  }

  return c.json({
    ok: true,
    devMode: result.devMode === true,
    message: 'Вы отписаны от рассылки',
  });
});

// GET /api/subscribers/count — для админки / счётчика в дашборде.
app.get('/api/subscribers/count', async (c) => {
  // KV не умеет count() — перебираем по prefix.
  // Для маленьких баз (<10k) это OK; для большой — отдельная страница через UniSender API.
  let count = 0;
  let cursor: string | undefined;
  // Лимит: не больше 1000 в одной странице; защита от runaway.
  for (let i = 0; i < 50; i++) {
    const page = await c.env.LAB_KV.list({
      prefix: 'subscribe:email:',
      cursor,
      limit: 1000,
    });
    for (const k of page.keys) {
      const v = await c.env.LAB_KV.get(k.name);
      if (!v) continue;
      try {
        const r = JSON.parse(v);
        if (!r.unsubscribedAt) count++;
      } catch {
        /* ignore */
      }
    }
    if (!page.list_complete) {
      cursor = page.cursor;
    } else {
      break;
    }
  }
  return c.json({ ok: true, count });
});

export default app;