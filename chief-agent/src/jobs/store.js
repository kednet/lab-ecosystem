/**
 * Chief Agent — jobs CRUD over SQLite.
 * All methods are synchronous (better-sqlite3 is sync).
 */
'use strict';

const db = require('../db/client');
const { uuidv4 } = require('../util/ids');
const log = require('../util/logger').make('jobs.store');

const STDOUT_CAP = (() => {
  const n = parseInt(process.env.CHIEF_STDOUT_CAP_BYTES, 10);
  return Number.isFinite(n) && n > 0 ? n : 5 * 1024 * 1024;
})();

function cap(s) {
  if (!s) return null;
  if (s.length <= STDOUT_CAP) return s;
  return s.slice(0, STDOUT_CAP) + `\n\n[truncated at ${STDOUT_CAP} bytes]`;
}

const STMT = {
  insert: db.prepare(`
    INSERT INTO jobs (
      id, agent_id, action_id, status, params_json,
      dry_run, triggered_by, triggered_by_user, transport, created_at
    ) VALUES (
      @id, @agent_id, @action_id, 'queued', @params_json,
      @dry_run, @triggered_by, @triggered_by_user, @transport, datetime('now')
    )
  `),

  updateStatus: db.prepare(`UPDATE jobs SET status = @status WHERE id = @id`),

  setStarted: db.prepare(`
    UPDATE jobs SET status = 'running', pid = @pid, started_at = @started_at
    WHERE id = @id
  `),

  appendStdout: db.prepare(`
    UPDATE jobs SET stdout = CASE
      WHEN stdout IS NULL THEN @chunk
      WHEN length(stdout) + length(@chunk) > ${STDOUT_CAP}
        THEN substr(stdout, length(@chunk)) || @chunk
      ELSE stdout || @chunk
    END
    WHERE id = @id
  `),

  appendStderr: db.prepare(`
    UPDATE jobs SET stderr = CASE
      WHEN stderr IS NULL THEN @chunk
      WHEN length(stderr) + length(@chunk) > ${STDOUT_CAP}
        THEN substr(stderr, length(@chunk)) || @chunk
      ELSE stderr || @chunk
    END
    WHERE id = @id
  `),

  addArtifact: db.prepare(`
    UPDATE jobs SET artifacts_json = @payload WHERE id = @id
  `),

  finalize: db.prepare(`
    UPDATE jobs SET
      status = @status,
      exit_code = @exit_code,
      finished_at = datetime('now'),
      error_message = @error_message,
      stdout = COALESCE(@stdout, stdout),
      stderr = COALESCE(@stderr, stderr)
    WHERE id = @id
  `),

  approve: db.prepare(`
    UPDATE jobs SET
      status = 'completed',
      approved_at = datetime('now'),
      approved_by = @approved_by,
      error_message = COALESCE(error_message, '')
    WHERE id = @id AND status = 'awaiting_approval'
  `),

  reject: db.prepare(`
    UPDATE jobs SET
      status = 'cancelled',
      rejected_at = datetime('now'),
      rejection_reason = @reason,
      finished_at = datetime('now'),
      error_message = @reason
    WHERE id = @id AND status = 'awaiting_approval'
  `),

  get: db.prepare(`SELECT * FROM jobs WHERE id = ?`),
  list: db.prepare(`
    SELECT * FROM jobs
    WHERE (@agent IS NULL OR agent_id = @agent)
      AND (@status IS NULL OR status = @status)
    ORDER BY created_at DESC
    LIMIT @limit
  `),
  listAwaiting: db.prepare(`
    SELECT j.* FROM jobs j
    JOIN approvals a ON a.job_id = j.id
    WHERE j.status = 'awaiting_approval'
    ORDER BY j.created_at ASC
  `),

  cancel: db.prepare(`
    UPDATE jobs SET status = 'cancelled', finished_at = datetime('now'),
                    error_message = COALESCE(error_message, 'cancelled by user')
    WHERE id = @id AND status IN ('queued','running')
  `)
};

// ────────────────────────────────────────────────────────────
// Write API
// ────────────────────────────────────────────────────────────

function createJob({ agentId, actionId, params, dryRun, triggeredBy, triggeredByUser, transport }) {
  const id = uuidv4();
  STMT.insert.run({
    id,
    agent_id: agentId,
    action_id: actionId,
    params_json: JSON.stringify(params || {}),
    dry_run: dryRun ? 1 : 0,
    triggered_by: triggeredBy,
    triggered_by_user: triggeredByUser || null,
    transport: transport || null
  });
  log.debug('job created', { id, agentId, actionId, transport });
  return id;
}

function updateJobStarted(id, { pid, startedAt }) {
  STMT.setStarted.run({
    id,
    pid: pid || null,
    started_at: startedAt || new Date().toISOString()
  });
}

function appendStdout(id, chunk) {
  if (!chunk) return;
  STMT.appendStdout.run({ id, chunk });
}

function appendStderr(id, chunk) {
  if (!chunk) return;
  STMT.appendStderr.run({ id, chunk });
}

