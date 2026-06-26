/**
 * Chief Agent — config loader.
 * Reads .env (in dev only — prod uses systemd EnvironmentFile),
 * exposes typed values and the allowlist for system/restart.
 */
'use strict';

const fs = require('fs');
const path = require('path');

// === Load .env only in dev (not under systemd) ===
if (process.env.NODE_ENV !== 'production') {
  const envPath = path.join(__dirname, '..', '.env');
  if (fs.existsSync(envPath)) {
    require('dotenv-mini')(envPath);
  }
}

// === Strong-typed env accessors with defaults ===
function req(name) {
  const v = process.env[name];
  if (!v || v === 'replace-me-with-32-byte-hex-from-openssl') {
    throw new Error(`[config] Required env var missing or placeholder: ${name}`);
  }
  return v;
}

function opt(name, def) {
  const v = process.env[name];
  return v === undefined || v === '' ? def : v;
}

function num(name, def) {
  const v = opt(name, undefined);
  if (v === undefined) return def;
  const n = parseInt(v, 10);
  if (isNaN(n)) throw new Error(`[config] Env var ${name} must be int, got: ${v}`);
  return n;
}

function bool(name, def) {
  const v = opt(name, undefined);
  if (v === undefined) return def;
  return v === '1' || v.toLowerCase() === 'true';
}

const config = {
  port:           num('CHIEF_PORT', 7070),
  bind:           opt('CHIEF_BIND', '127.0.0.1'),
  wsPath:         opt('CHIEF_WS_PATH', '/ws'),
  apiToken:       process.env.CHIEF_API_TOKEN || '',   // optional in dev (no token = open API)
  adminToken:     process.env.CHIEF_ADMIN_TOKEN || '',// ≥32 chars in prod, gates POST/PUT/DELETE
  kednetToken:    process.env.KEDNET_AGENT_TOKEN || '',// auth for Kednet-агент WS handshake
  heartbeatSec:   num('CHIEF_HEARTBEAT_INTERVAL', 30),
  stdoutCapBytes: num('CHIEF_STDOUT_CAP_BYTES', 5 * 1024 * 1024),
  insecureTls:    bool('CHIEF_INSECURE_TLS', false),

  tg: {
    enabled:      Boolean(opt('TG_BOT_TOKEN') && opt('TG_CHAT_ID')),
    botToken:     opt('TG_BOT_TOKEN', ''),
    chatId:       opt('TG_CHAT_ID', ''),
    webhookSecret: opt('TG_WEBHOOK_SECRET', ''),
    botName:      opt('TG_BOT_NAME', '@ChiefAgentbot'),
    approvalTimeoutSec: num('CHIEF_APPROVAL_TIMEOUT', 24 * 3600),
    reminderSec:  num('CHIEF_APPROVAL_REMINDER', 3600)
  },

  coachApiUrl:    opt('COACH_API_URL', ''),
  labSiteApiUrl:  opt('LAB_SITE_API_URL', 'https://api.pulab.online'),

  // Allowlist for POST /api/system/restart/:service
  allowedServices: new Set([
    'wl-detector',
    'wl-tg-posting',
    'wl-librarian',
    'experiments-bot',
    'lab-api',
    'chief-agent'
  ])
};

// === Strong validation in production ===
if (process.env.NODE_ENV === 'production') {
  if (!config.apiToken || config.apiToken.length < 32) {
    throw new Error('[config] CHIEF_API_TOKEN must be set and ≥32 chars in production');
  }
  if (!config.adminToken || config.adminToken.length < 32) {
    throw new Error('[config] CHIEF_ADMIN_TOKEN must be set and ≥32 chars in production');
  }
  if (!config.kednetToken || config.kednetToken.length < 32) {
    throw new Error('[config] KEDNET_AGENT_TOKEN must be set and ≥32 chars in production');
  }
  if (config.bind === '0.0.0.0') {
    // eslint-disable-next-line no-console
    console.warn('[config] WARNING: CHIEF_BIND=0.0.0.0 — Chief is publicly accessible.');
  }
}

module.exports = config;
