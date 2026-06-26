/**
 * Chief Agent v2.0 — registry of 13 agents.
 *
 * Транспорт:
 *   type: 'subprocess' → native (subprocess) на VPS (89.108.88.74)
 *   type: 'http'       → native (HTTP fetch) к внешнему сервису
 *   type: 'remote'     → Kednet (Windows, kfigh ноут) через WebSocket
 *
 * 4 native: wishlibrarian, lab_site, coach, experiments_bot
 * 9 remote (WS): publisher, video_skill, image_skill, audio_skill,
 *                seo_advisor, expert_reviews, lead_generator,
 *                content_ideas, wish_market
 *
 * Для remote:
 *   metadata.cwd       = C:\Users\kfigh\<skill>\
 *   metadata.command   = 'python' или абсолютный путь к venv-python
 *   metadata.argsTemplate = ['-u', 'scripts/<entry>.py', '<subcmd>']
 *   metadata.envKeys   = ['YANDEX_API_KEY','TG_BOT_TOKEN',...] — только нужные,
 *                        безопасные для отправки по WS (НЕ VK_ACCESS_TOKEN от pulabru!)
 *
 * Удаление/добавление: см. agents/scaffold.js + api/agents.js.
 */

'use strict';

const path = require('path');

// Tiny helper to build Python venv executable path (для native).
function venvPy(dir) {
  return path.join(dir, '.venv', 'bin', 'python');
}

// ────────────────────────────────────────────────────────────
// Helpers
// ────────────────────────────────────────────────────────────

/**
 * Обёртка для remote-агента: тип 'remote' (WS к Kednet), cwd = C:\Users\kfigh\<skill>,
 * python из .venv если есть, иначе системный 'python'.
 */
function remote({ id, displayName, description, kednetDir, scriptsEntry, argsTemplate,
                  healthcheck = 'ws', envKeys = [], actions = [], enabled = true,
                  defaultPython = 'python' }) {
  return {
    id, displayName, description,
    type: 'remote',
    transport: 'ws',
    healthcheck,
    enabled,
    metadata: {
      cwd: kednetDir,
      command: defaultPython,                 // Kednet-агент сам найдёт .venv\python.exe если есть
      argsTemplate,                          // ['-u', scriptsEntry, ...]
      scriptsEntry,                          // 'scripts/post_channels.py'
      envKeys                                // ['YANDEX_API_KEY', ...]
    },
    actions
  };
}

/**
 * Обёртка для native subprocess на VPS.
 */
function nativeSubprocess({ id, displayName, description, cwd, argsTemplate, envFile,
                            healthcheck = 'state', enabled = true, actions = [],
                            systemdUnit = null, stateFile = null }) {
  const meta = {
    cwd,
    command: venvPy(cwd),
    argsTemplate,
    envFile: envFile || path.join(cwd, '.env')
  };
  if (systemdUnit) meta.systemdUnit = systemdUnit;
  if (stateFile)   meta.stateFile = stateFile;
  return { id, displayName, description, type: 'subprocess', healthcheck, enabled, metadata: meta, actions };
}

/**
 * Обёртка для native HTTP-агента.
 */
function nativeHttp({ id, displayName, description, endpoint, healthcheck = 'http',
                      enabled = true, actions = [], healthUrl = '/health' }) {
  return {
    id, displayName, description, type: 'http', healthcheck, enabled,
    metadata: { endpoint, healthUrl }, actions
  };
}

// ────────────────────────────────────────────────────────────
// Registry (13 agents)
// ────────────────────────────────────────────────────────────

