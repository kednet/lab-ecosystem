/**
 * Chief Agent — remote runner.
 *
 * Запускает action на Kednet-агенте через WebSocket.
 * Kednet-агент спавнит .venv\python.exe в C:\Users\kfigh\<skill>\, стримит
 * stdout/stderr chunks обратно по WS, по завершению шлёт exit + artifacts.
 *
 * Потокобезопасно: один job на agent (mutex в queue.js).
 * Возврат: Promise, который резолвится по приходу 'exit' от Kednet-агента.
 */
'use strict';

const store = require('../jobs/store');
const hub = require('../ws/hub');
const log = require('../util/logger').make('runner.remote');

// jobId → { resolve, reject, timer }
const inflight = new Map();

/**
 * Запустить action на Kednet-агенте.
 * @param {object} ctx  { agentId, actionId, params, dryRun, jobId, agent, action }
 * @returns {Promise<{exitCode, status, errorMessage}>}
 */
function runRemote({ agentId, actionId, params, dryRun, jobId, agent, action }) {
  const m = agent.metadata;
  const argv = [...(m.argsTemplate || [])];
  // для remote argsTemplate обычно содержит script-entry, дальше --flag value
  for (const [k, v] of Object.entries(params || {})) {
    if (v === undefined || v === null || v === '') continue;
    argv.push(`--${k}`);
    argv.push(String(v));
  }
  if (dryRun) argv.push('--dry-run');

  // env: фильтруем по envKeys (НЕ сливаем process.env целиком!)
  const env = {};
  for (const key of (m.envKeys || [])) {
    if (process.env[key]) env[key] = process.env[key];
  }

  log.info('remote.run', { agentId, jobId, cwd: m.cwd, argv: argv.slice(0, 5).join(' '), dryRun });

  return new Promise((resolve) => {
    if (!hub.isConnected()) {
      resolve({
        exitCode: null,
        status: 'failed',
        errorMessage: 'kednet agent not connected'
      });
      return;
    }

    // timeout = estimatedDurationSec × 6 + 5 мин запас, макс 1 час
    const timeoutMs = Math.min(
      ((action.estimatedDurationSec || 60) * 1000 * 6) + (5 * 60 * 1000),
      60 * 60 * 1000
    );

    const timer = setTimeout(() => {
      inflight.delete(jobId);
      resolve({
        exitCode: null,
        status: 'failed',
        errorMessage: `remote run timeout (${Math.round(timeoutMs / 1000)}s)`
      });
    }, timeoutMs);

    inflight.set(jobId, { resolve, timer });

    try {
      hub.send('run', {
        agentId,
        jobId,
        cwd: m.cwd,
        command: m.command || 'python',
        args: argv,
        env,
        timeoutMs
      }, jobId);
    } catch (e) {
      clearTimeout(timer);
      inflight.delete(jobId);
      resolve({
        exitCode: null,
        status: 'failed',
        errorMessage: e.message
      });
    }
  });
}

/**
 * Вызывается WS hub'ом когда Kednet прислал exit для jobId.
 * Резолвит соответствующий inflight Promise.
 */
function handleExit(jobId, { exitCode, durationMs, errorMessage }) {
  const entry = inflight.get(jobId);
  if (!entry) {
    // Возможно exit пришёл уже после timeout — игнорим.
    log.warn('remote.handleExit for unknown jobId', { jobId });
    return;
  }
  clearTimeout(entry.timer);
  inflight.delete(jobId);

  // store.finalizeJob уже вызван в ws/hub.js; тут просто резолвим.
  const status = exitCode === 0 ? 'completed' : 'failed';
  entry.resolve({ exitCode, durationMs, status, errorMessage: errorMessage || null });
}

/**
 * Отменить running remote-job (SIGTERM для процесса на Kednet).
 */
function cancel(jobId) {
  try {
    hub.send('cancel', { jobId, signal: 'SIGTERM' }, jobId);
    return true;
  } catch (e) {
    log.warn('remote.cancel failed', { jobId, err: e.message });
    return false;
  }
}

module.exports = { runRemote, handleExit, cancel };
