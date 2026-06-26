/**
 * pay.ts — роуты для приёма оплаты через ЮKassa.
 *
 *  POST /api/pay/create        — создать платёж, получить redirectUrl
 *  POST /api/pay/webhook       — приём событий от ЮKassa
 *  GET  /api/members/access    — обменять magic-link токен на cookie
 *  GET  /api/members/me        — проверить активную сессию (для /members/ в Astro)
 *  POST /api/members/logout    — удалить cookie
 *
 * Поток:
 *   1) /api/pay/create: валидация email + consent + honeypot + rate-limit
 *      → createPayment в ЮKassa → сохраняем в pay_payments (pending)
 *      → возвращаем confirmationUrl (или mockUrl)
 *   2) /api/pay/webhook: верификация подписи
 *      → payment.succeeded → markPaid + upsertSubscription + sendMagicLink
 *      → payment.canceled → markCanceled
 *   3) /api/members/access?token=XXX: находим SHA256(token) в KV
 *      → ставим cookie member_session с expires=valid_until
 *      → редирект на /members/
 */

import { Hono } from 'hono';
import type { Env } from '../types';
import { KV_KEYS } from '../lib/kv';
import {
  PLANS,
  createPayment as dbCreatePayment,
  setYookassaId,
  findPaymentById,
  findPaymentByYkId,
  markPaid,
  markCanceled,
  upsertSubscription,
  getSubscription,
  isAccessActive,
  type Plan,
} from '../lib/pay-db';
import { createPayment as ykCreatePayment, verifyWebhookSignature } from '../lib/pay-yookassa';
import {
  newMagicToken,
  storeMagicToken,
  consumeMagicToken,
  sendMagicLink,
} from '../lib/email-magic-link';

const app = new Hono<{ Bindings: Env }>();

// Простая валидация email — как в /api/subscribe
const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

// Лимиты антиспама (5/час с одного IP — как у /api/subscribe)
const RL_IP_LIMIT = 5;
const RL_IP_TTL_SEC = 3600;

function clientIp(c: { req: { raw: Request } }): string {
  const r = c.req.raw;
  return (
    r.headers.get('cf-connecting-ip') ??
    (r.headers.get('x-forwarded-for') ?? '').split(',')[0].trim() ??
    r.headers.get('x-real-ip') ??
    'unknown'
  );
}

// UUID v4 без node:crypto (crypto.randomUUID есть в Node 19+)
function uuid(): string {
  return crypto.randomUUID();
}

