/**
 * Обёртка над SMTP (Яндекс 360) — отправка писем через nodemailer.
 *
 * Прод: SMTP_HOST=smtp.yandex.ru, SMTP_PORT=465 (SSL) или 587 (STARTTLS).
 * Dev: если SMTP_* не заданы — логируем письмо в консоль.
 */

import nodemailer from 'nodemailer';

export interface SendEmailParams {
  to: string;
  subject: string;
  html: string;
  text?: string;
}

export interface SmtpEnv {
  SMTP_HOST?: string;
  SMTP_PORT?: string;
  SMTP_USER?: string;
  SMTP_PASS?: string;
  EMAIL_FROM?: string;
  FRONTEND_ORIGIN: string;
  // legacy — если остался, игнорируем
  RESEND_API_KEY?: string;
}

let cachedTransport: nodemailer.Transporter | null = null;
let lastTransportKey = '';

function getTransport(env: SmtpEnv): nodemailer.Transporter | null {
  if (!env.SMTP_HOST || !env.SMTP_USER || !env.SMTP_PASS) return null;
  const key = `${env.SMTP_HOST}|${env.SMTP_PORT ?? '465'}|${env.SMTP_USER}`;
  if (cachedTransport && lastTransportKey === key) return cachedTransport;
  const port = parseInt(env.SMTP_PORT ?? '465', 10);
  const secure = port === 465; // 465 = SSL, 587 = STARTTLS
  cachedTransport = nodemailer.createTransport({
    host: env.SMTP_HOST,
    port,
    secure,
    auth: { user: env.SMTP_USER, pass: env.SMTP_PASS },
    // Яндекс требует валидный EHLO/HELO с A-записью
    tls: { servername: env.SMTP_HOST },
  });
  lastTransportKey = key;
  return cachedTransport;
}

export async function sendEmail(env: SmtpEnv, params: SendEmailParams): Promise<{ ok: boolean; id?: string; error?: string }> {
  const transport = getTransport(env);

  // Dev-режим: SMTP не настроен — логируем письмо, не отправляем.
  if (!transport) {
    console.log('[email:dev]', params.subject, '→', params.to);
    console.log('[email:dev]', params.text ?? params.html.replace(/<[^>]+>/g, '').slice(0, 200));
    return { ok: true, id: 'dev-mode' };
  }

  const from = env.EMAIL_FROM ?? `ЛАБОРАТОРИЯ ЖЕЛАНИЙ <${env.SMTP_USER}>`;

  try {
    const info = await transport.sendMail({
      from,
      to: params.to,
      subject: params.subject,
      html: params.html,
      text: params.text,
    });
    return { ok: true, id: info.messageId };
  } catch (err) {
    const msg = err instanceof Error ? err.message : String(err);
    console.error('[email:smtp:error]', msg);
    return { ok: false, error: msg };
  }
}

// ────────────────────────────────────────────────
// Шаблоны
// ────────────────────────────────────────────────

