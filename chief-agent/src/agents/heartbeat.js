/**
 * Chief Agent — heartbeat loop.
 *
 * Every CHIEF_HEARTBEAT_INTERVAL seconds:
 *   1. For each agent, run its healthcheck (systemd | http | state | ws).
 *   2. Upsert into heartbeats table.
 *   3. If a previously-healthy agent becomes unhealthy, send TG alert
 *      (rate-limited: once per 15 min per agent).
 *
 * v2.0:
 *   - 'ws' healthcheck — для remote-агентов на Kednet.
 *     Смотрит kednet_agent.last_heartbeat_at.
 *     < 60s online, 60-300s degraded, > 300s offline, > 900s offline+TG alert.
 */
'use strict';

const { exec } = require('child_process');
const fs = require('fs');
const db = require('../db/client');
const REGISTRY = require('./registry');
const log = require('../util/logger').make('heartbeat');
const tg = require('../tg/notify');
const config = require('../config');
const events = require('../util/events');

const ALERT_COOLDOWN_MS = 15 * 60 * 1000;
const lastAlertAt = new Map(); // agentId → timestamp
const lastKednetAlert = { at: 0, wasOnline: false };

const STMT = {
  upsert: db.prepare(`
    INSERT INTO heartbeats (agent_id, status, last_check_at, detail_json, consecutive_failures)
    VALUES (@agent_id, @status, datetime('now'), @detail_json, @consecutive_failures)
    ON CONFLICT(agent_id) DO UPDATE SET
      status = excluded.status,
      last_check_at = excluded.last_check_at,
      detail_json = excluded.detail_json,
      consecutive_failures = excluded.consecutive_failures
  `)
};

// ============================================================
// Healthcheck implementations
// ============================================================

function checkSystemd(unit) {
  return new Promise((resolve) => {
    exec(`systemctl is-active ${unit}`, { timeout: 5000 }, (err, stdout, stderr) => {
      const s = (stdout || '').trim();
      const healthy = s === 'active';
      resolve({
        status: healthy ? 'online' : 'offline',
        detail: { systemd: s || 'unknown', raw: stderr ? stderr.trim() : null },
        consecutiveFailures: healthy ? 0 : null
      });
    });
  });
}

async function checkHttp(healthUrl, baseUrl) {
  const url = new URL(healthUrl, baseUrl).toString();
  try {
    const r = await fetch(url, { signal: AbortSignal.timeout(5000) });
    const healthy = r.ok;
    let detail = { http: r.status };
    if (!healthy) detail.error = `HTTP ${r.status}`;
    return {
      status: healthy ? 'online' : 'degraded',
      detail,
      consecutiveFailures: healthy ? 0 : null
    };
  } catch (err) {
    return {
      status: 'offline',
      detail: { error: err.message },
      consecutiveFailures: null
    };
  }
}

async function checkState(stateFilePath) {
  if (!stateFilePath) {
    return { status: 'unknown', detail: { reason: 'no stateFile in metadata' }, consecutiveFailures: null };
  }
  try {
    const st = fs.statSync(stateFilePath);
    const ageDays = (Date.now() - st.mtimeMs) / (1000 * 60 * 60 * 24);
    let status = 'online';
    if (ageDays > 30) status = 'degraded';
    if (ageDays > 90) status = 'offline';
    return {
      status,
      detail: { path: stateFilePath, ageDays: Math.round(ageDays), sizeBytes: st.size },
      consecutiveFailures: status === 'online' ? 0 : null
    };
  } catch (err) {
    return {
      status: 'unknown',
      detail: { path: stateFilePath, error: err.code || err.message },
      consecutiveFailures: null
    };
  }
}

/**
 * WS healthcheck: проверяет kednet_agent.last_heartbeat_at.
 * Тот же singleton row — все remote-агенты наследуют состояние Kednet-агента.
 */
function checkWs() {
  try {
    const row = db.prepare(`SELECT connected, last_heartbeat_at, hostname FROM kednet_agent WHERE id=1`).get();
    if (!row || !row.connected) {
      return {
        status: 'offline',
        detail: { reason: 'kednet not connected' },
        consecutiveFailures: null
      };
    }
    if (!row.last_heartbeat_at) {
      return {
        status: 'degraded',
        detail: { reason: 'connected but no heartbeat yet', hostname: row.hostname },
        consecutiveFailures: null
      };
    }
    const ageSec = (Date.now() - new Date(row.last_heartbeat_at + 'Z').getTime()) / 1000;
    let status;
    if (ageSec < 60) status = 'online';
    else if (ageSec < 300) status = 'degraded';
    else status = 'offline';
    return {
      status,
      detail: { hostname: row.hostname, ageSec: Math.round(ageSec) },
      consecutiveFailures: status === 'online' ? 0 : null
    };
  } catch (e) {
    return { status: 'unknown', detail: { error: e.message }, consecutiveFailures: null };
  }
}