function addArtifact(id, artifact) {
  const row = STMT.get.get(id);
  if (!row) return;
  let arr = [];
  try { arr = JSON.parse(row.artifacts_json || '[]'); } catch (_) { arr = []; }
  arr.push(artifact);
  STMT.addArtifact.run({ id, payload: JSON.stringify(arr) });
}

/**
 * Финализация job: completed | failed. status='awaiting_approval' выставляется
 * отдельно через approve.moveToAwaitingApproval если есть релевантные artifacts.
 */
function finalizeJob(id, { exitCode, durationMs, errorMessage, stdout, stderr }) {
  const row = STMT.get.get(id);
  if (!row) return;
  if (row.status !== 'running') return;   // идемпотентно (не перетираем approve/reject)

  const status = exitCode === 0 ? 'completed' : 'failed';
  STMT.finalize.run({
    id,
    status,
    exit_code: exitCode === null || exitCode === undefined ? null : exitCode,
    error_message: errorMessage || null,
    stdout: stdout || null,
    stderr: stderr || null
  });

  capOnRead(id);
}

function capOnRead(id) {
  // no-op: уже каппим в SQL через length-check. Но принудительно тримнем если есть oversize.
  const row = STMT.get.get(id);
  if (!row) return;
  const updates = [];
  if (row.stdout && row.stdout.length > STDOUT_CAP) {
    updates.push(`stdout = '${row.stdout.slice(0, STDOUT_CAP)}''[truncated at ${STDOUT_CAP} bytes]'`);
  }
  if (row.stderr && row.stderr.length > STDOUT_CAP) {
    updates.push(`stderr = '${row.stderr.slice(0, STDOUT_CAP)}''[truncated at ${STDOUT_CAP} bytes]'`);
  }
  if (updates.length) {
    db.prepare(`UPDATE jobs SET ${updates.join(', ')} WHERE id = ?`).run(id);
  }
}

function setAwaitingApproval(id) {
  const row = STMT.get.get(id);
  if (!row) return false;
  if (row.status !== 'completed') return false;
  STMT.updateStatus.run({ id, status: 'awaiting_approval' });
  return true;
}

function approveJob(id, approvedBy) {
  const r = STMT.approve.run({ id, approved_by: approvedBy || 'kfigh' });
  if (r.changes > 0) {
    db.prepare(`DELETE FROM approvals WHERE job_id = ?`).run(id);
  }
  return r.changes > 0;
}

function rejectJob(id, reason) {
  const r = STMT.reject.run({ id, reason: reason || 'user rejected' });
  if (r.changes > 0) {
    db.prepare(`DELETE FROM approvals WHERE job_id = ?`).run(id);
  }
  return r.changes > 0;
}

function cancelJob(id) {
  const r = STMT.cancel.run({ id });
  return r.changes > 0;
}

function getArtifacts(id) {
  const row = STMT.get.get(id);
  if (!row || !row.artifacts_json) return [];
  try { return JSON.parse(row.artifacts_json); } catch (_) { return []; }
}

// ────────────────────────────────────────────────────────────
// Read API
// ────────────────────────────────────────────────────────────

function getJob(id) {
  const row = STMT.get.get(id);
  if (!row) return null;
  return rowToJob(row);
}

function listJobs({ limit = 20, agent = null, status = null } = {}) {
  const rows = STMT.list.all({
    limit: Math.min(Math.max(parseInt(limit, 10) || 20, 1), 200),
    agent,
    status
  });
  return rows.map(rowToJob);
}

function listAwaitingApprovals() {
  const rows = STMT.listAwaiting.all();
  return rows.map(rowToJob);
}

function rowToJob(r) {
  let artifacts = [];
  try { artifacts = r.artifacts_json ? JSON.parse(r.artifacts_json) : []; } catch (_) { artifacts = []; }
  return {
    id: r.id,
    agentId: r.agent_id,
    actionId: r.action_id,
    status: r.status,
    params: r.params_json ? JSON.parse(r.params_json) : {},
    stdout: r.stdout,
    stderr: r.stderr,
    exitCode: r.exit_code,
    pid: r.pid,
    startedAt: r.started_at,
    finishedAt: r.finished_at,
    dryRun: !!r.dry_run,
    triggeredBy: r.triggered_by,
    triggeredByUser: r.triggered_by_user,
    errorMessage: r.error_message,
    transport: r.transport,
    artifacts,
    approvedAt: r.approved_at,
    approvedBy: r.approved_by,
    rejectedAt: r.rejected_at,
    rejectionReason: r.rejection_reason,
    createdAt: r.created_at
  };
}

module.exports = {
  createJob,
  updateJobStarted,
  appendStdout,
  appendStderr,
  addArtifact,
  finalizeJob,
  // legacy alias — native runner (runSubprocess) uses it
  markFinished: finalizeJob,
  setAwaitingApproval,
  approveJob,
  rejectJob,
  cancelJob,
  getArtifacts,
  getJob,
  listJobs,
  listAwaitingApprovals
};
