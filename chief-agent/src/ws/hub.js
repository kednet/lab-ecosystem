/**
 * Chief Agent — WebSocket hub.
 * Принимает одно persistent-соединение от Kednet-агента, аутентифицирует
 * токеном из первого hello-сообщения, держит ping/pong, маршрутизирует
 * run/cancel/scaffold команды.
 */
'use strict';

const { WebSocketServer } = require('ws');
const { C2K, K2C, validate, make } = require('./protocol');
const config = require('../config');
const logger = require('../util/logger').make('ws');
const store = require('../jobs/store');

const HEARTBEAT_INTERVAL_MS = 30 * 1000;   // ping каждые 30 сек
const PONG_TIMEOUT_MS       = 90 * 1000;   // close если нет pong 90 сек
const HELLO_TIMEOUT_MS      = 10 * 1000;   // 10 сек на hello после connect

let wss = null;
let client = null;                // текущее соединение (singleton)
let helloTimer = null;
let heartbeatTimer = null;
let lastPongAt = 0;

/**
 * Инициализировать WS server на переданном HTTP-сервере.
 * @param {http.Server} server
 */
function start(server) {
  wss = new WebSocketServer({ noServer: true });

  server.on('upgrade', (req, socket, head) => {
    // URL вида /ws или /ws/ — оба работают
    const url = req.url || '';
    const basePath = config.wsPath.endsWith('/') ? config.wsPath : config.wsPath + '/';
    if (url !== config.wsPath && url !== basePath && !url.startsWith(basePath)) {
      socket.write('HTTP/1.1 404 Not Found\r\n\r\n');
      socket.destroy();
      return;
    }
    wss.handleUpgrade(req, socket, head, (ws) => {
      wss.emit('connection', ws, req);
    });
  });

  wss.on('connection', onConnection);

  // Heartbeat (server-initiated ping)
  heartbeatTimer = setInterval(() => {
    if (!client || client.readyState !== client.OPEN) return;
    if (Date.now() - lastPongAt > PONG_TIMEOUT_MS) {
      logger.warn('pong timeout — closing connection');
      try { client.terminate(); } catch (_) {}
      return;
    }
    try { client.ping(); } catch (_) {}
  }, HEARTBEAT_INTERVAL_MS);

  logger.info(`hub started on ${config.wsPath} (heartbeat ${HEARTBEAT_INTERVAL_MS}ms)`);
}

function onConnection(ws, req) {
  const remoteAddr = req.socket?.remoteAddress || 'unknown';
  logger.info(`connection from ${remoteAddr}`);

  // Singleton: если уже есть живое соединение — закрываем новое.
  if (client && client.readyState === client.OPEN) {
    logger.warn('replacing existing connection');
    try { client.close(4000, 'replaced'); } catch (_) {}
  }
  client = ws;
  lastPongAt = Date.now();
  ws.isAlive = true;

  // Hello должен прийти в течение 10 сек
  helloTimer = setTimeout(() => {
    if (!ws.authenticated) {
      logger.warn('hello timeout');
      try { ws.close(4401, 'hello_timeout'); } catch (_) {}
    }
  }, HELLO_TIMEOUT_MS);

  ws.on('pong', () => {
    lastPongAt = Date.now();
    ws.isAlive = true;
  });

  ws.on('message', (raw) => {
    const v = validate(raw.toString());
    if (!v.ok) {
      logger.warn(`invalid message: ${v.error}`);
      return;
    }
    const msg = v.msg;

    // Hello — единственное сообщение до auth
    if (!ws.authenticated) {
      if (msg.type !== K2C.HELLO) {
        logger.warn(`expected hello, got ${msg.type}`);
        try { ws.close(4401, 'expected_hello'); } catch (_) {}
        return;
      }
      authenticate(ws, msg);
      return;
    }

    handleMessage(ws, msg);
  });

  ws.on('close', (code, reason) => {
    logger.info(`closed code=${code} reason=${reason || 'none'}`);
    if (client === ws) client = null;
    if (helloTimer) { clearTimeout(helloTimer); helloTimer = null; }
    markDisconnected(`closed code=${code}`);
  });

  ws.on('error', (err) => {
    logger.warn(`error: ${err.message}`);
  });
}

