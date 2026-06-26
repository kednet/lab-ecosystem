/**
 * Chief Agent v2.0 — entrypoint.
 *
 * Boots:
 *   1. DB migrations (creates schema if missing)
 *   2. Sync registry.js → SQLite
 *   3. Express HTTP server (REST API)
 *   4. WebSocket hub (для Kednet-агента)
 *   5. Heartbeat loop (30s)
 *   6. Approve pipeline tick (5 мин)
 *
 * Runs under systemd on VPS 89.108.88.74, port 7070 (127.0.0.1 only).
 */
'use strict';

if (!process.env.NODE_ENV) {
  process.env.NODE_ENV = process.env.CHIEF_DATA_DIR ? 'production' : 'development';
}

const http = require('http');
const express = require('express');
const cors = require('cors');

const config = require('./config');
const log = require('./util/logger').make('chief');

// CRITICAL: migrate.run() MUST execute before any module that does
// top-level `db.prepare(...)` is required (jobs/store.js, agents/sync.js,
// jobs/approve.js, …). Those modules fail-fast on `no such table: agents`
// if schema.sql hasn't run yet. We invoke it inline here, before requiring them.
require('./db/migrate').run();

const heartbeat = require('./agents/heartbeat');
const approve = require('./jobs/approve');
const wsHub = require('./ws/hub');
const tgPoller = require('./tg/poller');

const mw = require('./api/middleware');
const healthRoute  = require('./api/health');
const agentsRoute  = require('./api/agents');
const actionsRoute = require('./api/actions');
const jobsRoute    = require('./api/jobs');
const systemRoute  = require('./api/system');
const approvalsRoute = require('./api/approvals');
const auditRoute   = require('./api/audit');
const tgWebhookRoute = require('./api/tg');

function buildApp() {
  const app = express();
  app.disable('x-powered-by');
  app.set('trust proxy', true);
  app.use(express.json({ limit: '256kb' }));
  app.use(cors({ origin: false }));
  app.use(mw.logRequest);

  // TG webhook — НЕ через requireToken (проверяет X-Telegram-Bot-Api-Secret-Token).
  // Должен быть смонтирован ДО requireToken, иначе все TG-запросы получают 401.
  app.use('/api/tg', tgWebhookRoute);

  // Остальные API — под requireToken.
  app.use(mw.requireToken);
  app.use('/api', healthRoute);
  app.use('/api', agentsRoute);
  app.use('/api', actionsRoute);
  app.use('/api', jobsRoute);
  app.use('/api', systemRoute);
  app.use('/api', approvalsRoute);
  app.use('/api', auditRoute);

  app.use(mw.notFound);
  app.use(mw.errorHandler);
  return app;
}

function main() {
  // 1. DB migrations already ran at top of file (before any `db.prepare` module).
  // 2. Sync registry → SQLite.
  require('./agents/sync').syncAll();
  log.info('registry synced', { count: require('./agents/registry').length });

  // 3. Express + HTTP server (нужен http.Server для WS upgrade).
  const app = buildApp();
  const server = http.createServer(app);
  server.listen(config.port, config.bind, () => {
    log.info('chief-agent listening', {
      bind: config.bind,
      port: config.port,
      env: process.env.NODE_ENV,
      authEnabled: Boolean(config.apiToken),
      tgAlerts: config.tg.enabled,
      kednetTokenSet: Boolean(config.kednetToken)
    });
  });

  // 4. WebSocket hub.
  wsHub.start(server);

  // 5. Heartbeat.
  heartbeat.start();

  // 6. Approve tick.
  approve.start(300);

  // 7. TG long-poller (работает когда VPS не принимает входящие webhook'и от TG).
  tgPoller.start();

  const shutdown = (signal) => {
    log.info('shutdown initiated', { signal });
    heartbeat.stop();
    approve.stop();
    wsHub.stop();
    tgPoller.stop();
    server.close(() => {
      log.info('http server closed');
      process.exit(0);
    });
    setTimeout(() => process.exit(1), 10_000).unref();
  };
  process.on('SIGTERM', () => shutdown('SIGTERM'));
  process.on('SIGINT', () => shutdown('SIGINT'));
  process.on('uncaughtException', (err) => {
    log.error('uncaughtException', { err: err.message, stack: err.stack });
  });
  process.on('unhandledRejection', (err) => {
    log.error('unhandledRejection', { err: err && err.message });
  });
}

if (require.main === module) {
  main();
}

module.exports = { buildApp, main };
