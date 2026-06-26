---
name: image-skill
description: "Универсальный скил генерации картинок для соцсетей (VK/Pinterest/WB/OG) через YandexART"
version: 0.1.0
phase: 1
target: Phase 1 (генерация PNG 512×512 max) — готово
metadata:
  type: skill
  status: mvp
  date: 2026-06-17
  author: kfigh
---

# Image Skill

Универсальный скил для генерации картинок через YandexART (Yandex Cloud Foundation Models).
Создаёт PNG-драфты для 5 форматов × 5 профилей (lab/wl/coach/experts/market).

## Что умеет (Phase 1)

- ✅ Генерация PNG через YandexART (тот же ключ что для YandexGPT)
- ✅ 5 форматов: vk_post (1:1), vk_story (9:16), pinterest (2:3), wb (3:4), og (2:1)
- ✅ 5 профилей с brand-aware палитрой (lab rose / wl blue / coach golden / experts violet / market emerald)
- ✅ Override-матрица: CLI > profile.defaults > format registry
- ✅ State-идемпотентность: `state/<profile>/<slug>.json` со status lifecycle
- ✅ LLM-стилизация промпта (EN-перевод + бренд) с fallback на ручную сборку
- ✅ Валидация PNG (signature, размер, aspect)
- ✅ Dry-run / --force / seed
- ✅ MITM bypass для корпоративного прокси

## Что НЕ умеет (Phase 2+)

- ❌ Upscale до 1080×1080+ (Phase 2, через Pillow)
- ❌ Text overlay + watermark burn (Phase 2, через Pillow)
- ❌ Интеграция с publisher_skill (Phase 3, через Cloudflare R2)
- ❌ Автопубликация в VK/TG/OK/Zen (Phase 3)
- ❌ Нейросетевой upscale Real-ESRGAN (Phase 4, опционально)

## Режимы

| Команда | Что делает | Статус |
|---------|-----------|--------|
| `image generate` | Сгенерировать PNG (C-режим) | ✅ Phase 1 |
| `image profile list\|show\|validate` | Управление профилями | ✅ Phase 1 |
| `image state show\|list\|reset` | State идемпотентность | ✅ Phase 1 |
| `image validate` | Проверить PNG + state | ✅ Phase 1 |
| `image auto` | STUB: upscale + text overlay | ⏳ Phase 2 |
| `image publish` | STUB: интеграция с publisher_skill | ⏳ Phase 3 |

## Алгоритм (C-режим, generate)

1. **Парсинг CLI** → format, source_text, profile, опционально style/mood/seed
2. **Load profile** (YAML из `data/profiles/<name>.yaml`)
3. **resolve_params** (override-матрица — см. `sub-skills/profile-system.md`)
4. **resolve_format** (width_ratio, height_ratio, target_size из `data/formats.yaml`)
5. **build_prompt** — LLM-стилизация (`prompts/image-prompt.md`) или fallback
6. **yandex_art.generate** → POST на YandexART API, base64 PNG
7. **save_image** → `tmp/images/<profile>/<slug>-<format>.png`
8. **validate_image_file** → PNG signature, size ≤ 512 КБ
9. **state.update** → status="saved", image_path, image_size_kb, seed, prompt_text

## Быстрый старт

```bash
# Сгенерировать ВК-пост 1:1 (lab профиль, watercolor, soft)
python scripts/image.py generate vk_post "5 ошибок карты желаний" --profile=lab

# Pinterest 2:3 с override mood
python scripts/image.py generate pinterest "Рассвет над книгой" --mood=warm --profile=lab

# OG-image 2:1 (превью для статьи)
python scripts/image.py generate og "Превью статьи про желания" --style=flat --mood=bold --profile=lab

# Dry-run (без API-вызова)
python scripts/image.py generate vk_post "проверка" --dry-run --profile=lab

# Force перегенерация (новый seed)
python scripts/image.py generate vk_post "..." --force
```

## Связи

- **[[video-skill-v1-phase1-built]]** — образец state+profiles идиом
- **[[publisher-skill-built]]** — целевой интеграционный партнёр (Phase 3)
- **[[audio-skill-built]]** — Yandex SpeechKit, ключевой принцип (один ключ YandexAPI на всё)
- **[[wishlibrarian-project]]** — источник YANDEX_API_KEY
- **[[corporate-mitm-proxy]]** — обход MITM
- **[[lab-brand-decisions-2026-06-16]]** — палитра/бренд для lab.yaml
- **[[lab-content-strategy-2026-06-16]]** — каналы ВК/TG/Pinterest (НЕ Instagram)

## Конфигурация

### ENV (image_skill/.env или wish_librarian/.env)

```bash
# Profile по умолчанию
PROFILE_DEFAULT=lab

# YandexART API (тот же ключ что для YandexGPT)
YANDEX_API_KEY=AQVNxxxx_xxxx
YANDEX_FOLDER_ID=b1xxxxxx
YANDEX_MODEL_ART=art://b1xxxxxx/yandex-art/latest  # опц., default строится из FOLDER_ID
```

### Профили

`data/profiles/<name>.yaml` — см. `data/profiles/lab.yaml` для полного примера.

Обязательные поля:
- `name`, `display_name`, `description`
- `defaults.{format, style, mood, seed}` (seed может быть null)
- `branding.palette.{primary, primary_deep, primary_soft, bg, text}`
- `branding.accent_color`
- `output.state_subdir` (= `name`)

### Форматы

`data/formats.yaml` — 5 форматов. width_ratio/height_ratio — целые 1..8.

## Статусы state lifecycle

```
draft → prompt_ready → generated → saved → (Phase 2: upscaled) → (Phase 3: published) | failed
```

- **draft** — создан, генерация не начиналась
- **prompt_ready** — промпт собран (после build_prompt)
- **generated** — YandexART вернул PNG
- **saved** — PNG записан в `tmp/images/<profile>/`, валиден
- **upscaled** (Phase 2) — после Pillow Lanczos upscale до target_size
- **published** (Phase 3) — после интеграции с publisher_skill
- **failed** — ошибка (YandexART 4xx/5xx, сеть, валидация)

## Известные ограничения Phase 1

- ❌ Максимальный размер PNG — 512×512 (или меньше по пропорции). Upscale в Phase 2.
- ❌ YandexART плохо рисует текст на картинках — `negative_prompts` это блокирует.
- ❌ YandexART лучше понимает EN-промпты — `build_prompt` всегда переводит через LLM.
- ❌ Один ключ YandexAPI на YandexGPT + YandexART + будущий SpeechKit — квоты общие.
- ❌ Нет автопубликации — Phase 3.

## Следующие шаги

**Phase 2 (~6-8 ч):** Pillow upscale + text overlay + watermark burn.
Требует: `pip install Pillow`, шрифт `assets/fonts/Inter-Bold.ttf`.

**Phase 3 (~4-6 ч):** интеграция с publisher_skill + автопубликация.
Требует: Cloudflare R2 + 4 токена (R2, VK, TG, OK).

## Связано с

- [[image-skill-v1-phase1-built]] — главный memory
- [[video-skill-v1-phase1-built]] — образец state+profiles
- [[sub-skill-generate-mode]] — детали C-режима
- [[sub-skill-profile-system]] — override-матрица
- [[sub-skill-yandex-art-api]] — документация YandexART API
- [[data-formats-yaml]] — registry форматов
