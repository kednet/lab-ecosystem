/**
 * Chief Agent — system endpoints (restart allowlisted services).
 *
 * GET  /api/system/services              — list units Chief controls
 * POST /api/system/restart/:service      — restart (audit logged)
 */
'use strict';

const express = require('express');
const { exec } = require('child_process');
const db = require('../db/client');
const config = require('../config');
const log = require('../util/logger').make('system');

const router = express.Router();

const ALLOWED = config.allowedServices;

function systemctl(action, unit) {
  return new Promise((resolve) => {
    exec(`systemctl ${action} ${unit}`, { timeout: 15000 }, (err, stdout, stderr) => {
      resolve({
        ok: !err,
        exitCode: err ? err.code || 1 : 0,
        stdout: (stdout || '').trim(),
        stderr: (stderr || '').trim()
      });
    });
  });
}

router.get('/system/services', async (req, res) => {
  const list = [];
  for (const name of ALLOWED) {
    const r = await systemctl('is-active', `${name}.service`);
    list.push({
      name: `${name}.service`,
      status: r.ok ? 'active' : 'inactive',
      detail: r.stderr || r.stdout
    });
  }
  res.json(list);
});

router.post('/system/restart/:service', async (req, res) => {
  const name = req.params.service.replace(/\.service$/, '');
  const actor = req.headers['x-user'] || 'anonymous';
  const reason = (req.body && req.body.reason) || '';

  // Allowlist check.
  if (!ALLOWED.has(name)) {
    db.prepare(`
      INSERT INTO audit_log (actor, action, target, params_json, result, ip, user_agent)
      VALUES (?, 'restart_service', ?, ?, 'denied', ?, ?)
    `).run(actor, `${name}.service`, JSON.stringify({ reason }), req.ip, req.headers['user-agent'] || '');
    log.warn('restart denied (allowlist)', { name, actor });
    return res.status(403).json({ error: 'service_not_allowed', service: name });
  }

  // Self-restart safety: don't allow restarting chief-agent from itself.
  if (name === 'chief-agent') {
    db.prepare(`
      INSERT INTO audit_log (actor, action, target, params_json, result, ip, user_agent)
      VALUES (?, 'restart_service', ?, ?, 'denied', ?, ?)
    `).run(actor, `${name}.service`, JSON.stringify({ reason: 'self-restart forbidden via API' }), req.ip, req.headers['user-agent'] || '');
    return res.status(403).json({ error: 'self_restart_forbidden' });
  }

  log.info('restart initiated', { name, actor, reason });
  const r = await systemctl('restart', `${name}.service`);

  db.prepare(`
    INSERT INTO audit_log (actor, action, target, params_json, result, ip, user_agent)
    VALUES (?, 'restart_service', ?, ?, ?, ?, ?)
  `).run(
    actor,
    `${name}.service`,
    JSON.stringify({ reason }),
    r.ok ? 'ok' : 'error',
    req.ip,
    req.headers['user-agent'] || ''
  );

  if (!r.ok) {
    return res.status(500).json({
      ok: false,
      service: `${name}.service`,
      exitCode: r.exitCode,
      stderr: r.stderr
    });
  }
  res.json({ ok: true, service: `${name}.service` });
});

module.exports = router;
