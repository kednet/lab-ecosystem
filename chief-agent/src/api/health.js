/**
 * Chief Agent — health endpoint (no auth).
 */
'use strict';

const express = require('express');
const db = require('../db/client');
const queue = require('../jobs/queue');
const wsHub = require('../ws/hub');
const config = require('../config');

const router = express.Router();
const START_MS = Date.now();

router.get('/health', (req, res) => {
  const uptimeSec = Math.floor((Date.now() - START_MS) / 1000);
  const agents = db.prepare('SELECT COUNT(*) AS c FROM agents WHERE enabled = 1').get().c;
  const online = db.prepare("SELECT COUNT(*) AS c FROM heartbeats WHERE status = 'online'").get().c;
  const awaiting = db.prepare("SELECT COUNT(*) AS c FROM jobs WHERE status = 'awaiting_approval'").get().c;
  const kednet = wsHub.getStatus();
  res.json({
    status: 'ok',
    version: '2.0.0',
    uptimeSec,
    agentsTotal: agents,
    agentsOnline: online,
    runningJobs: queue.running().length,
    awaitingApproval: awaiting,
    kednetConnected: kednet.connected,
    kednetHostname: kednet.hostname || null,
    tgAlertsEnabled: config.tg.enabled
  });
});

module.exports = router;