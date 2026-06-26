/**
 * email-magic-link.ts — шаблон письма "Доступ к клубу открыт".
 *
 * Используется после успешной оплаты ЮKassa — отправляем письмо со ссылкой
 * /members/?token=XXX для входа в закрытый раздел.
 *
 * Токен:
 *   - 32 случайных байта → base64url → 43 символа
 *   - в KV (member:magic:{sha256}) хранится только SHA256 от токена
 *   - TTL = до конца подписки (но не больше 400 дней — лимит KV TTL)
 *   - Одноразовый: после первого использования заменяется на cookie member_session
 *
 * ВНИМАНИЕ: в MVP мы НЕ связываем magic-link с AuthUser (kfigh выбрала "только по email").
 * Если в будущем kfigh захочет привязать к /auth/ — добавим миграцию, обновляющую AuthUser.plan.
 */

import { sendEmail } from './email';
import type { Plan } from './pay-db';

const TOKEN_TTL_SEC_MAX = 400 * 24 * 60 * 60; // 400 дней (лимит KV TTL)

/**
 * Генерирует случайный токен (43 символа base64url из 32 байт).
 * Возвращает сам токен (для ссылки в письме) и его SHA256 (для ключа в KV).
 */
export async function newMagicToken(): Promise<{ token: string; tokenHash: string }> {
  const bytes = new Uint8Array(32);
  crypto.getRandomValues(bytes);
  const token = base64url(bytes);
  const hashBuf = await crypto.subtle.digest('SHA-256', new TextEncoder().encode(token));
  const tokenHash = Array.from(new Uint8Array(hashBuf))
    .map((b) => b.toString(16).padStart(2, '0'))
    .join('');
  return { token, tokenHash };
}

function base64url(bytes: Uint8Array): string {
  const b64 = btoa(String.fromCharCode(...bytes));
  return b64.replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
}

// ────────────────────────────────────────────────
// Хранение токенов в KV
// ────────────────────────────────────────────────

export interface MagicTokenPayload {
  email: string;
  plan: Plan;
  validUntil: number; // epoch ms — копируем из подписки
  createdAt: number;
  usedAt: number | null;
}

export async function storeMagicToken(
  kv: { put: (k: string, v: string, opts?: { expirationTtl?: number }) => Promise<void> },
  tokenHash: string,
  payload: MagicTokenPayload,
): Promise<void> {
  const ttl = Math.max(60, Math.min(TOKEN_TTL_SEC_MAX, Math.floor((payload.validUntil - Date.now()) / 1000)));
  await kv.put(`member:magic:${tokenHash}`, JSON.stringify(payload), { expirationTtl: ttl });
}

export async function consumeMagicToken(
  kv: { get: (k: string) => Promise<string | null>; delete: (k: string) => Promise<void> },
  tokenHash: string,
): Promise<MagicTokenPayload | null> {
  const raw = await kv.get(`member:magic:${tokenHash}`);
  if (!raw) return null;
  const payload = JSON.parse(raw) as MagicTokenPayload;
  // Помечаем использованным (но НЕ удаляем — на случай повторного клика по ссылке).
  // payload.usedAt не обновляем в KV (это ок — если ссылку переиспользуют, куки всё равно живёт).
  return payload;
}

// ────────────────────────────────────────────────
// Письмо
// ────────────────────────────────────────────────

