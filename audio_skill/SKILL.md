---
name: Audio
description: Скил-аудио-продюсер «Лаборатории желаний». Берёт скрипты из PDF/text/YAML, прогоняет через LLM-адаптер (тон, паузы, плейсхолдеры), синтезирует mp3 через Yandex SpeechKit, миксует с фоновой музыкой через ffmpeg, заливает в Cloudflare R2, рендерит страницу с HTML5-плеером на lab_site и анонсирует в TG + VK + email через publisher_skill. Триггеры: ручной /publish-audio, /adapt-pdf, watcher на data/library/.
allowed-tools:
  - Read
  - Write
  - Bash
  - WebFetch
  - Glob
  - Grep
  - WebSearch
---

# Audio Skill v0.1 (MVP)

Ты — **аудио-продюсер** экосистемы «Лаборатории желаний». Превращаешь скрипты
(медитации, аффирмации, аудиоуроки) в mp3-файлы на сайте **lab_site** с
HTML5-плеером, анонсами в соцсетях и email.

Связка: **PDF/text скрипт → LLM-адаптер → YAML → Yandex SpeechKit → ffmpeg mix
→ R2 → Astro-страница → deploy → TG/VK/email**.

**Не дублируешь:** publisher_skill (деплой + анонсы переиспользуем), WL
(книги), Coach (тексты диалогов), SEO Advisor (мета-разметка страниц — Phase 2+).

## 🎯 РЕЖИМЫ РАБОТЫ

| Маршрут | Команда | Что делает |
|---------|---------|------------|
| `/adapt-pdf <path>` | импорт | pdfplumber → черновой YAML, прогон через LLM-адаптер → `data/library/<slug>.yaml` |
| `/adapt-text <slug>` | импорт из чата | текст из чата → LLM-адаптер → YAML |
| `/preview-audio <slug>` | превью | YAML → SSML → TTS-черновик (mp3) + preview HTML + спек-анализ ffmpeg |
| `/publish-audio <slug>` | полный цикл | TTS → mix → R2 → render → deploy → announce → notify |
| `/publish-audio --dry-run <slug>` | превью | всё, кроме R2/deploy/VK/TG; mp3 + HTML-превью + план |
| `/publish-audio --only=tts <slug>` | только озвучка | TTS + mix → tmp/, без заливки и анонса |
| `/publish-audio --only=render <slug>` | только страница | render (если mp3 уже в R2) |
| `/status-audio <slug>` | отчёт | `state/<slug>.json` — что озвучено, залито, задеплоено, анонсировано |
| `/rollback-audio <slug>` | откат | удалить mp3 из R2 + вернуть предыдущую версию страницы (через publisher_skill) |
| `/list` | каталог | все YAML в `data/library/` со статусами |
| `/watch-audio` | фоновый режим | polling `data/library/*.yaml` (новые/изменённые) |

**NB (v0.1):** реализованы `/adapt-pdf`, `/adapt-text`, `/preview-audio`, `/publish-audio`
(полный + dry-run + --only), `/status-audio`, `/list`. НЕ реализованы: `/rollback-audio`,
`/watch-audio` (Phase 2+).

## 🧠 АЛГОРИТМ `/publish-audio <slug>`

### Шаг 0. Идемпотентность
- Прочитай `state/<slug>.json` (если есть). Уже сделанное не повторяй.
- Если `status == "published"` и не было `--force` → «уже опубликовано <дата>».

### Шаг 1. Загрузить YAML
- `data/library/<slug>.yaml` — финальный шаблон (результат LLM-адаптера).
- Внутри: `title, slug, voice, background, music_intro, music_outro,
  script, pauses, duration_target`.
- Если YAML нет → СТОП, ссылка на `/adapt-pdf` или `/adapt-text`.

### Шаг 2. Сгенерировать SSML
- `scripts/ssml_build.py` → `tmp/<slug>.ssml` (текст + паузы `<break time="..."/>`,
  замедление `<prosody rate="0.9">`, шёпот `<prosody volume="x-soft">`).

### Шаг 3. TTS (Yandex SpeechKit)
- `scripts/tts_yandex.py` → POST на `https://tts.api.cloud.yandex.net/speech/v1/tts:synthesize`
  с `lang=ru-RU`, `voice=<voice>`, `format=mp3`, SSML в теле.
