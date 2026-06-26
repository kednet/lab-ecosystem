/**
 * Chief Agent — agents endpoints.
 *
 * GET   /api/agents                — list with status from heartbeats
 * GET   /api/agents/:id            — details + heartbeat + actions
 * GET   /api/agents/:id/actions    — actions with params schema
 * POST  /api/agents                — create + scaffold (admin)
 * PUT   /api/agents/:id            — update (admin)
 * DELETE /api/agents/:id           — delete (admin, только если disabled)
 */
'use strict';

const express = require('express');
const db = require('../db/client');
const REGISTRY = require('../agents/registry');
const { findAgent } = require('../agents/sync');
const mw = require('./middleware');
const audit = require('../util/audit');
const log = require('../util/logger').make('api.agents');

const router = express.Router();

function getHeartbeat(agentId) {
  return db.prepare('SELECT * FROM heartbeats WHERE agent_id = ?').get(agentId) || null;
}

function getActions(agentId) {
  return db.prepare('SELECT * FROM actions WHERE agent_id = ? ORDER BY id').all(agentId);
}

function presentAgent(a) {
  const hb = getHeartbeat(a.id);
  return {
    id: a.id,
    displayName: a.displayName,
    description: a.description,
    type: a.type,
    enabled: a.enabled,
    status: hb ? hb.status : 'unknown',
    lastHeartbeatAt: hb ? hb.last_check_at : null,
    consecutiveFailures: hb ? hb.consecutive_failures : 0,
    actionsCount: (a.actions || []).length
  };
}

// ─────────────────────────────────────────────────────
// Public reads
// ─────────────────────────────────────────────────────

router.get('/agents', (req, res) => {
  const agents = REGISTRY.map(presentAgent);
  res.json(agents);
});

router.get('/agents/:id', (req, res) => {
  const a = findAgent(req.params.id);
  if (!a) return res.status(404).json({ error: 'agent_not_found' });
  const hb = getHeartbeat(a.id);
  res.json({
    ...presentAgent(a),
    metadata: a.metadata,
    heartbeatDetail: hb ? JSON.parse(hb.detail_json || '{}') : null,
    actions: getActions(a.id).map((row) => ({
      id: row.id,
      displayName: row.display_name,
      params: JSON.parse(row.params_json || '[]'),
      dryRunSupported: !!row.dry_run_supported,
      estimatedDurationSec: row.estimated_duration_sec
    }))
  });
});

router.get('/agents/:id/actions', (req, res) => {
  const a = findAgent(req.params.id);
  if (!a) return res.status(404).json({ error: 'agent_not_found' });
  res.json(getActions(req.params.id).map((row) => ({
    id: row.id,
    displayName: row.display_name,
    params: JSON.parse(row.params_json || '[]'),
    dryRunSupported: !!row.dry_run_supported,
    estimatedDurationSec: row.estimated_duration_sec
  })));
});

// ─────────────────────────────────────────────────────
// Admin CRUD
// ─────────────────────────────────────────────────────

/**
 * POST /api/agents
 * Body: { id, displayName, description, type, metadata, actions[], scaffold? }
 * - Валидирует
 * - Если scaffold=true и type='remote' — отправляет Kednet-агенту создать папку
 * - Добавляет запись в registry (in-memory + sync в SQLite)
 */
