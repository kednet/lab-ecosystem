/**
 * Chief Agent — approvals endpoint.
 * GET /api/approvals — list of jobs awaiting_approval.
 */
'use strict';

const express = require('express');
const store = require('../jobs/store');

const router = express.Router();

router.get('/approvals', (req, res) => {
  const jobs = store.listAwaitingApprovals();
  const now = Date.now();
  const enriched = jobs.map(j => ({
    jobId: j.id,
    agentId: j.agentId,
    actionId: j.actionId,
    artifacts: j.artifacts,
    artifactCount: (j.artifacts || []).length,
    createdAt: j.createdAt,
    ageSec: Math.round((now - new Date(j.createdAt + 'Z').getTime()) / 1000)
  }));
  res.json(enriched);
});

module.exports = router;