- Сохранить в `tmp/<slug>-voice.mp3`.
- Записать `state[slug].voice_path`, `state[slug].voice_duration_sec`.

### Шаг 4. Подмешать фоновую музыку
- `scripts/mix_audio.py` через ffmpeg:
  - `tmp/<slug>-voice.mp3` + `data/backgrounds/<background>.mp3` → `tmp/<slug>-full.mp3`
  - `music_intro` сек fade-in фона, voice начинается на 2 сек позже
  - `music_outro` сек fade-out
  - нормализация `-14 LUFS`
- Записать `state[slug].mixed_path`, `state[slug].final_duration_sec`.

### Шаг 5. Залить в R2
- `scripts/upload_r2.py` через S3-совместимый API → `https://audio.pulab.online/<slug>.mp3`
- Записать `state[slug].r2_url`, `state[slug].uploaded_at`.

### Шаг 6. Render (подскил `sub-skills/render.md`)
- Скопировать mp3 + cover в `lab_site/public/audio/<slug>/` (локальный fallback) **ИЛИ**
  в R2 (если доступ из РФ подтверждён).
- Сгенерировать `lab_site/src/data/audio/<slug>.json` для `import`.
- Сгенерировать `lab_site/src/pages/audio/<slug>.astro` по шаблону
  `templates/audio-page-astro.astro` (HTML5-плеер + транскрипт + кнопка «скачать»).
- Записать `state[slug].page_path`.

### Шаг 7. Deploy (через publisher_skill)
- Вызвать `python publisher_skill/scripts/deploy_pages.py` (импорт модуля).
- GET новой страницы → проверить HTTP 200.
- В `state[slug].deployed_at`, `state[slug].live_url`.

### Шаг 8. Announce (через publisher_skill)
- Импортировать `publisher_skill.scripts.post_telegram`,
  `post_vk`, `send_email` с шаблонами `templates/announcement-tg-audio.md`,
  `templates/announcement-vk-audio.md`.
- TG-канал + VK-группа `pulabru` + email-рассылка.
- Пометить `state[slug].channels_posted.{tg,vk,email}`.

### Шаг 9. Notify admin
- `publisher_skill/scripts/notify_admin.py` → @kfigh в TG: «Аудио «<title>» опубликовано ✅».

### Шаг 10. Финал
- `state[slug].status = "published"`, `state[slug].published_at = now()`.

## 📂 ГДЕ ЧТО

```
audio_skill/
├── SKILL.md              # оркестратор (этот файл)
├── README.md             # человеческое описание
├── CHANGELOG.md
├── commands/             # готовые рецепты
│   ├── publish-audio.md
│   └── adapt-pdf.md
├── sub-skills/           # детали каждой стадии (Phase 2+)
├── prompts/              # промпты LLM-адаптера
│   └── affirm-adapt.md
├── templates/            # шаблоны
│   ├── audio-page-astro.astro    # страница с HTML5-плеером
│   ├── announcement-tg-audio.md
│   └── announcement-vk-audio.md
├── scripts/              # Python-исполнители
│   ├── pdf_parse.py              # Stage 0: PDF → черновой YAML
│   ├── llm_adapt.py              # Stage 0.5: YAML → LLM-адаптированный YAML
│   ├── ssml_build.py             # Stage 1: YAML → SSML
│   ├── tts_yandex.py             # Stage 2: SSML → mp3 (Yandex SpeechKit)
│   ├── mix_audio.py              # Stage 3: ffmpeg mix voice + background
│   ├── upload_r2.py              # Stage 4: mp3 → R2
│   ├── render_audio.py           # Stage 5: mp3 + meta → Astro-страница
│   ├── deploy_audio.py           # Stage 6: build + wrangler (через publisher_skill)
│   ├── announce_audio.py         # Stage 7: TG + VK + email (через publisher_skill)
│   ├── state.py                  # идемпотентность
│   └── slugify.py                # общий с publisher_skill/seo-advisor-skill
├── data/
│   ├── voices.yaml               # каталог голосов Yandex
│   ├── backgrounds.yaml          # каталог фоновых треков
│   └── library/                  # YAML-скрипты (по slug)
├── examples/             # 1 готовый опубликованный трек
├── state/                # {slug}.json — идемпотентность
└── tmp/                  # mp3-черновики, превью, логи
```

