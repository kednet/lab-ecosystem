/**
 * Chief Agent — minimal logger.
 * Writes to console (journald captures via stdout/stderr in systemd unit).
 * Format: ISO timestamp + level + scope + message.
 */
'use strict';

function ts() {
  return new Date().toISOString();
}

function fmt(level, scope, msg, extra) {
  const head = `[${ts()}] ${level.toUpperCase().padEnd(5)} ${scope.padEnd(20)} ${msg}`;
  if (extra && Object.keys(extra).length) {
    try {
      return `${head} ${JSON.stringify(extra)}`;
    } catch (_) {
      return `${head} <unserializable extra>`;
    }
  }
  return head;
}

function make(scope) {
  return {
    debug: (msg, extra) => {
      if (process.env.CHIEF_LOG_LEVEL === 'debug') {
        // eslint-disable-next-line no-console
        console.log(fmt('debug', scope, msg, extra));
      }
    },
    info:  (msg, extra) => console.log(fmt('info',  scope, msg, extra)),
    warn:  (msg, extra) => console.warn(fmt('warn',  scope, msg, extra)),
    error: (msg, extra) => console.error(fmt('error', scope, msg, extra))
  };
}

module.exports = { make };