export function authCodeEmail(params: { code: string; email: string; frontendOrigin: string }): { subject: string; html: string; text: string } {
  const subject = 'Код входа в ЛАБОРАТОРИЮ ЖЕЛАНИЙ';
  const text = `Ваш код входа: ${params.code}\n\nОн действителен 10 минут.\n\nЕсли вы не запрашивали код, просто проигнорируйте это письмо.`;
  const html = `<!doctype html>
<html><body style="margin:0;padding:0;background:#fff1f2;font-family:'Helvetica Neue',Arial,sans-serif;color:#1f0a14;">
<table width="100%" cellpadding="0" cellspacing="0" style="background:#fff1f2;padding:40px 20px;">
  <tr><td align="center">
    <table width="480" cellpadding="0" cellspacing="0" style="background:#ffffff;border-radius:18px;border:1px solid rgba(225,29,72,0.18);overflow:hidden;">
      <tr><td style="background:linear-gradient(135deg,#e11d48 0%,#881337 100%);padding:32px 32px 24px;text-align:center;">
        <h1 style="margin:0;font-size:18px;font-weight:700;color:#ffffff;letter-spacing:0.04em;">ЛАБОРАТОРИЯ ЖЕЛАНИЙ</h1>
      </td></tr>
      <tr><td style="padding:36px 32px 16px;text-align:center;">
        <p style="margin:0 0 12px;font-size:14px;color:#6b3a4a;letter-spacing:0.04em;text-transform:uppercase;">Ваш код входа</p>
        <div style="font-family:'Courier New',monospace;font-size:36px;font-weight:700;letter-spacing:0.4em;color:#881337;padding:20px 0;background:#fff5f7;border-radius:14px;margin:0 0 20px;">${params.code}</div>
        <p style="margin:0 0 8px;font-size:14px;line-height:1.5;color:#1f0a14;">Код действителен <strong>10 минут</strong>.</p>
        <p style="margin:0;font-size:13px;line-height:1.5;color:#6b3a4a;">Если вы не запрашивали код — просто проигнорируйте это письмо.</p>
      </td></tr>
      <tr><td style="padding:24px 32px 32px;text-align:center;">
        <a href="${params.frontendOrigin}/wish-map/" style="display:inline-block;background:#e11d48;color:#ffffff;text-decoration:none;padding:12px 24px;border-radius:999px;font-size:14px;font-weight:600;">Открыть карту желаний</a>
      </td></tr>
    </table>
    <p style="margin:24px 0 0;font-size:12px;color:#6b3a4a;">© 2024–2026 ЛАБОРАТОРИЯ ЖЕЛАНИЙ</p>
  </td></tr>
</table>
</body></html>`;
  return { subject, html, text };
}

export function subscriptionSuccessEmail(params: { plan: string; expiresAt: string; frontendOrigin: string }): { subject: string; html: string; text: string } {
  const subject = 'Спасибо за подписку! 🎉';
  const planName = params.plan === 'year' ? 'Год (5 900 ₽)' : params.plan === 'half' ? 'Полгода (2 990 ₽)' : 'Месяц (590 ₽)';
  const expiresDate = new Date(params.expiresAt).toLocaleDateString('ru-RU', { day: 'numeric', month: 'long', year: 'numeric' });
  const text = `Спасибо за подписку «${planName}»!\n\nДоступ активен до ${expiresDate}.\n\nОткрыть карту желаний: ${params.frontendOrigin}/wish-map/`;
  const html = `<!doctype html>
<html><body style="margin:0;padding:0;background:#fff1f2;font-family:'Helvetica Neue',Arial,sans-serif;color:#1f0a14;">
<table width="100%" cellpadding="0" cellspacing="0" style="background:#fff1f2;padding:40px 20px;">
  <tr><td align="center">
    <table width="480" cellpadding="0" cellspacing="0" style="background:#ffffff;border-radius:18px;border:1px solid rgba(225,29,72,0.18);overflow:hidden;">
      <tr><td style="background:linear-gradient(135deg,#e11d48 0%,#881337 100%);padding:32px;text-align:center;">
        <h1 style="margin:0;font-size:24px;color:#ffffff;">Спасибо за подписку! 🎉</h1>
      </td></tr>
      <tr><td style="padding:32px;text-align:center;">
        <p style="margin:0 0 16px;font-size:16px;">Тариф: <strong>${planName}</strong></p>
        <p style="margin:0 0 24px;font-size:14px;color:#6b3a4a;">Доступ активен до <strong>${expiresDate}</strong></p>
        <a href="${params.frontendOrigin}/wish-map/" style="display:inline-block;background:#e11d48;color:#ffffff;text-decoration:none;padding:14px 28px;border-radius:999px;font-size:15px;font-weight:600;">Открыть карту желаний</a>
      </td></tr>
    </table>
  </td></tr>
</table>
</body></html>`;
  return { subject, html, text };
}