## 🔗 СВЯЗИ

- **publisher_skill** — переиспользуем `state.py`, `slugify.py`, `deploy_pages.py`,
  `post_telegram.py`, `post_vk.py`, `send_email.py`, `notify_admin.py`.
  Импорт, не копирование.
- **WishLibrarian** — не связан напрямую. WL = книги, Audio = скрипты.
- **lab_site** — целевой сайт, `lab_site/src/pages/audio/<slug>.astro` +
  `lab_site/src/data/audio/<slug>.json` + `lab_site/public/audio/<slug>/<slug>.mp3`.
- **Yandex Cloud** — SpeechKit (TTS).
- **Cloudflare R2** — хранилище mp3 (если доступен из РФ; иначе fallback на VPS).
- **ffmpeg** — микширование voice + background, нормализация.

## ⚙️ КОНФИГ (.env)

```bash
# === Yandex Cloud / SpeechKit ===
YC_FOLDER_ID=...                  # ID каталога в Yandex Cloud
YC_API_KEY=...                    # сервисный аккаунт с ролью ai.speechkit.user
YC_TTS_VOICE=alena                # дефолтный голос (см. data/voices.yaml)
YC_TTS_FORMAT=mp3
YC_TTS_SAMPLE_RATE=48000

# === Cloudflare R2 (mp3 storage) ===
CF_ACCOUNT_ID=...
CF_R2_ACCESS_KEY_ID=...
CF_R2_SECRET_ACCESS_KEY=...
R2_BUCKET=pulab-audio
R2_PUBLIC_URL=https://audio.pulab.online
R2_ENDPOINT=https://<account_id>.r2.cloudflarestorage.com

# === Локальный fallback (если R2 недоступен из РФ) ===
AUDIO_LOCAL_PUBLIC=C:/Users/kfigh/lab_site/public/audio

# === lab_site ===
LAB_SITE_ROOT=C:/Users/kfigh/lab_site
WL_OUTPUT_ROOT=C:/Users/kfigh/wish_librarian/output/library  # не используется в v0.1

# === publisher_skill (переиспользование) ===
PUBLISHER_SKILL_ROOT=C:/Users/kfigh/publisher_skill

# === LLM-адаптер (PDF → YAML) ===
LLM_PROVIDER=claude               # claude | yandex | gigachat
LLM_API_KEY=...                   # берётся из wish_librarian/agent/ai/factory.py

# === Логи ===
LOG_LEVEL=INFO
```

## 🚦 СТАТУСЫ В state/<slug>.json

```json
{
  "slug": "zolotye-pravila",
  "title": "Золотые правила исполнения желаний",
  "status": "draft | adapted | tts_ready | mixed | uploaded | published | failed",
  "created_at": "2026-06-11T19:00:00Z",
  "adapted_at": "2026-06-11T19:30:00Z",
  "ssml_path": "tmp/zolotye-pravila.ssml",
  "voice_path": "tmp/zolotye-pravila-voice.mp3",
  "mixed_path": "tmp/zolotye-pravila-full.mp3",
  "voice_duration_sec": 168.4,
  "final_duration_sec": 180.0,
  "r2_url": "https://audio.pulab.online/zolotye-pravila.mp3",
  "uploaded_at": "2026-06-11T20:00:00Z",
  "page_path": "lab_site/src/pages/audio/zolotye-pravila.astro",
  "deployed_at": "2026-06-11T20:05:00Z",
  "live_url": "https://app.pulab.online/audio/zolotye-pravila/",
  "channels_posted": {
    "tg": null,
    "vk": null,
    "email": null
  },
  "channels_failed": [],
  "error": null
}
```

## 🚧 ИЗВЕСТНЫЕ ОГРАНИЧЕНИЯ (MVP v0.1)

- Phase 1 (эта сессия): `/adapt-pdf`, `/adapt-text`, `/preview-audio` (до TTS),
  `/list`, `/status-audio`. Реального TTS ещё нет.
- Phase 2: TTS, mix, R2, deploy, announce, watcher, rollback.
- Нет CI/тестов (Phase 3+).
- LLM-адаптер использует ту же фабрику, что и WL (Claude/Yandex/Giga).

См. CHANGELOG.md.
