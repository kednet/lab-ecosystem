/**
 * Chief Agent — Telegram long-poller.
 *
 * Почему polling, а не webhook:
 *   VPS Reg.ru блокирует ВХОДЯЩИЕ с TG-подсетей (last_error: Connection timed out).
 *   Polling не требует входящих соединений — Chief дёргает getUpdates через SOCKS5.
 *
 * Что делает:
 *   1. Каждые POLL_INTERVAL_MS секунд вызывает getUpdates?timeout=LONG_POLL&offset=...
 *   2. Передаёт каждый update в handleUpdate через внутренний POST /api/tg/webhook.
 *   3. Шлёт ack'и offset'а, чтобы TG не возвращал уже обработанные updates.
 *   4. Если есть SOCKS5 прокси в TG_PROXY_URL — идёт через него (через curl).
 *
 * Почему curl, а не fetch+SocksProxyAgent:
 *   socks-proxy-agent@8 не парсит user:pass из socks5:// URL.
 *   Даже после ручного прокидывания userId/password — handshake зависает.
 *   curl --proxy socks5h:// работает гарантированно (проверено 2026-06-19).
 *
 * Env:
 *   TG_BOT_TOKEN          — обязателен для polling
 *   TG_PROXY_URL          — socks5:// или socks5h:// (опционально)
 *   TG_POLL_INTERVAL_MS   — дефолт 1000
 *
 * Короткий polling (без timeout=) вместо long-poll:
 *   SOCKS5-прокси proxy6.net не relay'ит длинные idle-соединения.
 *   Без long-poll TG отвечает сразу (<1s) — прокси справляется.
 *   Polling 1×/сек = мгновенная реакция на update'ы для пользователя.
 *
 * При TG_WEBHOOK_SECRET в .env и активном webhook — отключается (webhook>polling).
 */
'use strict';

const { execFile } = require('child_process');
const log = require('../util/logger').make('tg.poller');

const TOKEN = process.env.TG_BOT_TOKEN;
const PROXY_URL = process.env.TG_PROXY_URL || '';
const POLL_INTERVAL_MS = parseInt(process.env.TG_POLL_INTERVAL_MS, 10) || 200;
// 3s — короткий long-poll, потому что SOCKS5-прокси (proxy6.net) не делает relay
// для длинных idle-соединений и рвёт соединение через ~5-10 сек.
const LONG_POLL_SEC = parseInt(process.env.TG_LONG_POLL_SEC, 10) || 3;

let offset = 0;
let polling = false;
let stopRequested = false;

/**
 * Вызвать getUpdates через curl (поддерживает SOCKS5 нативно).
 * curl с socks5h — резолвит DNS на стороне прокси.
 */
function getUpdatesCurl(args) {
  return new Promise((resolve, reject) => {
    const curlArgs = [
      // -sS = silent + show errors. stderr идёт в pipe (см. stdio).
      // Без -S curl молча падает на ошибках.
      '-sS',
      // 10s достаточно: getUpdates без long-poll отвечает за <1s.
      '--max-time', '10',
      // SOCKS5-прокси (proxy6.net) не поддерживает keepalive — без этого
      // curl пытается переиспользовать соединение через прокси и зависает.
      '--no-keepalive',
      '-H', 'User-Agent: ChiefAgent/2.0 (poller/curl)',
    ];
    if (PROXY_URL) {
      curlArgs.push('--proxy', PROXY_URL);
    }
    curlArgs.push(args);

    // execFile (а не spawn) — фикс для systemd-окружения,
    // где spawn curl'у с socks-прокси почему-то зависает.
    // stdio: ignore/pipe/pipe — НЕ наследуем fd 0,1,2 (stdout/stderr у chief-agent
    // это journal socket, что мешает curl'у корректно работать).
    execFile('curl', curlArgs, { maxBuffer: 1024 * 1024, stdio: ['ignore', 'pipe', 'pipe'] }, (err, stdout, stderr) => {
      if (err) {
        return reject(new Error(`curl exit ${err.code}: ${String(stderr).slice(0, 200)}`));
      }
      try {
        resolve(JSON.parse(stdout));
      } catch (e) {
        reject(new Error(`JSON parse: ${e.message}, body: ${String(stdout).slice(0, 200)}`));
      }
    });
  });
}

async function getUpdates() {
  // Без параметра timeout — TG сразу вернёт [] если нет updates, либо update.
  // Это короткий запрос, который SOCKS5-прокси нормально relay'ит.
  // С long-poll (timeout=N) прокси proxy6.net рвёт idle соединение.
  const url = `https://api.telegram.org/bot${TOKEN}/getUpdates?offset=${offset}&allowed_updates=%5B%22message%22%2C%22callback_query%22%5D`;
  const j = await getUpdatesCurl(url);
  if (!j.ok) {
    throw new Error(`getUpdates returned not-ok: ${JSON.stringify(j).slice(0, 200)}`);
  }
  return j.result || [];
}

/**
 * Передать update в тот же обработчик, что использует webhook.
 * Идём через внутренний HTTP: localhost к Chief самому себе.
 */
async function handleUpdate(update) {
  try {
    const port = require('../config').port;
    const secret = process.env.TG_WEBHOOK_SECRET || '';
    const r = await fetch(`http://127.0.0.1:${port}/api/tg/webhook`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...(secret ? { 'X-Telegram-Bot-Api-Secret-Token': secret } : {})
      },
      body: JSON.stringify(update)
    });
    const text = await r.text().catch(() => '');
    log.debug('forwarded update', { id: update.update_id, status: r.status, len: text.length });
  } catch (e) {
    log.error('handleUpdate failed', { err: e.message, updateId: update.update_id });
  }
}

async function loop() {
  while (!stopRequested) {
    try {
      const updates = await getUpdates();
      if (updates.length > 0) {
        log.info('updates received', { count: updates.length });
        for (const u of updates) {
          if (typeof u.update_id === 'number') {
            offset = Math.max(offset, u.update_id + 1);
          }
          await handleUpdate(u);
        }
        continue;
      }
    } catch (e) {
      log.warn('getUpdates failed', { err: e.message });
      await new Promise(r => setTimeout(r, POLL_INTERVAL_MS));
      continue;
    }
    await new Promise(r => setTimeout(r, POLL_INTERVAL_MS));
  }
  log.info('poller stopped');
}

function start() {
  if (!TOKEN) {
    log.info('poller disabled (TG_BOT_TOKEN missing)');
    return false;
  }
  if (polling) {
    log.warn('poller already running');
    return true;
  }

  if (PROXY_URL) {
    log.info('poller uses SOCKS5 via curl', { proxy: PROXY_URL.replace(/:[^:@]+@/, ':***@') });
  } else {
    log.info('poller uses direct curl (no proxy)');
  }

  polling = true;
  stopRequested = false;
  loop().catch(e => log.error('loop crashed', { err: e.message, stack: e.stack }));
  log.info(`poller started (interval=${POLL_INTERVAL_MS}ms, long_poll=${LONG_POLL_SEC}s)`);
  return true;
}

function stop() {
  stopRequested = true;
  polling = false;
}

function status() {
  return { running: polling, offset, proxy: !!PROXY_URL };
}

module.exports = { start, stop, status };