// ────────────────────────────────────────────────
// POST /api/pay/create
// ────────────────────────────────────────────────
app.post('/api/pay/create', async (c) => {
  let body: { plan?: string; email?: string; consent?: boolean; hp?: string };
  try {
    body = await c.req.json();
  } catch {
    return c.json({ error: 'bad_request', message: 'Нужен JSON' }, 400);
  }

  // Honeypot
  if (body.hp && body.hp.trim() !== '') {
    console.log('[pay:create] honeypot triggered, ip=', clientIp(c));
    return c.json({ ok: true });
  }

  const plan = body.plan as Plan;
  if (plan !== 'month' && plan !== 'year') {
    return c.json({ error: 'bad_plan', message: 'Тариф должен быть month или year' }, 400);
  }

  const email = (body.email ?? '').trim().toLowerCase();
  if (!email || !EMAIL_RE.test(email) || email.length > 254) {
    return c.json({ error: 'invalid_email', message: 'Похоже, email указан неверно' }, 400);
  }
  if (body.consent !== true) {
    return c.json({ error: 'consent_required', message: 'Нужно согласие на обработку email' }, 400);
  }

  // Rate-limit по IP (5/час)
  const ip = clientIp(c);
  const ipKey = KV_KEYS.subscribeRlIp(`pay:${ip}`);
  const ipCountRaw = await c.env.LAB_KV.get(ipKey);
  const ipCount = parseInt(ipCountRaw ?? '0', 10);
  if (ipCount >= RL_IP_LIMIT) {
    return c.json({ error: 'rate_limited', message: 'Слишком много попыток. Попробуйте через час.' }, 429);
  }
  await c.env.LAB_KV.put(ipKey, String(ipCount + 1), { expirationTtl: RL_IP_TTL_SEC });

  // Создаём заказ
  const orderId = uuid();
  const planMeta = PLANS[plan];
  const origin = c.env.FRONTEND_ORIGIN.split(',')[0]?.trim() || 'https://app.pulab.online';
  const returnUrl = `${origin}/pay/success/?order_id=${orderId}`;
  const cancelUrl = `${origin}/pay/cancel/?order_id=${orderId}`;

  dbCreatePayment({
    id: orderId,
    plan,
    email,
    amount: planMeta.amount,
    return_url: returnUrl,
    created_at: Date.now(),
  });

  // Создаём платёж в ЮKassa
  const yk = await ykCreatePayment(c.env, {
    amount: planMeta.amount,
    description: planMeta.description,
    email,
    metadataKey: orderId,
    returnUrl,
  });

  if (!yk.ok) {
    console.error('[pay:create] yookassa_failed', yk.error, yk.code);
    return c.json({ error: 'pay_create_failed', message: 'Не удалось создать платёж. Попробуйте позже.' }, 502);
  }

  // Сохраняем yookassa_payment_id в нашу запись
  setYookassaId(orderId, yk.yookassaPaymentId);

  return c.json({
    ok: true,
    orderId,
    redirectUrl: yk.confirmationUrl,
    cancelUrl,
    mock: yk.mock === true,
  });
});

// ────────────────────────────────────────────────
// POST /api/pay/webhook
// ────────────────────────────────────────────────
app.post('/api/pay/webhook', async (c) => {
  const bodyText = await c.req.text();
  const signature = c.req.header('Signature') ?? c.req.header('signature');

  const ok = await verifyWebhookSignature(c.env, bodyText, signature);
  if (!ok) {
    console.warn('[pay:webhook] invalid_signature');
    return c.json({ error: 'invalid_signature' }, 400);
  }

  let event: { event?: string; object?: { id?: string; status?: string; metadata?: { order_id?: string } } };
  try {
    event = JSON.parse(bodyText);
  } catch {
    return c.json({ error: 'bad_json' }, 400);
  }

  const evType = event.event;
  const obj = event.object ?? {};
  const ykId = obj.id ?? '';
  const orderId = obj.metadata?.order_id ?? '';

  console.log('[pay:webhook]', evType, 'ykId=', ykId, 'orderId=', orderId, 'status=', obj.status);

  // Найти нашу запись
  const payment = findPaymentByYkId(ykId) ?? (orderId ? findPaymentById(orderId) : null);
  if (!payment) {
    console.warn('[pay:webhook] payment_not_found');
    // Возвращаем 200 — иначе ЮKassa будет ретраить, а мы не сможем помочь
    return c.json({ ok: true, ignored: true });
  }

  if (evType === 'payment.succeeded' && obj.status === 'succeeded') {
    if (payment.status !== 'paid') {
      markPaid(payment.id);
      const sub = upsertSubscription(payment.email, payment.plan, payment.id);
      // Отправляем magic-link (не блокируем ответ вебхука при ошибке — ЮKassa не любит долгие ответы)
      sendMagicLink(c.env, payment.email, payment.plan)
        .then((r) => {
          if (r.ok) console.log('[pay:webhook] magic_link_sent', payment.email);
          else console.error('[pay:webhook] magic_link_failed', r.error);
        })
        .catch((e) => console.error('[pay:webhook] magic_link_threw', e));
      console.log('[pay:webhook] payment_paid', payment.id, 'sub_valid_until=', sub.valid_until);
    }
  } else if (evType === 'payment.canceled' || obj.status === 'canceled') {
    if (payment.status !== 'canceled') {
      markCanceled(payment.id);
      console.log('[pay:webhook] payment_canceled', payment.id);
    }
  } else {
    // Другие события (refund.succeeded и т.п.) — игнорируем, но возвращаем 200
    console.log('[pay:webhook] event_ignored', evType);
  }

  return c.json({ ok: true });
});

