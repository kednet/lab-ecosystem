/**
 * Chief Agent — TG webhook endpoint.
 * POST /api/tg/webhook — Telegram шлёт update'ы (callback_query и commands).
 *
 * Без requireToken — аутентификация через X-Telegram-Bot-Api-Secret-Token.
 * Подключается ДО requireToken в src/index.js.
 */
'use strict';

const express = require('express');
const config = require('../config');
const log = require('../util/logger').make('api.tg');
const tg = require('../tg/notify');
const store = require('../jobs/store');
const audit = require('../util/audit');
const db = require('../db/client');

const router = express.Router();

/**
 * Verify X-Telegram-Bot-Api-Secret-Token header.
 * setWebhook принимает ?secret_token=... — TG шлёт этот header всегда.
 */
function verifySecret(req, res, next) {
  if (!config.tg.webhookSecret) {
    // В dev без секрета — пропускаем
    return next();
  }
  const provided = req.headers['x-telegram-bot-api-secret-token'] || '';
  if (provided !== config.tg.webhookSecret) {
    log.warn('TG webhook: bad secret');
    return res.status(403).send('forbidden');
  }
  next();
}

/**
 * Parse update → handle.
 * Поддерживаем:
 *   callback_query с data="approve:<jobId>"|"reject:<jobId>"|"open:<jobId>"
 *   message с text, начинающимся с /status, /approvals, /cancel
 */