// ============================================================
// Loop
// ============================================================

async function checkOne(agent) {
  if (!agent.enabled) {
    return { agentId: agent.id, status: 'disabled', detail: { reason: 'enabled=false' }, consecutiveFailures: 0 };
  }

  const hc = agent.healthcheck;
  let res;
  try {
    if (hc === 'systemd') {
      res = await checkSystemd(agent.metadata.systemdUnit);
    } else if (hc === 'http') {
      const healthPath = agent.metadata.healthUrl || '/health';
      res = await checkHttp(healthPath, agent.metadata.endpoint);
    } else if (hc === 'state') {
      res = await checkState(agent.metadata.stateFile);
    } else if (hc === 'ws') {
      res = checkWs();
    } else {
      res = { status: 'unknown', detail: { reason: `unknown healthcheck: ${hc}` }, consecutiveFailures: 0 };
    }
  } catch (err) {
    res = { status: 'offline', detail: { error: err.message }, consecutiveFailures: null };
  }

  if (res.consecutiveFailures === null) {
    res.consecutiveFailures = 1;
    const prev = db.prepare('SELECT consecutive_failures FROM heartbeats WHERE agent_id = ?').get(agent.id);
    if (prev && prev.consecutive_failures > 0) {
      res.consecutiveFailures = prev.consecutive_failures + 1;
    }
  }

  STMT.upsert.run({
    agent_id: agent.id,
    status: res.status,
    detail_json: JSON.stringify(res.detail || {}),
    consecutive_failures: res.consecutiveFailures || 0
  });

  return { agentId: agent.id, status: res.status, detail: res.detail };
}

async function heartbeatTick() {
  const results = await Promise.allSettled(REGISTRY.map(checkOne));
  const healthy = [];
  const unhealthy = [];
  for (const r of results) {
    if (r.status !== 'fulfilled') continue;
    const { agentId, status } = r.value;
    if (status === 'online') healthy.push(agentId);
    else unhealthy.push({ agentId, status, detail: r.value.detail });
  }

  log.info('tick', { online: healthy.length, unhealthy: unhealthy.length });

  // Per-agent TG alerts.
  const now = Date.now();
  for (const u of unhealthy) {
    const last = lastAlertAt.get(u.agentId) || 0;
    if (now - last < ALERT_COOLDOWN_MS) continue;
    lastAlertAt.set(u.agentId, now);
    tg.send(
      `🚨 Chief: ${u.agentId} → ${u.status.toUpperCase()}\n` +
      `detail: ${JSON.stringify(u.detail || {}).slice(0, 300)}`
    ).catch(() => {});
    log.warn('agent unhealthy', { agentId: u.agentId, status: u.status });
  }

  // Kednet-агент transition online ↔ offline.
  const kednetRow = db.prepare(`SELECT connected, hostname FROM kednet_agent WHERE id=1`).get();
  const isOnline = Boolean(kednetRow && kednetRow.connected);
  if (!isOnline && lastKednetAlert.wasOnline) {
    // Was online, now offline.
    if (now - lastKednetAlert.at > ALERT_COOLDOWN_MS) {
      lastKednetAlert.at = now;
      tg.sendKednetOffline({
        reason: 'connection closed',
        hostname: kednetRow && kednetRow.hostname
      }).catch(() => {});
    }
  } else if (isOnline && !lastKednetAlert.wasOnline) {
    // Just came back online.
    if (now - lastKednetAlert.at > 60 * 1000) {  // анти-спам 1 мин
      lastKednetAlert.at = now;
      const detail = db.prepare(`SELECT skills_detected_json FROM kednet_agent WHERE id=1`).get();
      let skills = [];
      try { skills = detail ? JSON.parse(detail.skills_detected_json) : []; } catch (_) {}
      tg.sendKednetOnline({
        hostname: kednetRow.hostname,
        os: kednetRow.os || 'unknown',
        skillsDetected: (skills || []).length
      }).catch(() => {});
    }
  }
  lastKednetAlert.wasOnline = isOnline;
}

let interval = null;

function start() {
  if (interval) return;
  log.info('starting heartbeat loop', { intervalSec: config.heartbeatSec });
  heartbeatTick().catch((err) => log.error('first tick failed', { err: err.message }));
  interval = setInterval(() => {
    heartbeatTick().catch((err) => log.error('tick failed', { err: err.message }));
  }, config.heartbeatSec * 1000);
}

function stop() {
  if (interval) {
    clearInterval(interval);
    interval = null;
    log.info('heartbeat loop stopped');
  }
}

async function tickNow() {
  return heartbeatTick();
}

module.exports = { start, stop, tickNow, checkOne };
