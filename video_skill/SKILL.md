---
name: Video
description: Универсальный генератор коротких видео для экосистемы kfigh. 5 проектов (lab/wl/coach/experts/market) через профили. 3 режима (C-сценарии/A-auto/B-manual) × 4 фазы. Phase 1 (MVP) — C-режим.
allowed-tools: [Read, Write, Bash, WebFetch, Glob, Grep]
---

# Skill v0.1 (MVP) — Video Creator, 1 фаза из 4

Ты — **оркестратор видео-контента** для экосистемы «Лаборатория желаний» и 4 других проектов. Берёшь тему/идею → генерируешь сценарий (Phase 1) → собираешь mp4 (Phase 2) → публикуешь в 4 канала (Phase 4).

**Phase 1 (MVP, реализовано):** C-режим — генерация shot-by-shot сценариев через LLM для 5 профилей (lab/wl/coach/experts/market). Идемпотентность, dry-run, валидация, override-матрица.

**Phase 2/3/4:** ЗАГЛУШКИ. Код скелетов на месте, реализация — следующие сессии.

## 🎯 РЕЖИМЫ РАБОТЫ

| Маршрут | Команда | Что делает | Phase |
|---|---|---|---|
| `/video script` | `python scripts/video.py script <platform> <goal> <tone> <duration> <source> [--profile=X]` | Генерирует сценарий через LLM (или stub). 5 профилей. | **1 ✅** |
| `/video profile` | `python scripts/video.py profile list\|show\|validate [name]` | Список/просмотр/валидация профилей | **1 ✅** |
| `/video state` | `python scripts/video.py state show\|list\|reset [slug_id]` | Идемпотентность — показать/сбросить state | **1 ✅** |
| `/video validate` | `python scripts/video.py validate <path>` | Валидировать .md сценарий | **1 ✅** |
| `/video auto` | `python scripts/video.py auto ... --from-script=<slug>` | Pexels+Pixabay+ffmpeg+TTS+subs+BGM+watermark → mp4 | **2 ⚠ STUB** |
| `/video manual` | `python scripts/video.py manual ... --timestamps="..."` | yt-dlp + multi-trim + concat → highlights mp4 | **3 ⚠ STUB** |
| `/video publish` | `python scripts/video.py publish <slug_id> --channels=vk,tg,ok,zen` | R2 + Astro + 4 канала публикации | **4 ⚠ STUB** |

## 🧠 АЛГОРИТМ `/video script <platform> <goal> <tone> <duration> <source> --profile=<name>`

### Шаг 0. Идемпотентность
- Прочитай `state/<profile>/<slug>.json` (если есть). Уже сделанное не повторяй.
- Если `status == script_ready` и не было `--force` → «уже есть сценарий, используйте --force».

### Шаг 1. resolve_params (override-матрица)
- См. `sub-skills/profile-system.md`. CLI-флаг → profile.defaults → profile.branding.
- Обязательные: `platform`, `tone`, `goal`, `duration`. Иначе ValueError.

### Шаг 2. build_prompt
- Собрать `system` (схема JSON) + `user` (параметры + контекст профиля).
- Профиль инъектируется: `display_name`, `description`, `watermark`, `hashtags_base`, `source_domains`, `cta_profiles[tone]`.
- Документация промпта: `prompts/script-generate.md`.

### Шаг 3. LLM-вызов
- `llm_factory.generate_script_json(system, user, profile_meta)` — singleton из `wish_librarian/agent/ai/factory.py`.
- Парсит `text → dict` через `json.loads` + regex fallback.
- При ошибке → `stub_script()` (валидный шаблон, не throw).

### Шаг 4. render_markdown
- JSON → markdown с frontmatter-JSON + таблица шотов + CTA + caption + hashtags.
- Сохраняет в `tmp/scripts/<profile>/<slug>.md`.

### Шаг 5. state.update
- `state/<profile>/<slug>.json` — `status="script_ready"`, `script_at`, `script_path`.
- Если ошибка — `status="failed"`, `error=<msg>`.

### Шаг 6. Вывод
- Печатает: путь к .md, путь к state, title, количество шотов.

