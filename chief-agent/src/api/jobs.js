/**
 * Chief Agent — jobs log endpoint.
 *
 * GET    /api/jobs?limit=&agent=&status=       — log
 * GET    /api/jobs/:id                         — detail
 * GET    /api/jobs/:id/artifacts               — artifact list
 * POST   /api/jobs/:id/cancel                  — cancel by SIGTERM
 * POST   /api/jobs/:id/approve                 — approve awaiting_approval → completed
 * POST   /api/jobs/:id/reject                  — reject awaiting_approval → cancelled
 * GET    /api/ws/status                        — Kednet-агент connection status
 */
'use strict';

const express = require('express');
const store = require('../jobs/store');
const queue = require('../jobs/queue');
const runner = require('../agents/runner');
const wsHub = require('../ws/hub');
const events = require('../util/events');
const log = require('../util/logger').make('api.jobs');
const audit = require('../util/audit');
const db = require('../db/client');

const router = express.Router();

// ============================================================
// /api/jobs
// ============================================================

router.get('/jobs', (req, res) => {
  const { limit, agent, status } = req.query;
  const jobs = store.listJobs({
    limit: limit ? parseInt(limit, 10) : 20,
    agent: agent || null,
    status: status || null
  });
  res.json(jobs);
});

router.get('/jobs/:id', (req, res) => {
  const job = store.getJob(req.params.id);
  if (!job) return res.status(404).json({ error: 'job_not_found' });
  res.json(job);
});

router.get('/jobs/:id/artifacts', (req, res) => {
  const job = store.getJob(req.params.id);
  if (!job) return res.status(404).json({ error: 'job_not_found' });
  res.json({ jobId: job.id, artifacts: job.artifacts || [] });
});

router.post('/jobs/:id/cancel', (req, res) => {
  const job = store.getJob(req.params.id);
  if (!job) return res.status(404).json({ error: 'job_not_found' });
  if (!['queued', 'running'].includes(job.status)) {
    return res.status(400).json({
      error: 'not_cancellable',
      message: `Job is in status '${job.status}', cannot cancel`
    });
  }
  const killed = runner.cancelChild(req.params.id);
  const flipped = queue.cancel(req.params.id);
  audit.log({
    actor: req.headers['x-user'] || 'kfigh',
    action: 'cancel_job',
    target: req.params.id,
    result: 'ok',
    ip: req.ip,
    userAgent: req.headers['user-agent']
  });
  res.json({ ok: true, killed, flipped, jobId: req.params.id });
});

// ============================================================
// Approve / Reject
// ============================================================

router.post('/jobs/:id/approve', (req, res) => {
  const job = store.getJob(req.params.id);
  if (!job) return res.status(404).json({ error: 'job_not_found' });
  if (job.status !== 'awaiting_approval') {
    return res.status(400).json({
      error: 'not_awaiting_approval',
      message: `Job is in status '${job.status}'`
    });
  }
  const approvedBy = req.headers['x-user'] || req.body.approvedBy || 'kfigh';
  const ok = store.approveJob(req.params.id, approvedBy);
  if (!ok) return res.status(409).json({ error: 'approval_failed' });

  audit.log({
    actor: approvedBy,
    action: 'approve_job',
    target: req.params.id,
    params: JSON.stringify({ agentId: job.agentId, actionId: job.actionId, artifacts: (job.artifacts || []).length }),
    result: 'ok',
    ip: req.ip,
    userAgent: req.headers['user-agent']
  });

  events.emit('approval.approved', { jobId: job.id, approvedBy });
  log.info('job approved', { jobId: job.id, approvedBy });

  // TG-уведомление (редактируем исходное сообщение — убираем кнопки)
  try {
    const tg = require('../tg/notify');
    const row = db.prepare(`SELECT tg_message_id, tg_chat_id FROM approvals WHERE job_id = ?`).get(job.id);
    if (row && row.tg_message_id) {
      tg.editMessage(row.tg_message_id,
        `✅ Approved by *${approvedBy}*\n\n` +
        `Job: \`${job.id.slice(0,8)}\`\n` +
        `Агент: *${job.agentId}* / \`${job.actionId}\``,
        { parseMode: 'Markdown', replyMarkup: { inline_keyboard: [] } }
      ).catch(() => {});
    }
  } catch (_) {}

  res.json({ ok: true, jobId: job.id, status: 'completed', approvedBy });
});

router.post('/jobs/:id/reject', (req, res) => {
  const job = store.getJob(req.params.id);
  if (!job) return res.status(404).json({ error: 'job_not_found' });
  if (job.status !== 'awaiting_approval') {
    return res.status(400).json({
      error: 'not_awaiting_approval',
      message: `Job is in status '${job.status}'`
    });
  }
  const reason = req.body.reason || 'rejected by user';
  const rejectedBy = req.headers['x-user'] || 'kfigh';
  const ok = store.rejectJob(req.params.id, reason);
  if (!ok) return res.status(409).json({ error: 'reject_failed' });

  audit.log({
    actor: rejectedBy,
    action: 'reject_job',
    target: req.params.id,
    params: JSON.stringify({ reason, agentId: job.agentId, actionId: job.actionId }),
    result: 'ok',
    ip: req.ip,
    userAgent: req.headers['user-agent']
  });

  events.emit('approval.rejected', { jobId: job.id, reason });
  log.info('job rejected', { jobId: job.id, reason });

  try {
    const tg = require('../tg/notify');
    const row = db.prepare(`SELECT tg_message_id FROM approvals WHERE job_id = ?`).get(job.id);
    if (row && row.tg_message_id) {
      tg.editMessage(row.tg_message_id,
        `❌ Rejected by *${rejectedBy}*\n\n` +
        `Job: \`${job.id.slice(0,8)}\`\n` +
        `reason: ${reason}`,
        { parseMode: 'Markdown', replyMarkup: { inline_keyboard: [] } }
      ).catch(() => {});
    }
  } catch (_) {}

  res.json({ ok: true, jobId: job.id, status: 'cancelled', reason });
});

// ============================================================
// Kednet-агент status
// ============================================================

router.get('/ws/status', (req, res) => {
  const status = wsHub.getStatus();
  res.json(status);
});

module.exports = router;
