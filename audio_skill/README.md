# Audio Skill

Аудио-продюсер «Лаборатории желаний». Превращает скрипты (PDF, текст из чата,
YAML) в mp3-файлы с фоновой музыкой, HTML5-плеером на lab_site и анонсами
в TG + VK + email.

## Связка

```
PDF/text скрипт
   ↓ pdfplumber (scripts/pdf_parse.py)
черновой YAML
   ↓ LLM-адаптер (scripts/llm_adapt.py)
   промпт: prompts/affirm-adapt.md
   LLM: Claude / YandexGPT / GigaChat
финальный YAML в data/library/<slug>.yaml
   ↓ ssml_build.py
SSML
   ↓ tts_yandex.py
голосовая дорожка mp3
   ↓ mix_audio.py (ffmpeg)
голос + фон → финальный mp3
   ↓ upload_r2.py
https://audio.pulab.online/<slug>.mp3
   ↓ render_audio.py
Astro-страница lab_site/src/pages/audio/<slug>.astro
   ↓ deploy_audio.py → publisher_skill/scripts/deploy_pages.py
https://app.pulab.online/audio/<slug>/
   ↓ announce_audio.py → publisher_skill/scripts/post_*.py
TG + VK (pulabru) + email
   ↓ notify_admin.py
@kfigh в личку TG: «готово»
```

## Структура v0.1 (Phase 1)

```
audio_skill/
├── SKILL.md                       # оркестратор (7 команд)
├── README.md                      # этот файл
├── CHANGELOG.md
├── commands/                      # готовые рецепты
│   ├── publish-audio.md
│   └── adapt-pdf.md
├── prompts/
│   └── affirm-adapt.md            # промпт LLM-адаптера
├── templates/                     # шаблоны
│   ├── audio-page-astro.astro     # страница с HTML5-плеером
│   ├── announcement-tg-audio.md
│   └── announcement-vk-audio.md
├── scripts/
│   ├── pdf_parse.py               # Stage 0: PDF → черновой YAML
│   ├── llm_adapt.py               # Stage 0.5: LLM-адаптер
│   ├── ssml_build.py              # Stage 1: YAML → SSML
│   ├── tts_yandex.py              # Stage 2: SSML → mp3 (stub в v0.1)
│   ├── mix_audio.py               # Stage 3: ffmpeg mix (stub в v0.1)
│   ├── upload_r2.py               # Stage 4: mp3 → R2 (stub в v0.1)
│   ├── render_audio.py            # Stage 5: mp3 + meta → Astro (stub в v0.1)
│   ├── state.py                   # идемпотентность (импорт из publisher_skill)
│   └── slugify.py                 # общий slugify
├── data/
│   ├── voices.yaml                # каталог голосов Yandex SpeechKit
│   ├── backgrounds.yaml           # каталог фоновых треков
│   └── library/                   # YAML-скрипты (по slug)
├── examples/
│   └── zolotye-pravila.yaml       # эталон: твой скрипт №1 (адаптированный)
├── state/                         # {slug}.json — идемпотентность
├── tmp/                           # mp3-черновики, превью, логи
└── .env.example
```

## Запуск (Phase 1 — без реального TTS)

### Адаптировать PDF

```bash
# Один скрипт из PDF:
python scripts/pdf_parse.py "C:/Users/kfigh/Downloads/Скрипты для аудио.pdf" \
    --script-id=1 \
    --out=data/library/_draft-zolotye-pravila.yaml

# Прогнать через LLM-адаптер:
python scripts/llm_adapt.py _draft-zolotye-pravila.yaml \
    --provider=claude \
    --tone=warm_mentor \
    --remove-concrete-examples \
    --out=data/library/zolotye-pravila.yaml
```

### Превратить текст из чата в YAML

```bash
# В чате: «@adapt-text zolotye-pravila» + вставить текст
# Скилл создаст data/library/zolotye-pravila.yaml
```

### Каталог и статусы

```bash
python scripts/state.py list                    # все slug и статусы
python scripts/state.py show zolotye-pravila     # детально
```

## Зависимости

- **Python 3.11+** + `pip install pdfplumber pyyaml pydantic`
- **ffmpeg** (для Phase 2) — https://ffmpeg.org/download.html
- **publisher_skill** (`C:/Users/kfigh/publisher_skill/`) — переиспользование
  state, slugify, deploy, announce
- **wish_librarian** (`C:/Users/kfigh/wish_librarian/`) — переиспользование
  LLM-фабрики из `agent/ai/factory.py`
- **Yandex Cloud** (Phase 2) — SpeechKit API key + folder ID
- **Cloudflare R2** (Phase 2) — bucket + access keys

## Конфиг

Скопируй `.env.example` в `.env` и заполни:

```bash
cp .env.example .env
# Заполни YC_FOLDER_ID, YC_API_KEY, R2_*, LLM_API_KEY
```

В Phase 1 достаточно `LLM_API_KEY` (для адаптера) и `PUBLISHER_SKILL_ROOT`.

## Changelog

См. [CHANGELOG.md](./CHANGELOG.md).

## Известные ограничения (v0.1, Phase 1)

- TTS, mix, R2, deploy, announce — **stubs** в Phase 1
- LLM-адаптер работает, но не покрывает edge-кейсы (длинные скрипты, шёпот-середины)
- Нет CI/тестов
- Нет watcher-а (Phase 2+)