## 📂 ГДЕ ЧТО

```
video_skill/
├── SKILL.md (этот файл)              # оркестратор
├── README.md                          # человеческое описание
├── CHANGELOG.md                       # v0.1
├── .env.example                       # PROFILE_DEFAULT + Phase 2+ ключи
│
├── commands/                          # рецепты для пользователя
│   ├── video-script.md
│   ├── video-profile.md
│   ├── video-auto.md (Phase 2 stub)
│   ├── video-manual.md (Phase 3 stub)
│   └── video-publish.md (Phase 4 stub)
│
├── sub-skills/                        # детали режимов
│   ├── profile-system.md              # NEW v1.0: override-матрица
│   ├── script-mode.md                 # C-режим детально
│   ├── auto-mode.md (Phase 2 stub)
│   ├── manual-mode.md (Phase 3 stub)
│   ├── ffmpeg-pipeline.md             # Phase 2+ ffmpeg reference
│   └── publish-flow.md (Phase 4 stub)
│
├── prompts/                           # plain MD промпты
│   ├── script-generate.md             # главный LLM-промпт
│   ├── profile-context.md             # NEW v1.0: инъекция профиля
│   ├── clip-keywords.md (Phase 2 stub)
│   └── announce-text.md (Phase 4 stub)
│
├── templates/                         # markdown-шаблоны
│   ├── script-{tiktok,youtube,vk,telegram,reels}.md
│   └── script-pacing.md (Phase 2 stub)
│
├── scripts/                           # Python
│   ├── video.py                       # orchestrator
│   ├── cmd_script.py                  # C-режим
│   ├── cmd_profile.py                 # NEW v1.0: list/show/validate
│   ├── cmd_{auto,manual,publish}.py    # Phase 2/3/4 stubs
│   ├── state.py                       # идемпотентность (path: state/<profile>/<slug>.json)
│   ├── slugify.py                     # копия publisher_skill
│   ├── llm_factory.py                 # NEW: обёртка над wish_librarian/agent/ai/factory
│   ├── validate_script.py             # validate подкоманда
│   ├── _video_common.py               # load_env, now_iso, paths
│   ├── parse_timestamps.py            # Phase 3 stub
│   ├── tts_pipeline.py                # Phase 2 stub
│   ├── {pexels,pixabay}_client.py     # Phase 2 stubs
│   ├── fetch_clips.py                 # Phase 2 stub
│   ├── burn_subs.py                   # Phase 2 stub
│   ├── concat_clips.py                # Phase 3 stub
│   ├── mix_video.py                   # Phase 2 stub
│   ├── upload_r2.py                   # Phase 4 stub
│   ├── render_video.py                # Phase 4 stub
│   ├── announce_video.py              # Phase 4 stub
│   └── source_loader.py               # Phase 3 stub
│
├── data/                              # каталоги + профили
│   ├── platforms.yaml                 # 5 платформ (aspect, safe_zones)
│   ├── voice_map.yaml                 # тон → голос Yandex
│   ├── bgm_catalog.yaml (Phase 2 stub)
│   ├── presets/9x16-h264.json (Phase 2 stub)
│   ├── profiles/                      # NEW v1.0
│   │   ├── lab.yaml                   # ПОЛНЫЙ (по брендбуку)
│   │   ├── wl.yaml (заглушка)
│   │   ├── coach.yaml (заглушка)
│   │   ├── experts.yaml (заглушка)
│   │   └── market.yaml (заглушка)
│   └── library/.gitkeep
│
├── examples/                          # 1 полный + 4 заглушки
│   ├── lab-5-oshibok-karty-zhelaniy.md
│   ├── wl-promo-novaya-kniga.md
│   ├── coach-modul-1-explainer.md
│   ├── experts-mini-interview.md
│   └── market-wish-of-day.md
│
├── references/                        # справка
│   ├── ffmpeg-cheatsheet.md
│   ├── yandex-voices.md
│   └── pexels-pixabay-limits.md
│
├── assets/
│   ├── fonts/, frames/, watermark/    # Phase 2+
│
├── state/                             # runtime: state/<profile>/<slug>.json
├── tmp/                               # runtime: tmp/scripts/<profile>/<slug>.md
└── logs/
```

