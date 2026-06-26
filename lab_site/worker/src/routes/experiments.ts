/**
 * Experiments: «Эксперименты читателей» — форма /my-experiment/.
 *
 * Стратегия community-first (2026-06-18): истории участников сообщества
 * становятся главным контентом. Лаборатория — равноправный участник, не «админ».
 *
 * Поток:
 *   1. POST /api/experiments          — создать эксперимент (анонимно или с именем)
 *   2. KV: experiment:<id>            — запись (id, name, source, did, got, allowPublish, status, ts, ip)
 *   3. Rate-limit: rl:experiments:ip:<ip> (5/час)
 *   4. Уведомление Лаборатории в TG + email (если настроено)
 *
 * Модерация (с 2026-06-19):
 *   - status: 'new'        — только что пришла, не видна публично
 *   - status: 'approved'   — одобрена, видна в /experiments/ и публичном фиде
 *   - status: 'rejected'   — отклонена, скрыта
 *   - По умолчанию всё 'new'. Лаборатория модерирует через /admin/experiments/.
 *
 * TG-уведомления (2026-06-19):
 *   - POST    → "новый эксперимент, ждёт модерации"
 *   - PATCH   → "одобрен / отклонён / возвращён в new" + ссылка на /experiments/
 *   - DELETE  → "удалён (пометка для лога)"
 *   Код работает, даже если TELEGRAM_BOT_TOKEN/TELEGRAM_ADMIN_ID не заданы —
 *   просто молча выходим (проверка в TelegramAdapter.sendToAdmin).
 *   Чтобы включить: задать TELEGRAM_BOT_TOKEN и TELEGRAM_ADMIN_ID в /etc/lab-site.env.
 *
 * Эндпоинты:
 *   POST   /api/experiments              — публичный (форма, TG-бот, Mini App)
 *   GET    /api/experiments/public       — публичный, только status='approved' (для /experiments/)
 *   GET    /api/experiments/count        — публичный, общий счётчик
 *   GET    /api/experiments              — ЗАЩИЩЁННЫЙ (X-Admin-Token), для админки
 *   PATCH  /api/experiments/:id          — ЗАЩИЩЁННЫЙ (X-Admin-Token), смена status
 *   DELETE /api/experiments/:id          — ЗАЩИЩЁННЫЙ (X-Admin-Token), удаление
 */
import { Hono } from 'hono';
import type { Env } from '../types';
import { TelegramAdapter } from '../lib/social_tg';
import { sendEmail } from '../lib/email';

const app = new Hono<{ Bindings: Env }>();

const RL_IP_LIMIT = 5;
const RL_IP_TTL_SEC = 3600;

// Простая защита от пустых полей и спама
const NAME_MAX = 60;
const DID_MIN = 30;
const DID_MAX = 1000;
const GOT_MIN = 30;
const GOT_MAX = 1000;
const SOURCE_MAX = 200;

// Кнопки, которые мы добавляем в уведомления о модерации
const MODERATE_PUBLIC_URL = 'https://app.pulab.online/experiments/';
const MODERATE_ADMIN_URL = 'https://app.pulab.online/admin/experiments/';

function clientIp(c: { req: { raw: Request } }): string {
  const r = c.req.raw;
  return (
    r.headers.get('cf-connecting-ip') ??
    (r.headers.get('x-forwarded-for') ?? '').split(',')[0].trim() ??
    r.headers.get('x-real-ip') ??
    'unknown'
  );
}

function genId(): string {
  // Короткий читаемый ID: дата (YYYYMMDD) + случайный 6-char base36
  const d = new Date();
  const ymd = `${d.getUTCFullYear()}${String(d.getUTCMonth() + 1).padStart(2, '0')}${String(d.getUTCDate()).padStart(2, '0')}`;
  const rand = Math.random().toString(36).slice(2, 8);
  return `${ymd}-${rand}`;
}

