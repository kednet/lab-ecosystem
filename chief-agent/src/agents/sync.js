/**
 * Chief Agent — sync registry.js into SQLite.
 * Called on every boot. Idempotent: enabled flag, metadata_json, actions all upserted.
 */
'use strict';

const db = require('../db/client');
const REGISTRY = require('./registry');

const STMT = {
  upsertAgent: db.prepare(`
    INSERT INTO agents (id, display_name, description, type, enabled, metadata_json, updated_at)
    VALUES (@id, @display_name, @description, @type, @enabled, @metadata_json, datetime('now'))
    ON CONFLICT(id) DO UPDATE SET
      display_name = excluded.display_name,
      description  = excluded.description,
      type         = excluded.type,
      enabled      = excluded.enabled,
      metadata_json = excluded.metadata_json,
      updated_at   = datetime('now')
  `),
  upsertAction: db.prepare(`
    INSERT INTO actions (id, agent_id, display_name, params_json, dry_run_supported, estimated_duration_sec)
    VALUES (@id, @agent_id, @display_name, @params_json, @dry_run_supported, @estimated_duration_sec)
    -- Multiple agents may share an action.id (e.g. "generate" in both
    -- content_ideas and image_skill). Primary key on (id) alone would
    -- reject the second insert. We use ON CONFLICT(id) DO UPDATE and
    -- rebind agent_id. UNIQUE(agent_id, id) guards against duplicates.
    ON CONFLICT(id) DO UPDATE SET
      agent_id                = excluded.agent_id,
      display_name            = excluded.display_name,
      params_json             = excluded.params_json,
      dry_run_supported       = excluded.dry_run_supported,
      estimated_duration_sec  = excluded.estimated_duration_sec
  `),
  deleteAgent: db.prepare(`DELETE FROM agents WHERE id = ?`),
  deleteActionsForAgent: db.prepare(`DELETE FROM actions WHERE agent_id = ?`),
  getAction: db.prepare(`SELECT * FROM actions WHERE agent_id = ? AND id = ?`),
  listAllActions: db.prepare(`SELECT * FROM actions WHERE agent_id = ?`)
};

function syncAll() {
  const tx = db.transaction(() => {
    const seen = new Set();
    for (const a of REGISTRY) {
      STMT.upsertAgent.run({
        id: a.id,
        display_name: a.displayName,
        description: a.description || null,
        type: a.type,
        enabled: a.enabled ? 1 : 0,
        metadata_json: JSON.stringify(a.metadata || {})
      });
      // Replace actions for this agent (delete + insert is simplest & correct).
      STMT.deleteActionsForAgent.run(a.id);
      for (const act of (a.actions || [])) {
        STMT.upsertAction.run({
          id: act.id,
          agent_id: a.id,
          display_name: act.displayName,
          params_json: JSON.stringify(act.params || []),
          dry_run_supported: act.dryRunSupported ? 1 : 0,
          estimated_duration_sec: act.estimatedDurationSec || 60
        });
      }
      seen.add(a.id);
    }
    // Drop agents that disappeared from registry.
    const rows = db.prepare('SELECT id FROM agents').all();
    for (const r of rows) {
      if (!seen.has(r.id)) STMT.deleteAgent.run(r.id);
    }
  });
  tx();
}

function findAgent(id) {
  return REGISTRY.find((a) => a.id === id) || null;
}

function findAction(agentId, actionId) {
  const agent = findAgent(agentId);
  if (!agent) return { agent: null, action: null };
  const action = (agent.actions || []).find((x) => x.id === actionId) || null;
  return { agent, action };
}

module.exports = { syncAll, findAgent, findAction };