## 🔗 СВЯЗИ

- **`wish_librarian/agent/ai/factory.py`** — LLM-клиент (singleton, lazy import). API: `generate(system, user) → str` (TEXT, не JSON — парсим руками)
- **`audio_skill/scripts/tts_yandex.py`** — TTS-клиент (Phase 2). Голоса: alena/jane/filipp/ermil/marina/madirus/zahar
- **`publisher_skill/scripts/post_channels.py`** — multi-channel адаптер для Phase 4 (4 канала: VK/TG/OK/Дзен)
- **`publisher_skill/scripts/deploy_pages.py`** — Astro build + scp на VPS
- **`publisher_skill/scripts/notify_admin.py`** — admin-уведомления
- **`seo-advisor-skill`** — SEO-пакет для Astro-страницы видео (Phase 4)
- **`content_ideas_skill`** — вход для идей
- **`expert-reviews-hub`** — вход в `auto --from-review=<slug>` (Phase 4.5)
- **`coach_agent`** — модули 1-5 → темы для `coach`-профиля

## ⚙️ КОНФИГ (.env)

```env
PROFILE_DEFAULT=lab              # default-профиль, если не передан --profile
WL_ROOT=C:/Users/kfigh/wish_librarian   # путь к LLM-фабрике
PUBLISHER_SKILL_ROOT=C:/Users/kfigh/publisher_skill
LAB_SITE_ROOT=C:/Users/kfigh/lab_site

# Phase 2 (auto)
PEXELS_API_KEY=...
PIXABAY_API_KEY=...
YANDEX_SPEECHKIT_API_KEY=...
FFMPEG_BIN=C:/tools/ffmpeg/bin/ffmpeg.exe

# Phase 4 (publish)
CF_ACCOUNT_ID=...
CF_R2_BUCKET=pulab-video
TG_BOT_TOKEN=...
VK_ACCESS_TOKEN=...
OK_ACCESS_TOKEN=...
```

## 🚦 СТАТУСЫ В state/<profile>/<slug>.json

```json
{
  "slug": "5-oshibok-karty-zhelaniy",
  "profile": "lab",
  "status": "draft | script_ready | fetched | rendered | mixed | exported | published | failed",
  "title": "...",
  "created_at": "...",
  "script_at": "...",
  "script_path": "...",
  "channels_posted": {"tg": null, "vk": null, "email": null, "ok": null, "zen": null},
  "channels_failed": [],
  "error": null
}
```

**Pipeline:** `draft → script_ready → fetched → rendered → mixed → exported → published` (или `failed`).

**Phase 1 реализует:** `draft → script_ready` (через `cmd_script.py`).

## 🚧 ИЗВЕСТНЫЕ ОГРАНИЧЕНИЯ (MVP v0.1)

- ❌ **Не генерируется видео** (mp4) — только сценарии (Phase 2)
- ❌ **Не работает с Pexels/Pixabay/ffmpeg/TTS** — стабы
- ❌ **LLM-фабрика:** если LLM-ключ отсутствует → fallback на stub
- ❌ **Watermark пока не рисуется** в видео (Phase 2)
- ❌ **Публикация не работает** (Phase 4)
- ❌ **Astro-страница видео** не создаётся (Phase 4)

**Что работает уже сегодня:**
- ✅ Генерация сценариев для 5 проектов через LLM (или stub)
- ✅ Идемпотентность (`script_ready` + `--force`)
- ✅ Dry-run (показывает промпт без генерации)
- ✅ 5 профилей с override-матрицей
- ✅ Валидация (≥3 шота, duration±2 сек, ≥5 хештегов, CTA)
- ✅ State-менеджмент (show/list/reset)

## Следующий шаг

**Phase 2 (~6-8 ч):** A-режим (auto). Требует от kfigh:
- PEXELS_API_KEY (https://www.pexels.com/api/) — 2 мин
- PIXABAY_API_KEY (https://pixabay.com/service/about/api/) — 2 мин
- YANDEX_SPEECHKIT_API_KEY (переиспользовать от audio_skill) — 0 мин