function authenticate(ws, msg) {
  const token = msg.data && msg.data.token;
  if (!config.kednetToken) {
    logger.warn('KEDNET_AGENT_TOKEN not set — rejecting all WS connections');
    try { ws.close(4401, 'server_misconfigured'); } catch (_) {}
    return;
  }
  if (token !== config.kednetToken) {
    logger.warn('auth failed (bad token)');
    try { ws.close(4401, 'bad_token'); } catch (_) {}
    return;
  }
  if (helloTimer) { clearTimeout(helloTimer); helloTimer = null; }
  ws.authenticated = true;

  const hostname = msg.data.hostname || 'unknown';
  const os = msg.data.os || 'unknown';
  const version = msg.data.version || '0.0.0';
  const skillsDetected = Array.isArray(msg.data.skillsDetected) ? msg.data.skillsDetected : [];

  saveAgentRow({
    connected: 1, hostname, os, version,
    skillsDetected, connectedAt: new Date().toISOString(),
    lastHeartbeatAt: new Date().toISOString(), lastError: null
  });

  logger.info(`authenticated: ${hostname} (${os}) skills=${skillsDetected.length}`);

  // Welcome
  try { ws.send(make(C2K.WELCOME, {
    version: '2.0.0',
    serverTime: Date.now(),
    heartbeatSec: HEARTBEAT_INTERVAL_MS / 1000
  })); } catch (e) { logger.warn(`welcome send failed: ${e.message}`); }
}

function handleMessage(ws, msg) {
  // Update last_heartbeat_at on every authenticated message
  touchHeartbeat();

  switch (msg.type) {
    case K2C.PONG:
      // nothing extra (handled in 'pong' event)
      break;

    case K2C.STARTED: {
      const { jobId, pid, startedAt } = msg.data;
      if (jobId) store.updateJobStarted(jobId, { pid, startedAt });
      break;
    }

    case K2C.STDOUT: {
      const { jobId, chunk } = msg.data;
      if (jobId && typeof chunk === 'string') store.appendStdout(jobId, chunk);
      break;
    }

    case K2C.STDERR: {
      const { jobId, chunk } = msg.data;
      if (jobId && typeof chunk === 'string') store.appendStderr(jobId, chunk);
      break;
    }

    case K2C.ARTIFACT: {
      const { jobId, path: fpath, kind, sizeBytes, mime } = msg.data;
      if (jobId && fpath) store.addArtifact(jobId, { path: fpath, kind, sizeBytes, mime });
      break;
    }

    case K2C.EXIT: {
      const { jobId, exitCode, durationMs, errorMessage } = msg.data;
      if (jobId) {
        // finalize переводит job в completed/failed, jobs/approve.js переведёт
        // в awaiting_approval если есть artifacts с kind∈{image,audio,video,json}.
        store.finalizeJob(jobId, {
          exitCode,
          durationMs,
          errorMessage: errorMessage || null
        });
        // Lazy require чтобы избежать circular import (remote ↔ hub).
        process.nextTick(() => {
          try {
            const remote = require('../agents/remote');
            remote.handleExit(jobId, { exitCode, durationMs, errorMessage });
          } catch (e) {
            logger.warn(`remote.handleExit failed: ${e.message}`);
          }
          // Триггерим approve-pipeline + TG-уведомления
          try {
            const events = require('../util/events');
            events.emit('job.exited', { jobId, exitCode, errorMessage });
          } catch (e) {
            logger.warn(`events.emit failed: ${e.message}`);
          }
        });
      }
      break;
    }

    case K2C.SCAFFOLD_DONE: {
      const { agentId, files, requirements, error } = msg.data;
      logger.info(`scaffold.done agentId=${agentId} files=${(files||[]).length} err=${error||'none'}`);
      // EventEmitter не используем — scaffold.js дождётся через promise map
      if (ws._scaffoldResolvers && agentId && ws._scaffoldResolvers.has(agentId)) {
        const { resolve, reject } = ws._scaffoldResolvers.get(agentId);
        ws._scaffoldResolvers.delete(agentId);
        if (error) reject(new Error(error));
        else resolve({ files: files || [], requirements: requirements || [] });
      }
      break;
    }

    case K2C.ERROR: {
      const { jobId, message } = msg.data;
      logger.warn(`kednet error jobId=${jobId}: ${message}`);
      if (jobId) {
        store.appendStderr(jobId, `\n[ws:kednet_error] ${message}\n`);
      }
      break;
    }

    case K2C.REQUEST: {
      // Зарезервировано на Phase 2 (например Kednet просит Chief скачать файл)
      logger.info(`request from kednet: ${JSON.stringify(msg.data).slice(0, 200)}`);
      break;
    }

    default:
      logger.warn(`unknown message type: ${msg.type}`);
  }
}

