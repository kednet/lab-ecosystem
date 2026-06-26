# /image generate

Сгенерировать картинку через YandexART.

## Команда

```bash
python scripts/image.py generate <format> "<source_text>" [--profile=lab] [--style=watercolor] [--mood=soft] [--seed=271828] [--force] [--dry-run]
```

## Позиционные аргументы

- `<format>` — формат: `vk_post` | `vk_story` | `pinterest` | `wb` | `og`
- `<source_text>` — текст запроса (RU/EN), будет стилизован через LLM в EN-промпт

## Флаги

- `--profile` — профиль (по умолчанию из `PROFILE_DEFAULT` env, иначе `lab`)
- `--style` — стиль (`watercolor` | `photo` | `flat` | `3d` | `anime`)
- `--mood` — настроение (`soft` | `bold` | `warm` | `calm` | `mystic`)
- `--seed` — целое 0..2^32 для воспроизводимости (default: random)
- `--force` — перезаписать существующий state
- `--dry-run` — показать что будет, но НЕ вызывать API и НЕ создавать файлы

## Алгоритм

1. Парсинг CLI → format, source_text, опционально style/mood/seed
2. Load profile (YAML из `data/profiles/<name>.yaml`)
3. resolve_params (override-матрица)
4. resolve_format (width_ratio, height_ratio из `data/formats.yaml`)
5. build_prompt (LLM-стилизация через `prompts/image-prompt.md` или fallback)
6. yandex_art.generate → POST на YandexART API → base64 PNG
7. save_image → `tmp/images/<profile>/<slug>-<format>.png`
8. validate_image_file → PNG signature, size ≤ 512 КБ
9. state.update → status="saved", image_path, image_size_kb, seed, prompt_text

## Идемпотентность

Перед генерацией проверяется `state["status"] == "saved"`. Если да и нет `--force` —
печатает "⏭ Изображение уже есть" и выходит с rc=0.

Для перегенерации используй `--force` (новый seed).

## Примеры

```bash
# Полный прогон
python scripts/image.py generate vk_post "5 ошибок карты желаний" --profile=lab

# Override style/mood
python scripts/image.py generate pinterest "Рассвет" --mood=warm --profile=lab

# Dry-run (показать промпт без API)
python scripts/image.py generate vk_post "проверка" --dry-run --profile=lab

# Force перегенерация
python scripts/image.py generate vk_post "..." --force

# OG для статьи
python scripts/image.py generate og "Превью статьи про желания" --style=flat --mood=bold --profile=lab

# WishLibrarian профиль (blue palette)
python scripts/image.py generate vk_post "Книга желаний" --profile=wl
```

## Связано с

- [[SKILL]] — главный orchestrator
- [[sub-skill-generate-mode]] — детали C-режима
- [[sub-skill-profile-system]] — override-матрица
- [[sub-skill-yandex-art-api]] — API контракт
- [[data-formats-yaml]] — registry форматов
