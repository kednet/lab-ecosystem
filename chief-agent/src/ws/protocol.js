/**
 * Chief Agent — WebSocket protocol validator.
 * JSON-сообщения между Chief и Kednet-агентом.
 * Формат: { type: string, ts: number, jobId?: string, data: object }
 */
'use strict';

// Message types: Chief → Kednet
const C2K = {
  WELCOME:  'welcome',
  RUN:      'run',
  CANCEL:   'cancel',
  PING:     'ping',
  SCAFFOLD: 'scaffold',
  REPLY:    'reply'         // ответ на запрос Kednet-агента (например open file)
};

// Message types: Kednet → Chief
const K2C = {
  HELLO:        'hello',
  PONG:         'pong',
  STARTED:      'started',
  STDOUT:       'stdout',
  STDERR:       'stderr',
  ARTIFACT:     'artifact',
  EXIT:         'exit',
  SCAFFOLD_DONE:'scaffold.done',
  REQUEST:      'request',   // Kednet инициирует (например TG inline "open file")
  ERROR:        'error'
};

/**
 * Validate and normalize an incoming message.
 * Returns { ok: true, msg } or { ok: false, error }.
 */
function validate(raw) {
  let msg;
  try {
    msg = JSON.parse(raw);
  } catch (e) {
    return { ok: false, error: 'invalid_json' };
  }
  if (typeof msg !== 'object' || msg === null) {
    return { ok: false, error: 'not_object' };
  }
  if (typeof msg.type !== 'string' || !msg.type) {
    return { ok: false, error: 'missing_type' };
  }
  if (msg.data !== undefined && (typeof msg.data !== 'object' || msg.data === null)) {
    return { ok: false, error: 'data_not_object' };
  }
  if (msg.ts === undefined) msg.ts = Date.now();
  if (msg.data === undefined) msg.data = {};
  return { ok: true, msg };
}

/**
 * Build outgoing message. Adds ts automatically.
 */
function make(type, data = {}, jobId) {
  const msg = { type, ts: Date.now(), data };
  if (jobId) msg.jobId = jobId;
  return JSON.stringify(msg);
}

module.exports = { C2K, K2C, validate, make };
