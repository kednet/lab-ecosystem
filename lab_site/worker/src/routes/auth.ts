import { Hono } from 'hono';
import type { Env } from '../types';
import { setAuthCode, getAuthCode, deleteAuthCode, recordFailedAttempt, ensureAuthUser, getAuthUser, getGenerationCounts } from '../lib/kv';
import { signJWT, getJWTSecret } from '../lib/jwt';
import { sendEmail, authCodeEmail } from '../lib/email';
import { requireAuth } from '../middleware/auth';

const app = new Hono<{ Bindings: Env }>();

// Простая валидация email — не пускаем мусор и попытки инъекций
const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

function generateCode(): string {
  // 6 цифр, криптографически стойкий RNG
  const buf = new Uint8Array(4);
  crypto.getRandomValues(buf);
  const n = (buf[0] << 24 | buf[1] << 16 | buf[2] << 8 | buf[3]) >>> 0;
  return String(n % 1_000_000).padStart(6, '0');
}

// ────────────────────────────────────────────────
// POST /auth/code
// Body: { email: string }
// Отправляет 6-значный код на email
// ────────────────────────────────────────────────
app.post('/auth/code', async (c) => {
  let body: { email?: string };
  try {
    body = await c.req.json();
  } catch {
    return c.json({ error: 'bad_request', message: 'Нужен JSON с полем email' }, 400);
  }

  const email = (body.email ?? '').trim().toLowerCase();
  if (!email || !EMAIL_RE.test(email) || email.length > 254) {
    return c.json({ error: 'invalid_email', message: 'Похоже, email указан неверно' }, 400);
  }

  const code = generateCode();
  await setAuthCode(c.env.LAB_KV, email, code);

  const tpl = authCodeEmail({ code, email, frontendOrigin: c.env.FRONTEND_ORIGIN });
  const result = await sendEmail(c.env, {
    to: email,
    subject: tpl.subject,
    html: tpl.html,
    text: tpl.text,
  });

  if (!result.ok) {
    return c.json({ error: 'email_send_failed', message: 'Не удалось отправить письмо. Попробуйте позже.' }, 502);
  }

  return c.json({
    ok: true,
    // В dev-режиме (без SMTP_HOST) возвращаем код в ответе для удобства тестирования
    devCode: c.env.SMTP_HOST ? undefined : code,
    expiresInSec: 600,
  });
});

// ────────────────────────────────────────────────
// POST /auth/verify
// Body: { email: string, code: string }
// Возвращает JWT-токен
// ────────────────────────────────────────────────
app.post('/auth/verify', async (c) => {
  let body: { email?: string; code?: string };
  try {
    body = await c.req.json();
  } catch {
    return c.json({ error: 'bad_request', message: 'Нужен JSON' }, 400);
  }

  const email = (body.email ?? '').trim().toLowerCase();
  const code = (body.code ?? '').trim();

  if (!email || !code) {
    return c.json({ error: 'bad_request', message: 'Нужны email и код' }, 400);
  }

  const stored = await getAuthCode(c.env.LAB_KV, email);
  if (!stored) {
    return c.json({ error: 'code_expired', message: 'Код истёк или не существует. Запросите новый.' }, 410);
  }
  if (Date.now() > stored.expiresAt) {
    await deleteAuthCode(c.env.LAB_KV, email);
    return c.json({ error: 'code_expired', message: 'Код истёк. Запросите новый.' }, 410);
  }
  if (stored.code !== code) {
    const updated = await recordFailedAttempt(c.env.LAB_KV, email);
    const remaining = updated ? Math.max(0, 5 - updated.attempts) : 0;
    return c.json({
      error: 'code_invalid',
      message: 'Неверный код.',
      attemptsRemaining: remaining,
    }, 401);
  }

  // Успех — удаляем код, создаём/получаем пользователя, выдаём JWT
  await deleteAuthCode(c.env.LAB_KV, email);
  const user = await ensureAuthUser(c.env.LAB_KV, email);
  const token = await signJWT({ sub: user.userId, email: user.email }, getJWTSecret(c.env));

  return c.json({
    ok: true,
    token,
    user: {
      email: user.email,
      userId: user.userId,
      plan: user.plan,
      subscriptionStatus: user.subscriptionStatus,
      subscriptionExpiresAt: user.subscriptionExpiresAt,
      generationsLimit: user.generationsLimit,
      wishesLimit: user.wishesLimit,
    },
  });
});

// ────────────────────────────────────────────────
// GET /auth/me
// Защищён: возвращает текущего пользователя + квоты
// ────────────────────────────────────────────────
app.get('/auth/me', requireAuth, async (c) => {
  const user = c.get('user')!;
  const counts = await getGenerationCounts(c.env.LAB_KV, user.userId);
  return c.json({
    user: {
      email: user.email,
      userId: user.userId,
      plan: user.plan,
      subscriptionStatus: user.subscriptionStatus,
      subscriptionExpiresAt: user.subscriptionExpiresAt,
      generationsLimit: user.generationsLimit,
      wishesLimit: user.wishesLimit,
    },
    generations: {
      usedThisMonth: counts.month,
      usedToday: counts.day,
      limitThisMonth: user.generationsLimit,
      limitPerDay: user.plan === 'free' ? 1 : user.plan === 'month' ? 5 : 100,
    },
  });
});

// ────────────────────────────────────────────────
// POST /auth/logout
// Просто для симметрии — JWT stateless, на бэке нечего инвалидировать.
// Клиент сам удаляет токен из localStorage.
// ────────────────────────────────────────────────
app.post('/auth/logout', (c) => c.json({ ok: true }));

export default app;
