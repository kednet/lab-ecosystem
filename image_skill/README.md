# Image Skill

Универсальный скил для генерации картинок для соцсетей (ВК, Pinterest, WB, OG)
через YandexART (Yandex Cloud Foundation Models).

**Версия:** 0.1.0 (Phase 1, MVP)
**Дата:** 2026-06-17
**Целевая папка:** `C:\Users\kfigh\image_skill\`

## Что это

Генерирует PNG-драфты для 5 форматов × 5 профилей через YandexART API.
Использует тот же `YANDEX_API_KEY`, что и YandexGPT (единый ключ Yandex Cloud).

Поддерживает:
- 5 форматов: ВК-пост (1:1), ВК-история (9:16), Pinterest (2:3), WB (3:4), OG (2:1)
- 5 профилей с brand-aware палитрой
- LLM-стилизацию промпта (EN-перевод + бренд)
- State-идемпотентность

## Быстрый старт

```bash
cd C:\Users\kfigh\image_skill

# Скопируй ключи из wish_librarian/.env (если нужно)
# cp ../wish_librarian/.env .env

# Сгенерировать ВК-пост
python scripts/image.py generate vk_post "5 ошибок карты желаний" --profile=lab

# Pinterest с override
python scripts/image.py generate pinterest "Рассвет над книгой" --mood=warm --profile=lab

# OG-image для статьи
python scripts/image.py generate og "Превью статьи" --style=flat --mood=bold --profile=lab

# Dry-run
python scripts/image.py generate vk_post "проверка" --dry-run --profile=lab
```

## Структура

```
image_skill/
├── SKILL.md              # Главный orchestrator doc
├── README.md             # Этот файл
├── CHANGELOG.md          # История версий
├── .env.example          # Шаблон ENV
│
├── commands/             # 4 команды для пользователя
├── sub-skills/           # 6 sub-skills (4 stubs + 2 рабочих)
├── prompts/              # 4 промпта (image-prompt + profile-context + negative + announce)
├── templates/            # 6 шаблонов (5 форматов + upscale stub)
│
├── scripts/              # 12 Python-скриптов
│   ├── image.py          # Orchestrator
│   ├── cmd_generate.py   # C-режим
│   ├── cmd_profile.py    # Управление профилями
│   ├── yandex_art.py     # YandexART API клиент
│   └── ...
│
├── data/
│   ├── formats.yaml      # 5 форматов × размеры
│   └── profiles/         # 5 профилей (lab полный, остальные заглушки)
│
├── examples/             # 5 примеров (3 полных lab + 2 заглушки)
├── references/           # yandex-art-api.md + image-format-sizes.md
│
├── state/                # state/<profile>/<slug>.json (runtime)
├── tmp/                  # tmp/images/<profile>/<slug>-<format>.png (runtime)
└── logs/                 # логи (runtime)
```

## Известные ограничения Phase 1

- Максимальный размер PNG: 512×512. Upscale до 1080×1080+ — Phase 2.
- Нет text overlay и watermark — Phase 2.
- Нет интеграции с publisher_skill — Phase 3.
- Нет автопубликации в соцсети — Phase 3.

## Связано с

- [Video Creator Skill](../video_skill/) — образец state+profiles
- [Publisher Skill](../publisher_skill/) — целевой интеграционный партнёр (Phase 3)
- [Audio Skill](../audio_skill/) — Yandex SpeechKit, общий ключ YandexAPI

## Автор

kfigh, 2026-06-17
