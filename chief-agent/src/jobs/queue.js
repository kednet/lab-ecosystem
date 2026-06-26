/**
 * Chief Agent — in-memory job queue with per-agent mutex.
 *
 * Contract:
 *   - One run per agentId at a time. Concurrent calls for the same agent
 *     throw a ConflictError (HTTP 409).
 *   - Runs different agents in parallel.
 *   - Persists job state to SQLite via store.js.
 *   - For remote agents: runRemote() resolves on Kednet-агент 'exit'.
 *   - For completed jobs WITH artifacts (image/audio/video/json):
 *     status → 'awaiting_approval' (не 'completed').
 *     TG push с inline ✅/📂/❌.
 *   - Sends offline alerts via tg/notify when an agent is unhealthy 3 ticks.
 */
'use strict';

const store = require('./store');
const log = require('../util/logger').make('jobs.queue');
const tg = require('../tg/notify');
const approve = require('./approve');

const runningByAgent = new Map(); // agentId → { jobId, startedAt, agent }

class ConflictError extends Error {
  constructor(agentId) {
    super(`Agent "${agentId}" is already running a job`);
    this.code = 'agent_busy';
    this.statusCode = 409;
  }
}

function isRunning(agentId) {
  return runningByAgent.has(agentId);
}

function findRunningJob(jobId) {
  for (const [agentId, v] of runningByAgent.entries()) {
    if (v.jobId === jobId) return { agentId, ...v };
  }
  return null;
}

/**
 * Schedule a job: create row, then execute asynchronously.
 * Resolves with jobId immediately (don't wait for completion).
 */
function schedule({ agentId, actionId, params, dryRun, triggeredBy, triggeredByUser, runner, agent, transport }) {
  if (isRunning(agentId)) {
    throw new ConflictError(agentId);
  }
  const jobId = store.createJob({
    agentId,
    actionId,
    params,
    dryRun,
    triggeredBy,
    triggeredByUser,
    transport: transport || (agent && agent.type) || null
  });
  setImmediate(() => {
    runJob({ jobId, agentId, actionId, params, dryRun, runner, agent })
      .catch((err) => {
        log.error('runJob crashed', { jobId, err: err.message });
        finalize(jobId, agentId, actionId, {
          exitCode: null,
          status: 'failed',
          errorMessage: `runner exception: ${err.message}`
        });
      });
  });
  return jobId;
}

async function runJob({ jobId, agentId, actionId, params, dryRun, runner, agent }) {
  runningByAgent.set(agentId, { jobId, startedAt: new Date(), agent });
  log.info('job started', { jobId, agentId, actionId, dryRun, transport: agent && agent.type });

  // Для native запусков markRunning делает runner после spawn (pid доступен).
  // Для remote — Kednet-агент сам пришлёт 'started' по WS, hub вызовет
  // store.updateJobStarted. Поэтому локально markRunning НЕ вызываем — иначе
  // для remote у нас finishedAt будет, а started_at = null.

  let result;
  try {
    result = await runner({ agentId, actionId, params, dryRun, jobId });
  } catch (err) {
    log.error('runner threw', { jobId, err: err.message });
    result = {
      exitCode: null,
      status: 'failed',
      errorMessage: err.message
    };
  }

  await finalize(jobId, agentId, actionId, result);
}

async function finalize(jobId, agentId, actionId, result) {
  const wasRunning = runningByAgent.get(agentId);
  runningByAgent.delete(agentId);

  // Для native: статус приходит из runner, локальный markFinished.
  // Для remote: status/exitCode уже зафиксированы в store через ws/hub.handleMessage
  // (вызовы store.finalizeJob). Здесь нужно только:
  //   1) перевести job → awaiting_approval если есть artifacts + success
  //   2) отправить TG-уведомления
  const isRemote = wasRunning && wasRunning.agent && wasRunning.agent.type === 'remote';

  if (!isRemote) {
    // Native — локально финализируем.
    store.markFinished(jobId, result);
  }

  const job = store.getJob(jobId);
  if (!job) return;

  // Approve pipeline: success + есть artifacts с релевантным kind → awaiting_approval
  // (для remote — ws/hub уже emitнул 'job.exited' и approve.js сам подхватил;
  //  чтобы не было двойной обработки, setAwaitingApproval идемпотентный.)
  if (job.status === 'completed' && job.artifacts && job.artifacts.length > 0) {
    const RELEVANT = new Set(['image', 'audio', 'video', 'json']);
    if (job.artifacts.some(a => a && a.kind && RELEVANT.has(a.kind))) {
      const ok = store.setAwaitingApproval(jobId);
      if (ok && !isRemote) {
        // Для native — сами зовём TG-push (remote идёт через events).
        approve.onAwaitingApproval({ job: store.getJob(jobId), agentId, actionId })
          .catch(err => log.error('onAwaitingApproval failed', { jobId, err: err.message }));
      }
    }
  }

  // TG-алерт на failed job.
  if (job.status === 'failed') {
    tg.sendFailedJob({ job, agentId, actionId }).catch(() => {});
  }

  log.info('job finished', {
    jobId, agentId, status: job.status, exitCode: job.exitCode
  });
}

function cancel(jobId) {
  const entry = findRunningJob(jobId);
  if (!entry) {
    return store.cancelJob(jobId);
  }
  // Локально — flag cancelled; runner/runner.remote.detect cancel
  store.cancelJob(jobId);
  // Для native — runner.js SIGTERM через childProcesses Map.
  // Для remote — ws/hub шлёт cancel по WS (см. jobs/queue.cancelRemote()).
  try {
    const runner = require('../agents/runner');
    runner.cancelChild(jobId);
  } catch (_) {}
  try {
    const remote = require('../agents/remote');
    remote.cancel(jobId);
  } catch (_) {}
  return true;
}

function running() {
  return [...runningByAgent.entries()].map(([agentId, v]) => ({
    agentId,
    jobId: v.jobId,
    startedAt: v.startedAt.toISOString()
  }));
}

module.exports = {
  schedule,
  cancel,
  running,
  isRunning,
  findRunningJob,
  finalize
};