router.post('/agents', mw.requireAdmin, async (req, res) => {
  const a = req.body;
  if (!a || typeof a !== 'object') return res.status(400).json({ error: 'bad_body' });

  const required = ['id', 'displayName', 'type'];
  for (const k of required) {
    if (!a[k] || typeof a[k] !== 'string') return res.status(400).json({ error: 'missing_field', field: k });
  }
  if (!/^[a-z][a-z0-9_]{1,40}$/.test(a.id)) {
    return res.status(400).json({ error: 'bad_id', message: 'id must match /^[a-z][a-z0-9_]{1,40}$/' });
  }
  if (!['subprocess', 'http', 'remote'].includes(a.type)) {
    return res.status(400).json({ error: 'bad_type', message: 'type must be subprocess|http|remote' });
  }
  if (REGISTRY.find(r => r.id === a.id)) {
    return res.status(409).json({ error: 'agent_exists', id: a.id });
  }

  const meta = a.metadata || {};
  if (a.type === 'remote' && !meta.cwd) {
    return res.status(400).json({ error: 'missing_cwd', message: 'remote agents require metadata.cwd' });
  }

  // Scaffold
  let scaffolded = null;
  if (a.scaffold && a.type === 'remote') {
    try {
      const scaffold = require('../agents/scaffold');
      scaffolded = await scaffold.createOnKednet({
        agentId: a.id,
        cwd: meta.cwd,
        templateType: 'remote',
        scriptsEntry: meta.scriptsEntry,
        envKeys: meta.envKeys || []
      });
    } catch (e) {
      return res.status(500).json({ error: 'scaffold_failed', message: e.message });
    }
  }

  // Add to in-memory registry
  const newAgent = {
    id: a.id,
    displayName: a.displayName,
    description: a.description || '',
    type: a.type,
    transport: a.type === 'remote' ? 'ws' : (a.type === 'http' ? 'http' : 'subprocess'),
    healthcheck: a.healthcheck || (a.type === 'remote' ? 'ws' : (a.type === 'http' ? 'http' : 'state')),
    enabled: a.enabled !== false,
    metadata: meta,
    actions: Array.isArray(a.actions) ? a.actions : []
  };
  REGISTRY.push(newAgent);

  // Sync to SQLite (нужно для restart-recovery)
  try {
    const { syncAll } = require('../agents/sync');
    syncAll();
  } catch (e) {
    log.warn('sync failed', { err: e.message });
  }

  audit.log({
    actor: req.headers['x-user'] || 'admin',
    action: 'create_agent',
    target: a.id,
    params: JSON.stringify({ type: a.type, scaffolded }),
    result: 'ok',
    ip: req.ip,
    userAgent: req.headers['user-agent']
  });

  res.status(201).json({ ok: true, id: a.id, scaffolded });
});

router.put('/agents/:id', mw.requireAdmin, (req, res) => {
  const a = REGISTRY.find(r => r.id === req.params.id);
  if (!a) return res.status(404).json({ error: 'agent_not_found' });
  const updates = req.body || {};
  const allowed = ['displayName', 'description', 'enabled', 'metadata', 'actions'];
  for (const k of Object.keys(updates)) {
    if (allowed.includes(k)) a[k] = updates[k];
  }
  try {
    const { syncAll } = require('../agents/sync');
    syncAll();
  } catch (_) {}
  audit.log({
    actor: req.headers['x-user'] || 'admin',
    action: 'update_agent',
    target: req.params.id,
    params: JSON.stringify(updates),
    result: 'ok',
    ip: req.ip,
    userAgent: req.headers['user-agent']
  });
  res.json({ ok: true, id: a.id });
});

router.delete('/agents/:id', mw.requireAdmin, (req, res) => {
  const idx = REGISTRY.findIndex(r => r.id === req.params.id);
  if (idx < 0) return res.status(404).json({ error: 'agent_not_found' });
  const a = REGISTRY[idx];
  if (a.enabled) {
    return res.status(409).json({ error: 'agent_enabled', message: 'Disable the agent first (PUT enabled:false)' });
  }
  REGISTRY.splice(idx, 1);
  try {
    const { syncAll } = require('../agents/sync');
    syncAll();
  } catch (_) {}
  audit.log({
    actor: req.headers['x-user'] || 'admin',
    action: 'delete_agent',
    target: req.params.id,
    result: 'ok',
    ip: req.ip,
    userAgent: req.headers['user-agent']
  });
  res.json({ ok: true, id: req.params.id });
});

module.exports = router;