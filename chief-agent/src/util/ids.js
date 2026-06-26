/**
 * Chief Agent — UUID v4 generator (RFC 4122).
 * Uses crypto.randomBytes, no external dependency.
 */
'use strict';

const { randomBytes } = require('crypto');

function uuidv4() {
  const b = randomBytes(16);
  // Per RFC 4122 §4.4: set version (4) and variant (10).
  b[6] = (b[6] & 0x0f) | 0x40;
  b[8] = (b[8] & 0x3f) | 0x80;
  const hex = b.toString('hex');
  return (
    hex.slice(0, 8) + '-' +
    hex.slice(8, 12) + '-' +
    hex.slice(12, 16) + '-' +
    hex.slice(16, 20) + '-' +
    hex.slice(20)
  );
}

module.exports = { uuidv4 };