export function magicLinkEmail(params: {
  email: string;
  plan: Plan;
  token: string;
  frontendOrigin: string;
}): { subject: string; html: string; text: string } {
  const planLabel = params.plan === 'year' ? 'Год (4 990 ₽)' : 'Месяц (590 ₽)';
  const link = `${params.frontendOrigin}/members/?token=${params.token}`;
  const subject = 'Доступ к клубу «ЛАБОРАТОРИЯ ЖЕЛАНИЙ» открыт ✨';
  const text =
    `Спасибо за оплату! Тариф: ${planLabel}.\n\n` +
    `Чтобы войти в клуб, перейдите по ссылке (одноразовая, действует до конца подписки):\n${link}\n\n` +
    `Ссылка работает в любом браузере. После первого входа мы запомним вас на этом устройстве.\n\n` +
    `Если вы не оформляли подписку — просто проигнорируйте это письмо.\n\n` +
    `С теплом,\nКоманда Лаборатории желаний`;
  const html = `<!doctype html>
<html><body style="margin:0;padding:0;background:#fff1f2;font-family:'Helvetica Neue',Arial,sans-serif;color:#1f0a14;">
<table width="100%" cellpadding="0" cellspacing="0" style="background:#fff1f2;padding:40px 20px;">
  <tr><td align="center">
    <table width="480" cellpadding="0" cellspacing="0" style="background:#ffffff;border-radius:18px;border:1px solid rgba(225,29,72,0.18);overflow:hidden;">
      <tr><td style="background:linear-gradient(135deg,#e11d48 0%,#881337 100%);padding:32px 32px 24px;text-align:center;">
        <p style="margin:0 0 8px;font-size:12px;letter-spacing:0.18em;color:rgba(255,255,255,0.85);text-transform:uppercase;">ЛАБОРАТОРИЯ ЖЕЛАНИЙ</p>
        <h1 style="margin:0;font-size:22px;color:#ffffff;">Доступ к клубу открыт ✨</h1>
      </td></tr>
      <tr><td style="padding:36px 32px 8px;text-align:center;">
        <p style="margin:0 0 12px;font-size:16px;line-height:1.55;">Спасибо за оплату тарифа <strong>${planLabel}</strong>.</p>
        <p style="margin:0;font-size:14px;line-height:1.55;color:#6b3a4a;">Нажмите кнопку ниже, чтобы войти в клуб. Ссылка одноразовая и действует до конца подписки.</p>
      </td></tr>
      <tr><td style="padding:24px 32px 8px;text-align:center;">
        <a href="${link}" style="display:inline-block;background:#e11d48;color:#ffffff;text-decoration:none;padding:14px 28px;border-radius:999px;font-size:15px;font-weight:600;">Войти в клуб</a>
      </td></tr>
      <tr><td style="padding:16px 32px 24px;text-align:center;">
        <p style="margin:0;font-size:12px;line-height:1.5;color:#6b3a4a;">Если кнопка не работает — скопируйте ссылку:<br><a href="${link}" style="color:#881337;word-break:break-all;">${link}</a></p>
      </td></tr>
      <tr><td style="padding:20px 32px;border-top:1px solid rgba(225,29,72,0.12);text-align:center;">
        <p style="margin:0;font-size:12px;line-height:1.5;color:#6b3a4a;">Если вы не оформляли подписку — просто проигнорируйте это письмо.</p>
      </td></tr>
    </table>
    <p style="margin:24px 0 0;font-size:12px;color:#6b3a4a;text-align:center;">© 2024–2026 ЛАБОРАТОРИЯ ЖЕЛАНИЙ</p>
  </td></tr>
</table>
</body></html>`;
  return { subject, html, text };
}

// ────────────────────────────────────────────────
// Отправка
// ────────────────────────────────────────────────

export async function sendMagicLink(
  env: {
    SMTP_HOST?: string;
    SMTP_PORT?: string;
    SMTP_USER?: string;
    SMTP_PASS?: string;
    EMAIL_FROM?: string;
    FRONTEND_ORIGIN: string;
    LAB_KV: any;
  },
  email: string,
  plan: Plan,
): Promise<{ ok: boolean; token?: string; error?: string }> {
  // 1) Генерируем токен
  const { token, tokenHash } = await newMagicToken();

  // 2) Получаем валидную подписку для расчёта TTL
  const { getSubscription } = await import('./pay-db');
  const sub = getSubscription(email);
  const validUntil = sub?.valid_until ?? Date.now() + 30 * 24 * 60 * 60 * 1000;

  // 3) Сохраняем в KV (TTL = до конца подписки)
  await storeMagicToken(env.LAB_KV, tokenHash, {
    email: email.toLowerCase().trim(),
    plan,
    validUntil,
    createdAt: Date.now(),
    usedAt: null,
  });

  // 4) Отправляем письмо
  const origin = env.FRONTEND_ORIGIN.split(',')[0]?.trim() || 'https://app.pulab.online';
  const tmpl = magicLinkEmail({ email, plan, token, frontendOrigin: origin });
  const result = await sendEmail(env, {
    to: email,
    subject: tmpl.subject,
    html: tmpl.html,
    text: tmpl.text,
  });

  if (!result.ok) {
    return { ok: false, error: result.error };
  }
  return { ok: true, token };
}