async function handleUpdate(update) {
  // 1) Callback query (нажатие inline-кнопки)
  if (update.callback_query) {
    const cb = update.callback_query;
    const data = cb.data || '';
    const m = /^(approve|reject|open):(.+)$/.exec(data);
    if (!m) {
      await tg.answerCallback(cb.id, 'Unknown action', true).catch(() => {});
      return;
    }
    const [, action, jobId] = m;
    if (action === 'approve') {
      const ok = store.approveJob(jobId, cb.from.username || cb.from.first_name || 'tg-user');
      if (ok) {
        await tg.answerCallback(cb.id, '✅ Approved').catch(() => {});
        audit.log({
          actor: 'tg:' + (cb.from.username || cb.from.id),
          action: 'approve_job',
          target: jobId,
          result: 'ok'
        });
      } else {
        await tg.answerCallback(cb.id, 'Cannot approve (status changed?)', true).catch(() => {});
      }
    } else if (action === 'reject') {
      const ok = store.rejectJob(jobId, 'rejected via TG');
      if (ok) {
        await tg.answerCallback(cb.id, '❌ Rejected').catch(() => {});
        audit.log({
          actor: 'tg:' + (cb.from.username || cb.from.id),
          action: 'reject_job',
          target: jobId,
          result: 'ok'
        });
      } else {
        await tg.answerCallback(cb.id, 'Cannot reject (status changed?)', true).catch(() => {});
      }
    } else if (action === 'open') {
      const job = store.getJob(jobId);
      const a = job && job.artifacts && job.artifacts[0];
      if (a) {
        await tg.answerCallback(cb.id, `📂 ${a.path}`, false).catch(() => {});
        // Шлём follow-up с путём (файл локальный на Kednet — пользователь откроет сам)
        await tg.send(
          `📂 *File path*\n\n` +
          `\`${a.path}\`\n\n` +
          (a.sizeBytes ? `Size: ${Math.round(a.sizeBytes/1024)} КБ\n` : '') +
          `Открой на Kednet через Explorer.`
        , { parseMode: 'Markdown', replyToMessageId: cb.message && cb.message.message_id }).catch(() => {});
      } else {
        await tg.answerCallback(cb.id, 'No artifact', true).catch(() => {});
      }
    }
    return;
  }

  // 2) Slash-команда
  const msg = update.message;
  if (!msg || !msg.text) return;
  const chatId = msg.chat.id;
  const text = msg.text.trim();
  const userId = msg.from && msg.from.username || (msg.from && String(msg.from.id)) || 'unknown';

  // Логируем
  db.prepare(`
    INSERT INTO tg_commands (chat_id, user_id, command, args_json, response)
    VALUES (?, ?, ?, ?, ?)
  `).run(String(chatId), userId, text.split(/\s+/)[0], JSON.stringify({ text }), null);

  if (text === '/start' || text === '/help') {
    await tg.send(
      `🤖 *Chief Agent*\n\n` +
      `Команды:\n` +
      `/status — состояние 13 агентов\n` +
      `/approvals — pending approvals\n` +
      `/jobs — последние 10 jobs\n` +
      `/cancel <jobId> — отменить running job\n` +
      `/kednet — статус Kednet-агента\n\n` +
      `Inline-кнопки на approve-push'ах работают.`
    , { parseMode: 'Markdown' });
    return;
  }
  if (text === '/status') {
    const awaiting = store.listAwaitingApprovals();
    const recent = store.listJobs({ limit: 5 });
    const kednet = require('../ws/hub').getStatus();
    const lines = [
      `*Status*\n`,
      `Kednet-агент: ${kednet.connected ? '🟢' : '🔴'} ${kednet.hostname || '—'}`,
      `Pending approvals: ${awaiting.length}`,
      `\n*Recent jobs:*`,
      ...recent.map(j => `• \`${j.id.slice(0,8)}\` ${j.agentId}/${j.actionId} → ${j.status}${j.exitCode !== null ? ' (exit ' + j.exitCode + ')' : ''}`)
    ];
    await tg.send(lines.join('\n'), { parseMode: 'Markdown' });
    return;
  }
  if (text === '/approvals') {
    const awaiting = store.listAwaitingApprovals();
    if (awaiting.length === 0) {
      await tg.send('✅ No pending approvals');
      return;
    }
    const lines = awaiting.map(j => {
      const ageMin = Math.round((Date.now() - new Date(j.createdAt + 'Z').getTime()) / 60000);
      return `• \`${j.id.slice(0,8)}\` ${j.agentId}/${j.actionId} (${(j.artifacts || []).length} files, ${ageMin}m ago)`;
    });
    await tg.send(`*Pending approvals*\n\n${lines.join('\n')}\n\nОткрой /chief/ UI для approve/reject.`, { parseMode: 'Markdown' });
    return;
  }
  if (text === '/jobs') {
    const recent = store.listJobs({ limit: 10 });
    const lines = recent.map(j =>
      `• \`${j.id.slice(0,8)}\` ${j.agentId}/${j.actionId}\n  ${j.status} exit=${j.exitCode} ${j.dryRun ? '🧪' : ''}`
    );
    await tg.send(`*Last 10 jobs*\n\n${lines.join('\n')}`, { parseMode: 'Markdown' });
    return;
  }
  if (text === '/kednet') {
    const k = require('../ws/hub').getStatus();
    if (!k.connected) {
      await tg.send('🔴 Kednet-агент OFFLINE');
      return;
    }
    await tg.send(
      `🟢 *Kednet-агент ONLINE*\n` +
      `host: \`${k.hostname}\`\n` +
      `os: \`${k.os}\`\n` +
      `skills: ${(k.skillsDetected || []).length}\n` +
      `last heartbeat: ${k.lastHeartbeatAt}`
    , { parseMode: 'Markdown' });
    return;
  }
  if (text.startsWith('/cancel ')) {
    const jobId = text.slice(8).trim();
    if (!jobId) { await tg.send('Usage: /cancel <jobId>'); return; }
    const job = store.getJob(jobId);
    if (!job) { await tg.send('Job not found'); return; }
    const ok = store.cancelJob(jobId);
    if (ok) {
      try { require('../agents/runner').cancelChild(jobId); } catch (_) {}
      try { require('../agents/remote').cancel(jobId); } catch (_) {}
      await tg.send(`✅ Cancelled \`${jobId.slice(0,8)}\``);
    } else {
      await tg.send('Cannot cancel (status not in queued/running)');
    }
    return;
  }
  // Unknown command — show /help
  await tg.send('Unknown command. Try /help');
}

router.post('/webhook', verifySecret, async (req, res) => {
  // Отвечаем TG сразу 200, обработка async
  res.status(200).send('ok');
  try {
    await handleUpdate(req.body || {});
  } catch (e) {
    log.error('handleUpdate failed', { err: e.message });
  }
});

module.exports = router;
