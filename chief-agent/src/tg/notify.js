/**
 * Chief Agent — Telegram notifications.
 * Uses fetch() directly (Node 18+). No dependencies.
 * No-op if TG_BOT_TOKEN or TG_CHAT_ID is missing.
 *
 * Inline-кнопки для approval flow.
 */
'use strict';

const log = require('../util/logger').make('tg');

const TOKEN = process.env.TG_BOT_TOKEN;
const CHAT_ID = process.env.TG_CHAT_ID;
const ENABLED = Boolean(TOKEN && CHAT_ID);

if (!ENABLED) {
  log.warn('TG notifications disabled (TG_BOT_TOKEN or TG_CHAT_ID missing)');
}

const API = TOKEN ? `https://api.telegram.org/bot${TOKEN}` : null;

async function apiPost(method, body) {
  if (!ENABLED) return { ok: false, reason: 'disabled' };
  try {
    const r = await fetch(`${API}/${method}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body)
    });
    const json = await r.json().catch(() => ({}));
    return json;
  } catch (e) {
    log.error(`TG ${method} network error`, { err: e.message });
    return { ok: false, description: e.message };
  }
}

/**
 * Send a plain-text message. Failures are logged but never throw.
 * @returns {Promise<{ok:boolean, message_id?:number}>}
 */
async function send(text, opts = {}) {
  if (!ENABLED) {
    log.debug('send() skipped (disabled)', { len: text.length });
    return { ok: false };
  }
  const body = {
    chat_id: CHAT_ID,
    text,
    disable_web_page_preview: true,
    parse_mode: opts.parseMode || undefined
  };
  if (opts.replyMarkup) body.reply_markup = opts.replyMarkup;
  if (opts.replyToMessageId) body.reply_to_message_id = opts.replyToMessageId;
  if (opts.messageThreadId) body.message_thread_id = opts.messageThreadId;
  const r = await apiPost('sendMessage', body);
  if (!r.ok) {
    log.error('TG send failed', { desc: r.description });
    return { ok: false, error: r.description };
  }
  return { ok: true, message_id: r.result?.message_id };
}

/**
 * Edit existing message (inline-кнопки после approve/reject — убрать кнопки).
 */
async function editMessage(messageId, text, opts = {}) {
  if (!ENABLED) return { ok: false };
  const body = {
    chat_id: CHAT_ID,
    message_id: messageId,
    text,
    parse_mode: opts.parseMode || undefined
  };
  if (opts.replyMarkup !== undefined) body.reply_markup = opts.replyMarkup;
  const r = await apiPost('editMessageText', body);
  if (!r.ok) log.warn('TG editMessage failed', { desc: r.description });
  return r;
}

/**
 * Answer inline callback query (снимает loading у кнопки).
 */
async function answerCallback(callbackQueryId, text, showAlert = false) {
  if (!ENABLED) return { ok: false };
  return apiPost('answerCallbackQuery', {
    callback_query_id: callbackQueryId,
    text,
    show_alert: showAlert
  });
}

/**
 * Push об ожидании approval (с inline-кнопками).
 */
async function sendApprovalRequest({ job, agentId, actionId, isReminder, reminderCount }) {
  if (!ENABLED) return { ok: false };

  const artifacts = job.artifacts || [];
  const artifactLines = artifacts.slice(0, 5).map((a, i) => {
    const sz = a.sizeBytes ? ` (${Math.round(a.sizeBytes/1024)} КБ)` : '';
    return `${i+1}. ${a.kind}: \`${a.path}\`${sz}`;
  }).join('\n');
  const more = artifacts.length > 5 ? `\n…и ещё ${artifacts.length - 5}` : '';

  const text =
    `⏳ *Approval required*\n` +
    `\n` +
    `Агент: *${agentId}* / \`${actionId}\`\n` +
    `Job: \`${job.id.slice(0,8)}\`\n` +
    `Артефакты: ${artifacts.length} шт.\n` +
    `\n` +
    artifactLines + more +
    (isReminder ? `\n\n_(напоминание #${reminderCount})_` : '');

  const replyMarkup = {
    inline_keyboard: [
      [
        { text: '✅ Опубликовать', callback_data: `approve:${job.id}` },
        { text: '📂 Открыть',     callback_data: `open:${job.id}` }
      ],
      [
        { text: '❌ Отклонить', callback_data: `reject:${job.id}` }
      ]
    ]
  };

  return send(text, { parseMode: 'Markdown', replyMarkup });
}

/**
 * Алерт о failed job.
 */
async function sendFailedJob({ job, agentId, actionId }) {
  if (!ENABLED) return { ok: false };
  const excerpt = (job.stderr || job.stdout || '').split('\n').slice(-5).join('\n');
  const text =
    `❌ *Chief: job failed*\n` +
    `\n` +
    `Агент: *${agentId}* / \`${actionId}\`\n` +
    `Job: \`${job.id.slice(0,8)}\`\n` +
    `exitCode: \`${job.exitCode}\`\n` +
    (job.errorMessage ? `error: ${job.errorMessage.slice(0, 200)}\n` : '') +
    (excerpt ? `\n\`\`\`\n${excerpt.slice(0, 600)}\n\`\`\`\n` : '');
  return send(text, { parseMode: 'Markdown' });
}

/**
 * Алерт о Kednet-агенте offline.
 */
async function sendKednetOffline({ reason, hostname }) {
  if (!ENABLED) return { ok: false };
  return send(
    `🔌 *Chief: Kednet-агент OFFLINE*\n` +
    `host: \`${hostname || 'unknown'}\`\n` +
    `reason: ${reason}\n` +
    `\n` +
    `Машина уснула / нет сети. Действия с 9 remote-скиллами заблокированы.`
  , { parseMode: 'Markdown' });
}

/**
 * Алерт о Kednet-агенте online (только при reconnect после offline).
 */
async function sendKednetOnline({ hostname, os, skillsDetected }) {
  if (!ENABLED) return { ok: false };
  return send(
    `🟢 *Chief: Kednet-агент ONLINE*\n` +
    `host: \`${hostname}\`\n` +
    `os: \`${os}\`\n` +
    `skills: ${skillsDetected}`
  , { parseMode: 'Markdown' });
}

module.exports = {
  send, editMessage, answerCallback,
  sendApprovalRequest, sendFailedJob,
  sendKednetOffline, sendKednetOnline,
  enabled: ENABLED
};
