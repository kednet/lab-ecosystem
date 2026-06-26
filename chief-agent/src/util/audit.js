/**
 * Chief Agent — audit log helper.
 */
'use strict';

const db = require('../db/client');

const STMT = {
  insert: db.prepare(`
    INSERT INTO audit_log (ts, actor, action, target, params_json, result, ip, user_agent)
    VALUES (datetime('now'), @actor, @action, @target, @params_json, @result, @ip, @user_agent)
  `),
  list: db.prepare(`
    SELECT * FROM audit_log
    WHERE (@actor IS NULL OR actor = @actor)
    ORDER BY ts DESC LIMIT @limit
  `)
};

function log({ actor = 'kfigh', action, target = null, params = null, result = 'ok', ip = null, userAgent = null } = {}) {
  if (!action) return;
  try {
    STMT.insert.run({
      actor,
      action,
      target,
      params_json: params && typeof params !== 'string' ? JSON.stringify(params) : params,
      result,
      ip,
      user_agent: userAgent
    });
  } catch (_) {}
}

function list({ limit = 50, actor = null } = {}) {
  const rows = STMT.list.all({
    limit: Math.min(Math.max(parseInt(limit, 10) || 50, 1), 500),
    actor
  });
  return rows.map(r => ({
    id: r.id,
    ts: r.ts,
    actor: r.actor,
    action: r.action,
    target: r.target,
    params: r.params_json ? safeJson(r.params_json) : null,
    result: r.result,
    ip: r.ip,
    userAgent: r.user_agent
  }));
}

function safeJson(s) {
  try { return JSON.parse(s); } catch (_) { return s; }
}

module.exports = { log, list };