function escapeHtml(s: string): string {
  return s
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

interface ExperimentPayload {
  name?: string;
  bookSlug?: string;
  bookTitle?: string;
  source?: string; // откуда идея: книга, подкаст, жизненная ситуация, что угодно (community-first, опц.)
  did?: string;
  got?: string;
  allowPublish?: boolean;
  hp?: string;
}

// ────────────────────────────────────────────────
// Уведомления Лаборатории в Telegram (модератору в личку).
//
// Используется из POST/PATCH/DELETE. Если TELEGRAM_BOT_TOKEN
// или TELEGRAM_ADMIN_ID не заданы в /etc/lab-site.env — просто
// логируем в stdout и идём дальше (без падений).
//
// Кнопки ведут:
//   - "Открыть в админке" — на /admin/experiments/?token=... (нужен ADMIN_TOKEN в URL)
//   - "Открыть на сайте"  — на /experiments/ (если approved)
// ────────────────────────────────────────────────
async function notifyLab(
  env: Env,
  title: string,
  record: { id: string; name: string; source: string; did: string; got: string; allowPublish: boolean; ip?: string; status?: string },
  buttons: 'moderate' | 'open_site' | 'log_only' = 'moderate',
): Promise<void> {
  if (!env.TELEGRAM_BOT_TOKEN || !env.TELEGRAM_ADMIN_ID) {
    console.log(
      '[experiments:notify-skipped]',
      title,
      'id=' + record.id,
      'name=' + record.name,
      '(no TELEGRAM_BOT_TOKEN / TELEGRAM_ADMIN_ID)',
    );
    return;
  }
  try {
    const tg = new TelegramAdapter(env);
    const truncatedDid = record.did.length > 500 ? record.did.slice(0, 500) + '…' : record.did;
    const truncatedGot = record.got.length > 500 ? record.got.slice(0, 500) + '…' : record.got;
    const text =
      `${title}\n\n` +
      `💡 Откуда: ${record.source || '(не указано)'}\n` +
      `👤 Имя: ${record.name}\n` +
      (record.allowPublish ? `✅ Согласие на публикацию\n` : `⛔ Без публикации\n`) +
      (record.status ? `📊 Статус: ${record.status}\n` : '') +
      (record.ip ? `🌐 IP: ${record.ip}\n` : '') +
      `\n🧪 Что пробовали:\n${truncatedDid}\n\n` +
      `📝 Что получилось:\n${truncatedGot}\n\n` +
      `ID: ${record.id}`;

    let kb: { text: string; url: string }[][] | undefined;
    if (buttons === 'moderate') {
      kb = [
        [{ text: '🔧 Открыть в админке', url: MODERATE_ADMIN_URL }],
      ];
    } else if (buttons === 'open_site') {
      kb = [
        [{ text: '🌐 Открыть на сайте', url: MODERATE_PUBLIC_URL }],
        [{ text: '🔧 В админку', url: MODERATE_ADMIN_URL }],
      ];
    }
    await tg.sendToAdmin(text, kb);
  } catch (err) {
    console.error('[experiments:notify-failed]', err);
  }
}

// ────────────────────────────────────────────────
// POST /api/experiments
// Body: { name?, source?, did, got, allowPublish, hp? }
//
// Поля:
//   - name         — имя/псевдоним (опционально, до 60 знаков), может быть пустым
//   - source       — откуда идея (книга, подкаст, жизненная ситуация, что угодно)
//   - did          — что пробовали (30-1000 знаков)
//   - got          — что получилось (30-1000 знаков)
//   - allowPublish — согласие на публикацию в подборке (bool)
//   - hp           — honeypot (антиспам)
// ────────────────────────────────────────────────
app.post('/api/experiments', async (c) => {
  let body: ExperimentPayload;
  try {
    body = await c.req.json();
  } catch {
    return c.json({ error: 'bad_request', message: 'Нужен JSON' }, 400);
  }

  // Honeypot: если скрытое поле заполнено — это бот.
  if (body.hp && body.hp.trim() !== '') {
    console.log('[experiments] honeypot triggered, ip=', clientIp(c));
    return c.json({ ok: true });
  }

  const ip = clientIp(c);

  // Rate-limit по IP
  const rlKey = `rl:experiments:ip:${ip}`;
  const rlCount = parseInt((await c.env.LAB_KV.get(rlKey)) ?? '0', 10);
  if (rlCount >= RL_IP_LIMIT) {
    return c.json(
      { error: 'rate_limited', message: 'Слишком много попыток. Попробуйте через час.' },
      429,
    );
  }

  // Валидация
  const name = (body.name ?? '').trim().slice(0, NAME_MAX);
  // Источник идеи (community-first, опц.): книга, подкаст, жизненная ситуация, что угодно.
  // Бот шлёт `source` напрямую, старая веб-форма — `bookTitle`. Поддерживаем оба.
  const bookSlug = (body.bookSlug ?? '').trim().slice(0, 120);
  const bookTitle = (body.bookTitle ?? '').trim().slice(0, 200);
  const source = (body.source ?? '').trim().slice(0, SOURCE_MAX) || bookTitle || bookSlug;
  const did = (body.did ?? '').trim();
  const got = (body.got ?? '').trim();
  const allowPublish = body.allowPublish === true;

  // Источник НЕ обязателен — community-first: человек делится ЛЮБЫМ опытом.
  // Главное — did и got.
  if (did.length < DID_MIN) {
    return c.json(
      { error: 'did_too_short', message: `Расскажите подробнее, что вы пробовали (от ${DID_MIN} знаков)` },
      400,
    );
  }
  if (did.length > DID_MAX) {
    return c.json(
      { error: 'did_too_long', message: `Слишком длинно — максимум ${DID_MAX} знаков` },
      400,
    );
  }
  if (got.length < GOT_MIN) {
    return c.json(
      { error: 'got_too_short', message: `Расскажите, что получилось (от ${GOT_MIN} знаков)` },
      400,
    );
  }
  if (got.length > GOT_MAX) {
    return c.json(
      { error: 'got_too_long', message: `Слишком длинно — максимум ${GOT_MAX} знаков` },
      400,
    );
  }
  if (name.length === 0 && !allowPublish) {
    // Если человек не указал имя И не дал согласие — у нас нет способа его идентифицировать.
    // Это не ошибка, но дадим мягкий отклик.
  }

  // Запись
  const id = genId();
  const record = {
    id,
    name: name || 'участник сообщества',
    bookSlug, // legacy: остаётся для совместимости со старой веб-формой
    bookTitle, // legacy
    source, // community-first: откуда идея (книга/подкаст/жизнь/любое)
    did,
    got,
    allowPublish,
    ts: new Date().toISOString(),
    ip,
    status: 'new' as 'new' | 'approved' | 'rejected',
  };
  await c.env.LAB_KV.put(`experiment:${id}`, JSON.stringify(record));

  // Rate-limit инкремент
  await c.env.LAB_KV.put(rlKey, String(rlCount + 1), { expirationTtl: RL_IP_TTL_SEC });

  // Уведомление Лаборатории в TG (если настроен бот + admin_id)
  // Используем общий helper notifyLab — кнопка ведёт в админку.
  await notifyLab(
    c.env,
    '🧪 Новый эксперимент читателя',
    {
      id,
      name: record.name,
      source,
      did,
      got,
      allowPublish,
      ip,
      status: 'new',
    },
    'moderate',
  );

  // Уведомление по email (если SMTP настроен)
  try {
    if (c.env.SMTP_HOST && c.env.SMTP_USER) {
      await sendEmail(c.env, {
        to: 'hello@pulabru.ru',
        subject: `[ЛАБОРАТОРИЯ] Новый эксперимент: ${source || '(без источника)'}`,
        text: [
          `Новый эксперимент от читателя`,
          ``,
          `Откуда идея: ${source || '(не указано)'}`,
          `Имя: ${record.name}`,
          `Согласие на публикацию: ${allowPublish ? 'да' : 'нет'}`,
          ``,
          `Что пробовали:`,
          did,
          ``,
          `Что получилось:`,
          got,
          ``,
          `ID: ${id}`,
          `IP: ${ip}`,
          `Время: ${record.ts}`,
        ].join('\n'),
        html: `<!doctype html><html><body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; padding: 20px;">
<h2 style="color: #881337;">Новый эксперимент от читателя</h2>
<p><strong>Откуда идея:</strong> ${escapeHtml(source || '(не указано)')}<br>
<strong>Имя:</strong> ${escapeHtml(record.name)}<br>
<strong>Согласие на публикацию:</strong> ${allowPublish ? 'да' : 'нет'}</p>

<h3 style="color: #881337;">Что пробовали</h3>
<p style="white-space: pre-wrap;">${escapeHtml(did)}</p>

<h3 style="color: #881337;">Что получилось</h3>
<p style="white-space: pre-wrap;">${escapeHtml(got)}</p>

<hr>
<p style="font-size: 12px; color: #6b3a4a;">
ID: ${id}<br>
IP: ${ip}<br>
Время: ${record.ts}
</p>
</body></html>`,
      });
    }
  } catch (err) {
    console.error('[experiments] email-notify-failed', err);
  }

  return c.json({
    ok: true,
    id,
    message: allowPublish
      ? 'Спасибо! История попадёт в ближайшую подборку экспериментов.'
      : 'Спасибо! Мы получили вашу историю. Если захотите поделиться ею публично — отметьте галочку согласия.',
  });
});

// ────────────────────────────────────────────────
// Хелпер: проверка admin-токена (constant-time compare)
// ────────────────────────────────────────────────
function checkAdmin(c: { env: Env; req: { raw: Request } }): boolean {
  const expected = c.env.ADMIN_TOKEN;
  if (!expected) return false; // если токен не задан в env — закрыт для всех
  const got =
    c.req.raw.headers.get('x-admin-token') ??
    c.req.raw.headers.get('X-Admin-Token') ??
    '';
  // constant-time compare чтобы не было timing-атак
  if (got.length !== expected.length) return false;
  let diff = 0;
  for (let i = 0; i < got.length; i++) {
    diff |= got.charCodeAt(i) ^ expected.charCodeAt(i);
  }
  return diff === 0;
}

// ────────────────────────────────────────────────
// GET /api/experiments/count — публичный счётчик
// ────────────────────────────────────────────────
app.get('/api/experiments/count', async (c) => {
  let count = 0;
  let cursor: string | undefined;
  for (let i = 0; i < 50; i++) {
    const page = await c.env.LAB_KV.list({ prefix: 'experiment:', cursor, limit: 1000 });
    for (const k of page.keys) {
      if (!k.name.startsWith('experiment:')) continue;
      if (k.name.includes(':list')) continue;
      count++;
    }
    if (!page.list_complete) {
      cursor = page.cursor;
    } else {
      break;
    }
  }
  return c.json({ ok: true, count });
});

// ────────────────────────────────────────────────
// GET /api/experiments/public — только status='approved' (для /experiments/)
// Без авторизации. Без IP/имени (только то, что согласился на публикацию).
// ────────────────────────────────────────────────
app.get('/api/experiments/public', async (c) => {
  const limit = Math.min(parseInt(c.req.query('limit') ?? '50', 10), 100);
  const items: Array<Record<string, unknown>> = [];
  let cursor: string | undefined;
  for (let i = 0; i < 10; i++) {
    const page = await c.env.LAB_KV.list({ prefix: 'experiment:', cursor, limit: 1000 });
    for (const k of page.keys) {
      if (k.name.includes(':list')) continue;
      const v = await c.env.LAB_KV.get(k.name);
      if (!v) continue;
      try {
        const rec = JSON.parse(v);
        if (rec.status !== 'approved') continue;
        if (rec.allowPublish !== true) continue; // двойная защита: и status и галочка
        // Публикуем только безопасные поля (без IP, без id для анонимности если нужно)
        items.push({
          id: rec.id,
          name: rec.name,
          source: rec.source,
          did: rec.did,
          got: rec.got,
          ts: rec.ts,
        });
      } catch {
        /* ignore */
      }
    }
    if (!page.list_complete) {
      cursor = page.cursor;
    } else {
      break;
    }
  }
  items.sort((a, b) => String(b.ts).localeCompare(String(a.ts)));
  return c.json({ ok: true, items: items.slice(0, limit), total: items.length });
});

// ────────────────────────────────────────────────
// GET /api/experiments — ЗАЩИЩЁННЫЙ (X-Admin-Token), для админки
// Возвращает ВСЕ записи (все статусы, IP, всё) — только для модерации.
// ────────────────────────────────────────────────
app.get('/api/experiments', async (c) => {
  if (!checkAdmin(c)) {
    return c.json({ error: 'unauthorized', message: 'Нужен X-Admin-Token' }, 401);
  }
  const limit = Math.min(parseInt(c.req.query('limit') ?? '50', 10), 200);
  const statusFilter = c.req.query('status'); // опц.: 'new' | 'approved' | 'rejected'
  const items: Array<Record<string, unknown>> = [];
  let cursor: string | undefined;
  for (let i = 0; i < 10; i++) {
    const page = await c.env.LAB_KV.list({ prefix: 'experiment:', cursor, limit: 1000 });
    for (const k of page.keys) {
      if (k.name.includes(':list')) continue;
      const v = await c.env.LAB_KV.get(k.name);
      if (!v) continue;
      try {
        const rec = JSON.parse(v);
        if (statusFilter && rec.status !== statusFilter) continue;
        items.push(rec);
      } catch {
        /* ignore */
      }
    }
    if (!page.list_complete) {
      cursor = page.cursor;
    } else {
      break;
    }
  }
  items.sort((a, b) => String(b.ts).localeCompare(String(a.ts)));
  return c.json({ ok: true, items: items.slice(0, limit), total: items.length });
});

// ────────────────────────────────────────────────
// PATCH /api/experiments/:id — ЗАЩИЩЁННЫЙ, смена status (модерация)
// Body: { status: 'approved' | 'rejected' | 'new' }
// ────────────────────────────────────────────────
app.patch('/api/experiments/:id', async (c) => {
  if (!checkAdmin(c)) {
    return c.json({ error: 'unauthorized', message: 'Нужен X-Admin-Token' }, 401);
  }
  const id = c.req.param('id');
  if (!/^\d{8}-[a-z0-9]{6}$/.test(id)) {
    return c.json({ error: 'bad_id', message: 'Неверный формат id' }, 400);
  }
  let body: { status?: string };
  try {
    body = await c.req.json();
  } catch {
    return c.json({ error: 'bad_request', message: 'Нужен JSON' }, 400);
  }
  const status = body.status;
  if (status !== 'approved' && status !== 'rejected' && status !== 'new') {
    return c.json(
      { error: 'bad_status', message: "status должен быть 'new' | 'approved' | 'rejected'" },
      400,
    );
  }
  const raw = await c.env.LAB_KV.get(`experiment:${id}`);
  if (!raw) {
    return c.json({ error: 'not_found', message: 'История не найдена' }, 404);
  }
  let rec: Record<string, unknown>;
  try {
    rec = JSON.parse(raw);
  } catch {
    return c.json({ error: 'corrupt_record', message: 'Запись повреждена' }, 500);
  }
  rec.status = status;
  rec.moderatedAt = new Date().toISOString();
  await c.env.LAB_KV.put(`experiment:${id}`, JSON.stringify(rec));

  // Уведомление о решении модерации (только approved/rejected — new просто возврат, шумно)
  if (status === 'approved' || status === 'rejected') {
    const emoji = status === 'approved' ? '✅' : '⛔';
    const recSource = (rec.source as string) ?? '';
    await notifyLab(
      c.env,
      `${emoji} Модерация: ${status === 'approved' ? 'одобрено' : 'отклонено'}\n«${recSource || '(без источника)'}»`,
      {
        id: rec.id as string,
        name: rec.name as string,
        source: recSource,
        did: rec.did as string,
        got: rec.got as string,
        allowPublish: rec.allowPublish as boolean,
        ip: rec.ip as string,
        status,
      },
      status === 'approved' ? 'open_site' : 'moderate',
    );
  }

  return c.json({ ok: true, id, status });
});

// ────────────────────────────────────────────────
// DELETE /api/experiments/:id — ЗАЩИЩЁННЫЙ, удаление (для чистки спама)
// ────────────────────────────────────────────────
app.delete('/api/experiments/:id', async (c) => {
  if (!checkAdmin(c)) {
    return c.json({ error: 'unauthorized', message: 'Нужен X-Admin-Token' }, 401);
  }
  const id = c.req.param('id');
  if (!/^\d{8}-[a-z0-9]{6}$/.test(id)) {
    return c.json({ error: 'bad_id', message: 'Неверный формат id' }, 400);
  }
  const raw = await c.env.LAB_KV.get(`experiment:${id}`);
  if (!raw) {
    return c.json({ error: 'not_found', message: 'История не найдена' }, 404);
  }
  await c.env.LAB_KV.delete(`experiment:${id}`);

  // Лог-уведомление об удалении (для аудита спам-чисток)
  try {
    let parsed: { name?: string; source?: string; did?: string; got?: string; allowPublish?: boolean; ip?: string } = {};
    try { parsed = JSON.parse(raw); } catch { /* ignore */ }
    await notifyLab(
      c.env,
      '🗑 Удалён эксперимент (модераторская чистка)',
      {
        id,
        name: parsed.name ?? '—',
        source: parsed.source ?? '',
        did: parsed.did ?? '',
        got: parsed.got ?? '',
        allowPublish: parsed.allowPublish ?? false,
        ip: parsed.ip,
      },
      'log_only',
    );
  } catch (err) {
    console.error('[experiments] delete-notify-failed', err);
  }

  return c.json({ ok: true, id, deleted: true });
});

export default app;