export function newsletterWelcomeEmail(params: { frontendOrigin: string; unsubscribeLink: string }): { subject: string; html: string; text: string } {
  const subject = 'Добро пожаловать в «Мини-практики недели» 💌';
  const text = `Спасибо, что подписались на мини-практики Лаборатории желаний!

Раз в неделю — короткое упражнение на 15 минут, чтобы ваши «я хочу» превращались в «я есть».

📌 Что вас ждёт:
• 1 мини-практика по книге из нашей библиотеки
• 1 вопрос для самоанализа
• 0 воды и «мотивационной» болтовни

📅 Первое письмо — в ближайшее воскресенье.

Пока можно заглянуть в библиотеку конспектов:
${params.frontendOrigin}/library/

Если письма вам больше не нужны — просто перейдите по ссылке:
${params.unsubscribeLink}

С теплом,
Команда Лаборатории желаний
${params.frontendOrigin}`;
  const html = `<!doctype html>
<html><body style="margin:0;padding:0;background:#fff1f2;font-family:'Helvetica Neue',Arial,sans-serif;color:#1f0a14;">
<table width="100%" cellpadding="0" cellspacing="0" style="background:#fff1f2;padding:40px 20px;">
  <tr><td align="center">
    <table width="480" cellpadding="0" cellspacing="0" style="background:#ffffff;border-radius:18px;border:1px solid rgba(225,29,72,0.18);overflow:hidden;">
      <tr><td style="background:linear-gradient(135deg,#e11d48 0%,#881337 100%);padding:32px 32px 24px;text-align:center;">
        <p style="margin:0 0 8px;font-size:12px;letter-spacing:0.18em;color:rgba(255,255,255,0.85);text-transform:uppercase;">ЛАБОРАТОРИЯ ЖЕЛАНИЙ</p>
        <h1 style="margin:0;font-size:22px;color:#ffffff;">Добро пожаловать! 💌</h1>
      </td></tr>
      <tr><td style="padding:36px 32px 8px;">
        <p style="margin:0 0 16px;font-size:16px;line-height:1.55;">Спасибо, что подписались на <strong>мини-практики недели</strong>.</p>
        <p style="margin:0 0 24px;font-size:15px;line-height:1.55;color:#1f0a14;">Раз в неделю — короткое упражнение на 15 минут, чтобы ваши «я хочу» превращались в «я есть».</p>
      </td></tr>
      <tr><td style="padding:0 32px 24px;">
        <p style="margin:0 0 12px;font-size:13px;color:#6b3a4a;letter-spacing:0.04em;text-transform:uppercase;">Что вас ждёт</p>
        <table width="100%" cellpadding="0" cellspacing="0" style="background:#fff5f7;border-radius:14px;padding:18px 20px;">
          <tr><td style="padding:6px 0;font-size:14px;line-height:1.5;">📖 1 мини-практика по книге из библиотеки</td></tr>
          <tr><td style="padding:6px 0;font-size:14px;line-height:1.5;">❓ 1 вопрос для самоанализа</td></tr>
          <tr><td style="padding:6px 0;font-size:14px;line-height:1.5;">🚫 0 воды и мотивационной болтовни</td></tr>
        </table>
      </td></tr>
      <tr><td style="padding:0 32px 32px;text-align:center;">
        <p style="margin:0 0 18px;font-size:14px;color:#6b3a4a;">📅 Первое письмо — в ближайшее воскресенье.</p>
        <a href="${params.frontendOrigin}/library/" style="display:inline-block;background:#e11d48;color:#ffffff;text-decoration:none;padding:14px 28px;border-radius:999px;font-size:15px;font-weight:600;">Заглянуть в библиотеку</a>
      </td></tr>
      <tr><td style="padding:20px 32px;border-top:1px solid rgba(225,29,72,0.12);text-align:center;">
        <p style="margin:0;font-size:12px;line-height:1.5;color:#6b3a4a;">Письма больше не нужны? <a href="${params.unsubscribeLink}" style="color:#881337;text-decoration:underline;">Отписаться в один клик</a></p>
      </td></tr>
    </table>
    <p style="margin:24px 0 0;font-size:12px;color:#6b3a4a;text-align:center;">© 2024–2026 ЛАБОРАТОРИЯ ЖЕЛАНИЙ</p>
  </td></tr>
</table>
</body></html>`;
  return { subject, html, text };
}