const REGISTRY = [

  // ───── NATIVE on VPS 89.108.88.74 ─────

  nativeSubprocess({
    id: 'wishlibrarian',
    displayName: 'Wish Librarian',
    description: 'Парсит книгу из URL, генерирует summary + workbook + SEO + state',
    cwd: '/opt/wl',
    argsTemplate: ['-u', '-m', 'agent.cli'],
    envFile: '/opt/wl/.env',
    healthcheck: 'systemd',
    systemdUnit: 'wl-librarian.service',
    stateFile: '/opt/wl/output/library',
    actions: [
      {
        id: 'add_book', displayName: 'Добавить книгу',
        params: [
          { name: 'url',   type: 'string',  required: true },
          { name: 'force', type: 'boolean', default: false },
          { name: 'seo',   type: 'boolean', default: true }
        ],
        dryRunSupported: true, estimatedDurationSec: 180
      },
      {
        id: 'list_books', displayName: 'Список книг',
        params: [],
        dryRunSupported: false, estimatedDurationSec: 5
      }
    ]
  }),

  nativeHttp({
    id: 'lab_site',
    displayName: 'lab-site worker',
    description: 'Astro worker на 89.108.88.74: подписки, эксперименты, посты на модерацию',
    endpoint: process.env.LAB_SITE_API_URL || 'https://api.pulab.online',
    healthUrl: '/health',
    actions: [
      { id: 'publish_create', displayName: 'Создать пост (модерация)',
        httpMethod: 'POST', httpPath: '/internal/publish',
        params: [{ name: 'body', type: 'string', required: true }],
        dryRunSupported: false, estimatedDurationSec: 10 },
      { id: 'publish_list', displayName: 'Список постов на модерации',
        httpMethod: 'GET', httpPath: '/internal/publish/list',
        params: [],
        dryRunSupported: false, estimatedDurationSec: 5 },
      { id: 'experiments_list', displayName: 'Список экспериментов',
        httpMethod: 'GET', httpPath: '/api/experiments',
        params: [],
        dryRunSupported: false, estimatedDurationSec: 5 }
    ]
  }),

  nativeHttp({
    id: 'coach',
    displayName: 'Coach Agent',
    description: 'LLM-коуч по желаниям (Render, FastAPI, Phase 8 production)',
    endpoint: process.env.COACH_API_URL || '',
    actions: [
      { id: 'message', displayName: 'Отправить сообщение',
        httpMethod: 'POST', httpPath: '/coach/message',
        params: [
          { name: 'clientId', type: 'string', required: true },
          { name: 'message',  type: 'string', required: true }
        ],
        dryRunSupported: false, estimatedDurationSec: 15 }
    ]
  }),

  nativeSubprocess({
    id: 'experiments_bot',
    displayName: 'experiments_bot',
    description: 'TG-бот для участников экспериментов (community-first, FSM 5 шагов)',
    cwd: '/opt/experiments_bot',
    argsTemplate: ['-u', '-m', 'agent.experiments_bot'],
    envFile: '/opt/experiments_bot/.env',
    healthcheck: 'systemd',
    systemdUnit: 'experiments-bot.service',
    actions: [
      { id: 'restart', displayName: 'Перезапустить сервис',
        isSystemAction: true,
        params: [],
        dryRunSupported: false, estimatedDurationSec: 10 }
    ]
  }),

  // ───── REMOTE через WebSocket к Kednet-агенту ─────

  remote({
    id: 'publisher',
    displayName: 'Publisher',
    description: 'Пост контента в VK/TG/OK/Zen + модерация pending_store',
    kednetDir: 'C:\\Users\\kfigh\\publisher_skill',
    scriptsEntry: 'scripts/post_channels.py',
    argsTemplate: ['-u', 'scripts/post_channels.py'],
    envKeys: ['VK_ACCESS_TOKEN','VK_GROUP_ID','TG_BOT_TOKEN','TG_CHANNEL_ID','OK_ACCESS_TOKEN','OK_GROUP_ID','YANDEX_API_KEY'],
    actions: [
      { id: 'post', displayName: 'Опубликовать',
        params: [
          { name: 'content',  type: 'string', required: true },
          { name: 'channels', type: 'string', default: 'vk,tg' },
          { name: 'image',    type: 'string', required: false }
        ],
        dryRunSupported: true, estimatedDurationSec: 30 },
      { id: 'moderate', displayName: 'Модерация очереди',
        params: [],
        dryRunSupported: false, estimatedDurationSec: 10 }
    ]
  }),

  remote({
    id: 'video_skill',
    displayName: 'Video Creator',
    description: '5 профилей × shot-by-shot сценарии (Phase 1 готова, Phase 2 stub)',
    kednetDir: 'C:\\Users\\kfigh\\video_skill',
    scriptsEntry: 'scripts/video.py',
    argsTemplate: ['-u', 'scripts/video.py', 'script'],
    envKeys: ['YANDEX_API_KEY','PEXELS_API_KEY'],
    actions: [
      { id: 'script', displayName: 'Сгенерировать сценарий',
        params: [
          { name: 'platform', type: 'enum', options: ['tiktok','youtube','vk','telegram','reels'], required: true },
          { name: 'goal',     type: 'enum', options: ['engagement','subscribe','traffic','contest'], required: true },
          { name: 'tone',     type: 'string',  required: true },
          { name: 'duration', type: 'integer', required: true },
          { name: 'source',   type: 'string',  required: true }
        ],
        dryRunSupported: true, estimatedDurationSec: 60 }
    ]
  }),

  remote({
    id: 'image_skill',
    displayName: 'Image Generator',
    description: 'YandexART × 5 форматов × 5 профилей (Phase 1-3 готовы, V3.5+)',
    kednetDir: 'C:\\Users\\kfigh\\image_skill',
    scriptsEntry: 'scripts/image.py',
    argsTemplate: ['-u', 'scripts/image.py', 'generate'],
    envKeys: ['YANDEX_API_KEY','YANDEX_FOLDER_ID','R2_ACCESS_KEY','R2_SECRET_KEY','R2_ENDPOINT','R2_BUCKET','YANDEX_STORAGE_KEY','YANDEX_STORAGE_SECRET'],
    actions: [
      { id: 'generate', displayName: 'Сгенерировать картинку',
        params: [
          { name: 'format',      type: 'enum',   options: ['vk_post','vk_story','pinterest','wb','og'], required: true },
          { name: 'source_text', type: 'string', required: true },
          { name: 'profile',     type: 'string', required: false }
        ],
        dryRunSupported: true, estimatedDurationSec: 30 }
    ]
  }),

  remote({
    id: 'audio_skill',
    displayName: 'Audio Generator',
    description: 'PDF→YAML→TTS→mix (Yandex SpeechKit, 10 треков v5 готовы)',
    kednetDir: 'C:\\Users\\kfigh\\audio_skill',
    scriptsEntry: 'scripts/tts_yandex.py',
    argsTemplate: ['-u', 'scripts/tts_yandex.py'],
    envKeys: ['YANDEX_API_KEY','YANDEX_FOLDER_ID'],
    actions: [
      { id: 'tts', displayName: 'TTS (Yandex SpeechKit)',
        params: [
          { name: 'slug',  type: 'string', required: true },
          { name: 'voice', type: 'string', required: false },
          { name: 'tone',  type: 'enum',   options: ['neutral','lively','gentle'], required: false }
        ],
        dryRunSupported: true, estimatedDurationSec: 90 },
      { id: 'mix', displayName: 'Микс с фоновой музыкой',
        params: [{ name: 'slug', type: 'string', required: true }],
        dryRunSupported: true, estimatedDurationSec: 30 },
      { id: 'list', displayName: 'Каталог треков',
        params: [],
        dryRunSupported: false, estimatedDurationSec: 5 }
    ]
  }),

  remote({
    id: 'seo_advisor',
    displayName: 'SEO Advisor',
    description: '12 режимов оптимизации страниц Лаборатории желаний под Яндекс+Google',
    kednetDir: 'C:\\Users\\kfigh\\seo-advisor-skill',
    scriptsEntry: 'scripts/seo_optimize.py',
    argsTemplate: ['-u', 'scripts/seo_optimize.py'],
    envKeys: ['YANDEX_API_KEY','YANDEX_FOLDER_ID'],
    enabled: true,
    actions: [
      { id: 'optimize', displayName: 'Оптимизировать страницу',
        params: [{ name: 'slug', type: 'string', required: true }],
        dryRunSupported: true, estimatedDurationSec: 60 },
      { id: 'validate_schema', displayName: 'Валидация Schema.org',
        params: [{ name: 'slug', type: 'string', required: true }],
        dryRunSupported: false, estimatedDurationSec: 5 }
    ]
  }),

  remote({
    id: 'expert_reviews',
    displayName: 'Expert Reviews Hub',
    description: '13 команд, 4 парсера (LiveLib/Литрес/VK/stats), экспертные рекомендации',
    kednetDir: 'C:\\Users\\kfigh\\expert-reviews-hub',
    scriptsEntry: 'scripts/review_stats.py',
    argsTemplate: ['-u', 'scripts/review_stats.py'],
    envKeys: ['YANDEX_API_KEY'],
    enabled: true,
    actions: [
      { id: 'parse_litres', displayName: 'Парсер Литрес',
        params: [{ name: 'book_id', type: 'string', required: true }],
        dryRunSupported: true, estimatedDurationSec: 30 },
      { id: 'parse_livelib', displayName: 'Парсер LiveLib',
        params: [{ name: 'book_id', type: 'string', required: true }],
        dryRunSupported: true, estimatedDurationSec: 30 }
    ]
  }),

  remote({
    id: 'lead_generator',
    displayName: 'Lead Generator',
    description: '22 команды, 9 скриптов, spy-модуль (ads.vk/tgstat/otzovik)',
    kednetDir: 'C:\\Users\\kfigh\\lead_generator_skill',
    scriptsEntry: 'scripts/segment_recommender.py',
    argsTemplate: ['-u', 'scripts/segment_recommender.py'],
    envKeys: ['YANDEX_API_KEY','VK_ADS_TOKEN','TGSTAT_TOKEN'],
    enabled: true,
    actions: [
      { id: 'segments', displayName: 'Сегменты ЦА',
        params: [{ name: 'niche', type: 'string', required: true }],
        dryRunSupported: true, estimatedDurationSec: 60 },
      { id: 'wordstat', displayName: 'Wordstat',
        params: [{ name: 'query', type: 'string', required: true }],
        dryRunSupported: false, estimatedDurationSec: 15 }
    ]
  }),

  remote({
    id: 'content_ideas',
    displayName: 'Content Ideas',
    description: '12 скриптов: trending, идеи из болей, календарь, экспорт в publisher',
    kednetDir: 'C:\\Users\\kfigh\\content_ideas_skill',
    scriptsEntry: 'scripts/generate_ideas.py',
    argsTemplate: ['-u', 'scripts/generate_ideas.py'],
    envKeys: ['YANDEX_API_KEY'],
    enabled: true,
    actions: [
      { id: 'generate', displayName: 'Сгенерировать идеи',
        params: [
          { name: 'theme', type: 'string',  required: true },
          { name: 'count', type: 'integer', default: 5 }
        ],
        dryRunSupported: true, estimatedDurationSec: 30 }
    ]
  }),

  remote({
    id: 'wish_market',
    displayName: 'Wish Market',
    description: 'Каталог желаний × 8 сфер жизни (v0.1 MVP, без БД)',
    kednetDir: 'C:\\Users\\kfigh\\wish_market',
    scriptsEntry: 'scripts/curate_wishes.py',
    argsTemplate: ['-u', 'scripts/curate_wishes.py'],
    envKeys: ['YANDEX_API_KEY'],
    enabled: true,
    actions: [
      { id: 'curate', displayName: 'Курировать сферу',
        params: [
          { name: 'sphere', type: 'string',  required: true },
          { name: 'count',  type: 'integer', default: 18 }
        ],
        dryRunSupported: true, estimatedDurationSec: 60 }
    ]
  })

];

module.exports = REGISTRY;
