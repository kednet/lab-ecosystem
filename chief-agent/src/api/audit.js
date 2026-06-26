/**
 * Chief Agent — audit log endpoint.
 * GET /api/audit?limit=&actor=
 */
'use strict';

const express = require('express');
const audit = require('../util/audit');

const router = express.Router();

router.get('/audit', (req, res) => {
  const { limit, actor } = req.query;
  const items = audit.list({
    limit: limit ? parseInt(limit, 10) : 50,
    actor: actor || null
  });
  res.json(items);
});

module.exports = router;
