---
name: generate-mode
description: "Режим C: ручная генерация одной картинки через YandexART"
metadata:
  type: sub-skill
  phase: 1
---

# Generate Mode (C-режим)

## Что это

Sub-режим image_skill Phase 1: пользователь даёт текстовый запрос, профиль и формат —
получает готовый PNG-файл (драфт, 512×512 max в Phase 1).

Это базовый режим: один запрос = одна картинка. Идемпотентность обеспечивается через
state.

## Алгоритм

1. **Парсинг CLI** (`scripts/image.py:build_parser` → `cmd_generate.run`).
2. **Load profile** (`cmd_profile.load_profile(args.profile)`) — YAML из `data/profiles/<name>.yaml`.
3. **resolve_params** (override-матрица — см. `sub-skill-profile-system`).
4. **resolve_format** (`_image_common.get_format(args.format)`) — width/height_ratio.
5. **build_prompt** — LLM-стилизация (или fallback) из `prompts/image-prompt.md`.
6. **yandex_art.generate** — POST на YandexART API, base64 PNG.
7. **save_image** — `tmp/images/<profile>/<slug>-<format>.png`.
8. **validate_image_file** — PNG signature, size ≤ 512 КБ.
9. **state.update** — status="saved", image_path, image_size_kb, seed, prompt_text.

## Идемпотентность

Перед генерацией проверяется `state["status"] == "saved"`. Если да и нет `--force` —
печатает "⏭ Изображение уже есть" и выходит с rc=0.

State живёт в `state/<profile>/<slug>.json`. Slug = `slugify(source_text, max_length=60)`.

## Что внутри state (после успешной генерации)

```json
{
  "slug": "5-oshibok-karty-zhelaniy",
  "profile": "lab",
  "status": "saved",
  "title": "5 ошибок карты желаний",
  "format": "vk_post",
  "style": "watercolor",
  "mood": "soft",
  "aspect": "1:1",
  "width_ratio": 8,
  "height_ratio": 8,
  "seed": 271828,
  "prompt_text": "...",
  "image_path": "tmp/images/lab/5-oshibok-karty-zhelaniy-vk_post.png",
  "image_size_kb": 73.4,
  "image_mime": "image/png",
  "created_at": "2026-06-17T09:00:00Z",
  "prompt_at": "2026-06-17T09:00:00Z",
  "generated_at": "2026-06-17T09:00:01Z"
}
```

## Примеры вызова

```bash
# Полный прогон
python scripts/image.py generate vk_post "5 ошибок карты желаний" --profile=lab

# Dry-run (показать что будет без API-вызова)
python scripts/image.py generate pinterest "закат над книгой" --profile=lab --dry-run

# Override style/mood
python scripts/image.py generate og "превью статьи" --style=flat --mood=bold --profile=lab

# Force перегенерация (новый seed)
python scripts/image.py generate vk_post "..." --force
```

## Ограничения Phase 1

- ❌ Максимальный размер 512×512 (нужен upscale — Phase 2)
- ❌ Нет text overlay и watermark (Phase 2)
- ❌ Нет интеграции с publisher_skill (Phase 3)
- ❌ LLM-стилизация промпта может сбоить (есть fallback)
- ❌ Один ключ YandexAPI на YandexGPT + YandexART + будущий SpeechKit — квоты общие

## Связано с

- [[profile-system]] — override-матрица
- [[yandex-art-api]] — API контракт
- [[image-skill-v1-phase1-built]] — главный memory
