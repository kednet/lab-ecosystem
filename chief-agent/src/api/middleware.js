/**
 * Chief Agent — middleware: auth, logging, errors.
 */
'use strict';

const config = require('../config');
const log = require('../util/logger').make('http');

function requireToken(req, res, next) {
  // /api/health (and any other public paths) is always public.
  // req.path here is the full path because middleware is mounted on the app root.
  if (req.path === '/api/health' || req.path === '/health') return next();
  // No token configured (dev) → open API.
  if (!config.apiToken) return next();

  const header = req.headers['authorization'] || '';
  const m = /^Bearer\s+(.+)$/i.exec(header);
  if (!m || m[1] !== config.apiToken) {
    log.warn('auth rejected', { ip: req.ip, ua: req.headers['user-agent'] });
    return res.status(401).json({ error: 'unauthorized' });
  }
  next();
}

/**
 * Admin auth — поверх requireToken, требует X-Admin-Token.
 * Используется для: POST/PUT/DELETE /api/agents, POST /api/system/restart.
 */
function requireAdmin(req, res, next) {
  if (!config.adminToken) {
    return res.status(503).json({ error: 'admin_disabled', message: 'CHIEF_ADMIN_TOKEN not configured' });
  }
  const provided = req.headers['x-admin-token'] || '';
  if (provided !== config.adminToken) {
    log.warn('admin auth rejected', { ip: req.ip, path: req.path });
    return res.status(403).json({ error: 'admin_required' });
  }
  next();
}

function logRequest(req, res, next) {
  const start = Date.now();
  res.on('finish', () => {
    log.info('req', {
      method: req.method,
      path: req.path,
      status: res.statusCode,
      ms: Date.now() - start,
      ip: req.ip
    });
  });
  next();
}

function notFound(req, res) {
  res.status(404).json({ error: 'not_found', path: req.path });
}

// eslint-disable-next-line no-unused-vars
function errorHandler(err, req, res, next) {
  log.error('unhandled error', { path: req.path, err: err.message, stack: err.stack });
  const status = err.statusCode || 500;
  res.status(status).json({
    error: err.code || 'internal_error',
    message: err.message
  });
}

module.exports = { requireToken, requireAdmin, logRequest, notFound, errorHandler };
