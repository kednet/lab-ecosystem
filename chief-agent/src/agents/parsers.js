/**
 * Chief Agent — stdout parsers (Phase 2 stub).
 *
 * MVP: just return the raw text. Phase 2: extract structured artifacts
 * (URLs, slugs, state.json statuses, image paths) for richer UI.
 */
'use strict';

function parseStdout(agentId, actionId, stdout) {
  // No-op for MVP — store full stdout in jobs table.
  return { raw: stdout || '' };
}

module.exports = { parseStdout };
