---
name: profile-system
description: Profile-override матрица для image_skill — приоритет CLI > profile > format
metadata:
  type: sub-skill
  phase: 1
---

# Profile System

## Что такое профиль

Профиль в image_skill — это YAML-файл в `data/profiles/<name>.yaml` с настройками бренда:
- `defaults.{format, style, mood, seed}` — параметры по умолчанию
- `branding.palette` — 5 цветов (primary, primary_deep, primary_soft, bg, text)
- `branding.accent_color` — основной HEX для LLM-промпта
- `branding.watermark` — текст для watermark (Phase 2)
- `prompt_styles` — словарь "стиль → подсказка для LLM"
- `prompt_moods` — словарь "настроение → подсказка для LLM"
- `hashtags_base` — список хештегов (для Phase 3 автопубликации)
- `negative_prompts` — список того, что НЕ генерировать
- `output.{state_subdir, filename_template}` — пути сохранения

## Что такое формат

Формат — это запись в `data/formats.yaml` с:
- `label` — человеческое имя
- `aspect` — соотношение сторон ("1:1", "9:16", "2:3", "3:4", "2:1")
- `width_ratio`, `height_ratio` — целые 1..8 для YandexART
- `target_size` — целевой размер в пикселях (например [1080, 1080])
- `safe_zones` — отступы для текста/CTA (Phase 2)
- `use_case` — где используется

## Override-матрица

Приоритет (от высшего к низшему):

1. **CLI-флаг** (`--format`, `--style`, `--mood`, `--seed`, `--profile`)
2. **`profile.defaults.{format, style, mood, seed}`**
3. **`format.aspect` / `format.width_ratio` / `format.height_ratio`** (из format registry)
4. **`branding.palette`** (для LLM-промпта, не переопределяется)
5. **`branding.watermark`** (Phase 2, не переопределяется в Phase 1)

### Спец-случаи

- **`format` обязателен** — иначе `ValueError` со списком доступных.
- **Если `format` указан в CLI, но отсутствует в format registry** — `ValueError` с подсказкой.
- **Если `style` или `mood` не найдены в `prompt_styles` / `prompt_moods`** профиля — используется сам `style`/`mood` как подсказка для LLM (fallback).
- **`seed`**: если не указан в CLI и в profile — генерируется `random.randint(0, 2^32-1)`.

## Пример: override в действии

```bash
# Использует все defaults: vk_post, watercolor, soft
python scripts/image.py generate vk_post "промо новой книги" --profile=lab

# Override style/mood из CLI (--style=flat побеждает watercolor из lab.defaults.style)
python scripts/image.py generate vk_post "промо новой книги" --style=flat --mood=bold --profile=lab

# Другой профиль (wl.yaml)
python scripts/image.py generate pinterest "книга Андреевой" --profile=wl
# → palette будет blue (3B82F6), style defaults=flat, mood=calm

# Разные форматы, один профиль
python scripts/image.py generate og "превью статьи" --profile=lab
# → aspect=2:1, width_ratio=6, height_ratio=3
```

## Реализация

- **`scripts/_image_common.py`**: `load_formats()`, `get_format(name)`, `list_profile_names()`
- **`scripts/cmd_profile.py`**: `load_profile(name) → dict` (копия из video_skill)
- **`scripts/cmd_generate.py:resolve_params()`**: применяет override-матрицу

## Связано с

- [[data-formats-yaml]] — registry форматов
- [[data-profiles-lab-yaml]] — пример полного профиля
- [[sub-skill-generate-mode]] — где применяется override
- [[image-skill-v1-phase1-built]] — главный memory