function saveAgentRow(data) {
  try {
    const db = require('../db/client');
    const stmt = db.prepare(`
      INSERT INTO kednet_agent (id, hostname, os, version, skills_detected_json,
                                connected, connected_at, last_heartbeat_at, last_error)
      VALUES (1, @hostname, @os, @version, @skillsDetected,
              @connected, @connectedAt, @lastHeartbeatAt, @lastError)
      ON CONFLICT(id) DO UPDATE SET
        hostname              = excluded.hostname,
        os                    = excluded.os,
        version               = excluded.version,
        skills_detected_json  = excluded.skills_detected_json,
        connected             = excluded.connected,
        connected_at          = excluded.connected_at,
        last_heartbeat_at     = excluded.last_heartbeat_at,
        last_error            = excluded.last_error
    `);
    stmt.run({
      hostname: data.hostname,
      os: data.os,
      version: data.version,
      skillsDetected: JSON.stringify(data.skillsDetected || []),
      connected: data.connected,
      connectedAt: data.connectedAt,
      lastHeartbeatAt: data.lastHeartbeatAt,
      lastError: data.lastError
    });
  } catch (e) {
    logger.warn(`saveAgentRow failed: ${e.message}`);
  }
}

function touchHeartbeat() {
  try {
    const db = require('../db/client');
    db.prepare(`UPDATE kednet_agent SET last_heartbeat_at = ? WHERE id = 1`)
      .run(new Date().toISOString());
  } catch (e) {
    logger.warn(`touchHeartbeat failed: ${e.message}`);
  }
}

function markDisconnected(reason) {
  try {
    const db = require('../db/client');
    db.prepare(`
      UPDATE kednet_agent
      SET connected = 0, last_error = ?
      WHERE id = 1
    `).run(reason || 'disconnected');
  } catch (e) {
    logger.warn(`markDisconnected failed: ${e.message}`);
  }
}

/**
 * Отправить команду Kednet-агенту. Бросает, если нет соединения.
 * @param {string} type — один из C2K.*
 * @param {object} data
 * @param {string} [jobId]
 */
function send(type, data, jobId) {
  if (!client || client.readyState !== client.OPEN) {
    throw new Error('kednet agent not connected');
  }
  client.send(make(type, data, jobId));
}

/**
 * Запросить scaffold с ожиданием ответа. Promise резолвится по scaffold.done.
 */
function requestScaffold(agentId, cwd, templateType) {
  return new Promise((resolve, reject) => {
    if (!client || client.readyState !== client.OPEN) {
      reject(new Error('kednet agent not connected'));
      return;
    }
    if (!client._scaffoldResolvers) client._scaffoldResolvers = new Map();
    client._scaffoldResolvers.set(agentId, { resolve, reject });

    // timeout 30 сек
    setTimeout(() => {
      if (client._scaffoldResolvers && client._scaffoldResolvers.has(agentId)) {
        client._scaffoldResolvers.delete(agentId);
        reject(new Error('scaffold timeout'));
      }
    }, 30 * 1000);

    try {
      send(C2K.SCAFFOLD, { agentId, cwd, templateType });
    } catch (e) {
      client._scaffoldResolvers.delete(agentId);
      reject(e);
    }
  });
}

/**
 * Текущее состояние Kednet-агента. { connected, hostname, lastHeartbeatAt, ... }
 */
function getStatus() {
  try {
    const db = require('../db/client');
    const row = db.prepare(`SELECT * FROM kednet_agent WHERE id=1`).get();
    if (!row) return { connected: false };
    return {
      connected:        Boolean(row.connected),
      hostname:         row.hostname,
      os:               row.os,
      version:          row.version,
      skillsDetected:   JSON.parse(row.skills_detected_json || '[]'),
      connectedAt:      row.connected_at,
      lastHeartbeatAt:  row.last_heartbeat_at,
      lastError:        row.last_error
    };
  } catch (e) {
    return { connected: false, error: e.message };
  }
}

function isConnected() {
  return Boolean(client && client.readyState === client.OPEN);
}

function stop() {
  if (heartbeatTimer) { clearInterval(heartbeatTimer); heartbeatTimer = null; }
  if (helloTimer)     { clearTimeout(helloTimer); helloTimer = null; }
  if (client)         { try { client.close(1000, 'shutdown'); } catch (_) {} client = null; }
  if (wss)            { try { wss.close(); } catch (_) {} wss = null; }
}

module.exports = { start, stop, send, requestScaffold, getStatus, isConnected };
