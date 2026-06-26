/**
 * Tiny .env loader (no deps). Skips comments (#) and blank lines.
 * Does NOT expand ${VAR} or quoted values — just KEY=VALUE.
 */
'use strict';

const fs = require('fs');

function load(filePath) {
  if (!fs.existsSync(filePath)) return 0;
  const txt = fs.readFileSync(filePath, 'utf8');
  let count = 0;
  for (const rawLine of txt.split(/\r?\n/)) {
    const line = rawLine.trim();
    if (!line || line.startsWith('#')) continue;
    const eq = line.indexOf('=');
    if (eq < 0) continue;
    const key = line.slice(0, eq).trim();
    let val = line.slice(eq + 1).trim();
    // Strip inline # comment (only if preceded by space — avoid trimming #foo)
    const hashIdx = val.indexOf(' #');
    if (hashIdx >= 0) val = val.slice(0, hashIdx).trim();
    // Strip surrounding quotes
    if ((val.startsWith('"') && val.endsWith('"')) ||
        (val.startsWith("'") && val.endsWith("'"))) {
      val = val.slice(1, -1);
    }
    if (key && !(key in process.env)) {
      process.env[key] = val;
      count++;
    }
  }
  return count;
}

module.exports = load;
