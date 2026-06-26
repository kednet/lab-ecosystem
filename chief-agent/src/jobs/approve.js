/**
 * Chief Agent — approve / reject pipeline.
 *
 * Когда job завершается с exitCode=0 И есть artifacts с kind∈{image,audio,video,json},
 * job переводится в status='awaiting_approval' и Chief отправляет TG-push
 * с inline-кнопками ✅/📂/❌. Callback data: approve:<jobId> / reject:<jobId> / open:<jobId>.
 *
 * Approve/reject делает POST /api/jobs/:id/(approve|reject) (см. api/jobs.js).
 * Эти endpoints обновляют status и пишут в audit_log.
 */
'use strict';

const store = require('./store');
const log = require('../util/logger').make('jobs.approve');
const tg = require('../tg/notify');
const events = require('../util/events');
const config = require('../config');

const db = require('../db/client');

const RELEVANT_KINDS = new Set(['image', 'audio', 'video', 'json']);

/**
 * Подписаться на 'job.exited' из ws/hub (remote jobs).
 * Native jobs идут через queue.finalize (там тоже вызывается).
 */
function attachEventHandlers() {
  events.on('job.exited', ({ jobId }) => {
    try {
      const job = store.getJob(jobId);
      if (!job) return;
      if (job.status !== 'completed') return;
      if (!job.artifacts || job.artifacts.length === 0) return;
      if (!job.artifacts.some(a => a && a.kind && RELEVANT_KINDS.has(a.kind))) return;

      const ok = store.setAwaitingApproval(jobId);
      if (!ok) return;

      onAwaitingApproval({
        job: store.getJob(jobId),
        agentId: job.agentId,
        actionId: job.actionId
      }).catch(err => log.error('onAwaitingApproval failed', { jobId, err: err.message }));
    } catch (e) {
      log.error('job.exited handler error', { err: e.message });
    }
  });
}

/**
 * Вызывается из queue.finalize (native) и из attachEventHandlers (remote).
 * Проверяет, нужно ли перевести job в awaiting_approval + шлёт TG-push.
 */
async function onAwaitingApproval({ job, agentId, actionId }) {
  if (!job || job.status !== 'awaiting_approval') return;

  const msg = await tg.sendApprovalRequest({ job, agentId, actionId });

  db.prepare(`
    INSERT INTO approvals (job_id, artifact_count, tg_message_id, tg_chat_id)
    VALUES (?, ?, ?, ?)
    ON CONFLICT(job_id) DO UPDATE SET
      artifact_count = excluded.artifact_count,
      tg_message_id  = excluded.tg_message_id,
      tg_chat_id     = excluded.tg_chat_id
  `).run(job.id, job.artifacts.length, msg && msg.message_id, config.tg.chatId);

  events.emit('approval.created', { jobId: job.id, agentId, artifacts: job.artifacts });
  log.info('awaiting_approval push sent', { jobId: job.id, agentId, artifacts: job.artifacts.length });
}

/**
 * Periodic re-ping для зависших approvals (напомнить + 24h auto-reject).
 */
async function tick() {
  const awaiting = store.listAwaitingApprovals();
  const now = Date.now();
  for (const job of awaiting) {
    const ageSec = (now - new Date(job.createdAt).getTime()) / 1000;

    if (ageSec > config.tg.approvalTimeoutSec) {
      store.rejectJob(job.id, 'auto-rejected: timeout');
      events.emit('approval.rejected', { jobId: job.id, reason: 'timeout' });
      log.warn('approval auto-rejected (timeout)', { jobId: job.id, ageSec });
      continue;
    }

    if (ageSec > 0 && ageSec % config.tg.reminderSec < 60) {
      const row = db.prepare(`SELECT reminder_count FROM approvals WHERE job_id = ?`).get(job.id);
      if (row && row.reminder_count < 3) {
        db.prepare(`UPDATE approvals SET reminder_count = reminder_count + 1 WHERE job_id = ?`).run(job.id);
        await tg.sendApprovalRequest({
          job,
          agentId: job.agentId,
          actionId: job.actionId,
          isReminder: true,
          reminderCount: (row.reminder_count || 0) + 1
        }).catch(() => {});
      }
    }
  }
}

let intervalHandle = null;
function start(intervalSec = 300) {
  if (intervalHandle) return;
  attachEventHandlers();
  intervalHandle = setInterval(() => {
    tick().catch(err => log.warn('approve.tick error', { err: err.message }));
  }, intervalSec * 1000);
  log.info('approve tick started', { intervalSec });
}

function stop() {
  if (intervalHandle) { clearInterval(intervalHandle); intervalHandle = null; }
}

module.exports = { onAwaitingApproval, tick, start, stop, attachEventHandlers };

