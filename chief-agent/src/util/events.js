/**
 * Chief Agent — глобальный EventEmitter для межмодульных сигналов.
 * Используется чтобы избежать circular import (ws/hub ↔ jobs/queue).
 *
 * События:
 *   'job.exited'        { jobId, exitCode, errorMessage }
 *   'agent.offline'     { agentId, lastSeen }
 *   'agent.online'      { agentId }
 *   'kednet.connected'  { hostname, os, skillsDetected }
 *   'kednet.disconnected' { reason }
 *   'approval.created'  { jobId, agentId, artifacts }
 *   'approval.approved' { jobId, approvedBy }
 *   'approval.rejected' { jobId, reason }
 */
'use strict';

const { EventEmitter } = require('events');
const ee = new EventEmitter();
ee.setMaxListeners(50);
module.exports = ee;
