/**
 * Chief Agent — action runners.
 *
 * Two transports:
 *   - runSubprocess: spawn Python (or any) with given args, capture stdout/stderr.
 *   - runHttp: fetch a JSON endpoint with optional headers and body.
 *
 * Both return a normalized result:
 *   { exitCode, stdout, stderr, status, errorMessage }
 *
 * Jobs can be cancelled by killing the child PID via queue.cancel() — exposed
 * here as childProcesses Map so /api/jobs/:id/cancel can SIGTERM them.
 */
'use strict';

const { spawn } = require('child_process');
const fs = require('fs');
const store = require('../jobs/store');
const log = require('../util/logger').make('runner');

const childProcesses = new Map(); // jobId → ChildProcess

// ============================================================
// Subprocess runner
// ============================================================

async function runSubprocess({ agentId, actionId, params, dryRun, jobId, agent }) {
  const m = agent.metadata;

  // Build argv: base argsTemplate + per-action args + --dry-run.
  const argv = [...m.argsTemplate, actionId];
  for (const [k, v] of Object.entries(params || {})) {
    if (v === undefined || v === null || v === '') continue;
    argv.push(`--${k}`);
    argv.push(String(v));
  }
  if (dryRun) argv.push('--dry-run');

  // Load env from .env if envFile is set.
  const env = { ...process.env };
  if (m.envFile && fs.existsSync(m.envFile)) {
    require('../util/dotenv-mini')(m.envFile);
    Object.assign(env, process.env);
  }
  // Force UTF-8 + unbuffered.
  env.PYTHONIOENCODING = 'utf-8';
  env.LC_ALL = 'C.UTF-8';
  env.PYTHONUNBUFFERED = '1';

  log.info('spawn', { cmd: m.command, cwd: m.cwd, argv: argv.slice(0, 6).join(' '), jobId });

  return new Promise((resolve) => {
    let stdout = '';
    let stderr = '';
    let timedOut = false;
    const startMs = Date.now();

    const child = spawn(m.command, argv, {
      cwd: m.cwd,
      env,
      stdio: ['ignore', 'pipe', 'pipe'],
      // Run as root (Chief runs as root) — agent venv is world-readable.
      uid: 0,
      gid: 0
    });

    childProcesses.set(jobId, child);
    store.updateJobStarted(jobId, { pid: child.pid });

    child.stdout.setEncoding('utf8');
    child.stderr.setEncoding('utf8');

    child.stdout.on('data', (chunk) => { stdout += chunk; });
    child.stderr.on('data', (chunk) => { stderr += chunk; });

    child.on('error', (err) => {
      log.error('spawn error', { jobId, err: err.message });
      childProcesses.delete(jobId);
      resolve({
        exitCode: null,
        stdout,
        stderr,
        errorMessage: `spawn failed: ${err.message}`,
        status: 'failed'
      });
    });

    child.on('close', (code, signal) => {
      childProcesses.delete(jobId);
      const duration = Date.now() - startMs;
      log.info('child closed', { jobId, code, signal, duration });

      // If killed by SIGTERM (cancel), status = cancelled.
      const status = signal === 'SIGTERM' ? 'cancelled'
                   : code === 0 ? 'completed'
                   : 'failed';

      resolve({
        exitCode: code,
        stdout,
        stderr,
        status,
        errorMessage: timedOut ? 'timeout' :
                      code !== 0 && status === 'failed' ? `exit ${code}` : null
      });
    });
  });
}

// ============================================================
// HTTP runner
// ============================================================

async function runHttp({ agentId, actionId, params, dryRun, jobId, agent, action }) {
  const m = agent.metadata;
  const url = new URL(m.endpoint + (action.httpPath || '/'));

  const init = {
    method: action.httpMethod || 'GET',
    headers: {
      'Content-Type': 'application/json',
      ...(action.httpHeaders || {})
    },
    // 30s default timeout. Use AbortSignal.timeout if Node 18+ (it is).
    signal: AbortSignal.timeout(30_000)
  };

  // Body: POST/PUT/PATCH — merge action.httpHeaders with params.
  if (!['GET', 'HEAD'].includes(init.method)) {
    init.body = JSON.stringify(params || {});
  }

  // Apply X-Client-Id interpolation (coach expects this header).
  if (init.headers['X-Client-Id'] && typeof init.headers['X-Client-Id'] === 'string'
      && init.headers['X-Client-Id'].includes('{clientId}')) {
    init.headers['X-Client-Id'] = init.headers['X-Client-Id'].replace('{clientId}', params?.clientId || 'chief');
  }

  log.info('http fetch', { url: url.toString(), method: init.method, jobId });

  const startMs = Date.now();
  try {
    const r = await fetch(url, init);
    const text = await r.text();
    const stdout = `HTTP ${r.status} ${r.statusText}\n\n${text}`;
    const ok = r.ok;
    log.info('http done', { jobId, status: r.status, durationMs: Date.now() - startMs });
    return {
      exitCode: ok ? 0 : r.status,
      stdout,
      stderr: ok ? '' : `HTTP ${r.status}`,
      status: ok ? 'completed' : 'failed',
      errorMessage: ok ? null : `HTTP ${r.status}`
    };
  } catch (err) {
    log.error('http failed', { jobId, err: err.message });
    return {
      exitCode: null,
      stdout: '',
      stderr: err.message,
      status: 'failed',
      errorMessage: err.message
    };
  }
}

// ============================================================
// Public API: pick runner based on action/agent type
// ============================================================

function buildRunner(agent, action) {
  return async (ctx) => {
    if (action.isSystemAction) {
      // System actions like 'restart' — not handled here.
      // Routes them to /api/system/restart instead. Caller decides.
      throw new Error(`system action ${action.id} must be invoked via /api/system/restart`);
    }
    // type:'remote' → Kednet-агент через WS
    if (agent.type === 'remote') {
      const remote = require('./remote');
      return await remote.runRemote({ ...ctx, agent, action });
    }
    if (action.httpMethod) {
      return runHttp({ ...ctx, agent, action });
    }
    return runSubprocess({ ...ctx, agent });
  };
}

/**
 * Cancel a running subprocess by jobId.
 * Returns true if a child process was killed.
 */
function cancelChild(jobId) {
  const child = childProcesses.get(jobId);
  if (!child) return false;
  try {
    child.kill('SIGTERM');
    log.info('SIGTERM sent', { jobId });
    return true;
  } catch (err) {
    log.error('SIGTERM failed', { jobId, err: err.message });
    return false;
  }
}

module.exports = { buildRunner, cancelChild, runSubprocess, runHttp };