// ────────────────────────────────────────────────
// GET /api/members/access?token=XXX
//
// Меняет одноразовый токен на долгоиграющую cookie.
// Cookie member_session живёт до конца подписки.
// ────────────────────────────────────────────────
app.get('/api/members/access', async (c) => {
  const token = c.req.query('token');
  if (!token || token.length < 16) {
    return c.json({ error: 'no_token', message: 'Нет токена' }, 400);
  }

  const hashBuf = await crypto.subtle.digest('SHA-256', new TextEncoder().encode(token));
  const tokenHash = Array.from(new Uint8Array(hashBuf))
    .map((b) => b.toString(16).padStart(2, '0'))
    .join('');

  const payload = await consumeMagicToken(c.env.LAB_KV, tokenHash);
  if (!payload) {
    // Не валидный — редирект на /members/?need_token=1 с инструкцией
    const origin = c.env.FRONTEND_ORIGIN.split(',')[0]?.trim() || 'https://app.pulab.online';
    return c.redirect(`${origin}/members/?need_token=1`, 302);
  }

  // Проверяем, что подписка ещё активна
  if (payload.validUntil < Date.now()) {
    return c.redirect(`${(c.env.FRONTEND_ORIGIN.split(',')[0] || 'https://app.pulab.online').trim()}/members/?expired=1`, 302);
  }

  // Ставим cookie — domain-wide, чтобы кука была видна и на app., и на api.
  // Без Domain кука привязана к origin, на который пришёл verify — и если юзер
  // входит через app.pulab.ru, то api.pulab.ru её не видит (gate ломается).
  // Domain=.pulab.ru покрывает оба наших поддомена + голый pulab.ru.
  const expiresAtSec = Math.floor(payload.validUntil / 1000);
  const cookie = [
    `member_session=${payload.email}`,
    `Path=/`,
    `Domain=.pulab.ru`,
    `Expires=${new Date(expiresAtSec * 1000).toUTCString()}`,
    `HttpOnly`,
    `SameSite=Lax`,
  ].join('; ');

  const origin = c.env.FRONTEND_ORIGIN.split(',')[0]?.trim() || 'https://app.pulab.online';
  return new Response(null, {
    status: 302,
    headers: {
      'Location': `${origin}/members/`,
      'Set-Cookie': cookie,
    },
  });
});

// ────────────────────────────────────────────────
// GET /api/members/me
// Возвращает состояние подписки текущего пользователя (по cookie).
// Astro-страница /members/ дёргает это при загрузке.
// ────────────────────────────────────────────────
app.get('/api/members/me', async (c) => {
  const cookieHeader = c.req.header('Cookie') ?? '';
  const m = cookieHeader.match(/member_session=([^;]+)/);
  const email = m ? decodeURIComponent(m[1]) : null;

  if (!email) {
    return c.json({ ok: true, authenticated: false });
  }

  const sub = getSubscription(email);
  const active = isAccessActive(email);

  return c.json({
    ok: true,
    authenticated: true,
    email,
    subscription: sub
      ? {
          plan: sub.plan,
          planName: PLANS[sub.plan].name,
          validUntil: sub.valid_until,
          validUntilIso: new Date(sub.valid_until).toISOString(),
          status: sub.status,
          active,
        }
      : null,
  });
});

// ────────────────────────────────────────────────
// POST /api/members/logout
// Удаляет cookie.
// ────────────────────────────────────────────────
app.post('/api/members/logout', async (c) => {
  const cookie = 'member_session=; Path=/; Expires=Thu, 01 Jan 1970 00:00:00 GMT; HttpOnly; SameSite=Lax';
  return new Response(null, {
    status: 204,
    headers: { 'Set-Cookie': cookie },
  });
});

export default app;
