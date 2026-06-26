/**
 * Chief Agent — action runner endpoint.
 *
 * POST /api/agents/:id/run
 *   body: { actionId, params, dryRun?, triggeredBy?, triggeredByUser? }
 *   returns: { jobId, status: 'queued' }
 */
'use strict';

const express = require('express');
const queue = require('../jobs/queue');
const runner = require('../agents/runner');
const { findAction } = require('../agents/sync');
const db = require('../db/client');
const log = require('../util/logger').make('actions');

const router = express.Router();

function validateParams(params, schema) {
  if (!Array.isArray(schema)) return [];
  const errors = [];
  for (const p of schema) {
    if (p.required && (params[p.name] === undefined || params[p.name] === '')) {
      errors.push(`param '${p.name}' is required`);
    }
    if (params[p.name] !== undefined && p.type === 'enum' && p.options) {
      if (!p.options.includes(params[p.name])) {
        errors.push(`param '${p.name}' must be one of: ${p.options.join(', ')}`);
      }
    }
    if (params[p.name] !== undefined && p.type === 'integer') {
      if (!Number.isInteger(params[p.name])) {
        errors.push(`param '${p.name}' must be integer`);
      }
    }
  }
  return errors;
}

router.post('/agents/:id/run', (req, res) => {
  const { id } = req.params;
  const { actionId, params = {}, dryRun = false, triggeredBy = 'web', triggeredByUser } = req.body || {};

  if (!actionId) return res.status(400).json({ error: 'actionId_required' });

  const { agent, action } = findAction(id, actionId);
  if (!agent) return res.status(404).json({ error: 'agent_not_found' });
  if (!agent.enabled) return res.status(403).json({ error: 'agent_disabled' });
  if (!action) return res.status(404).json({ error: 'action_not_found' });

  if (action.isSystemAction) {
    return res.status(400).json({
      error: 'use_system_endpoint',
      message: `Action '${actionId}' must be invoked via POST /api/system/restart/${agent.id}`
    });
  }

  if (dryRun && !action.dryRunSupported) {
    return res.status(400).json({
      error: 'dry_run_not_supported',
      message: `Action '${actionId}' does not support --dry-run`
    });
  }

  const errors = validateParams(params, action.params);
  if (errors.length) {
    return res.status(400).json({ error: 'invalid_params', details: errors });
  }

  // Audit log.
  db.prepare(`
    INSERT INTO audit_log (actor, action, target, params_json, result, ip, user_agent)
    VALUES (?, 'run_action', ?, ?, 'ok', ?, ?)
  `).run(
    triggeredByUser || req.headers['x-user'] || 'anonymous',
    `${id}/${actionId}`,
    JSON.stringify({ params, dryRun }),
    req.ip,
    req.headers['user-agent'] || ''
  );

  try {
    const runnerFn = runner.buildRunner(agent, action);
    const jobId = queue.schedule({
      agentId: id,
      actionId,
      params,
      dryRun,
      triggeredBy,
      triggeredByUser: triggeredByUser || req.headers['x-user'] || null,
      runner: runnerFn,
      agent,
      transport: agent.type
    });
    log.info('action scheduled', { agentId: id, actionId, jobId, dryRun, transport: agent.type });
    res.status(202).json({ jobId, status: 'queued' });
  } catch (err) {
    if (err.code === 'agent_busy') {
      return res.status(409).json({ error: 'agent_busy', message: err.message });
    }
    log.error('schedule failed', { err: err.message });
    res.status(500).json({ error: 'schedule_failed', message: err.message });
  }
});

module.exports = router;
