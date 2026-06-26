# Content Ideas Skill

Генерация идей постов для **«Лаборатории желаний»** (VK, блог на сайте, опц. Telegram) с приоритезацией на основе данных и интеграцией в стек `pulabru` (WishLibrarian, WishCoach, SEO Advisor, Publisher, Expert & Reviews Hub).

## Что это

Скил превращает разрозненные источники (книги WL, модули Coach, конкуренты VK, боли ЦА, сезонный календарь) в **готовые к производству карточки идей**, которые можно отдавать в Publisher без переработки.

## Главная ценность

- **Темы подкреплены данными** (а не «придумал LLM»)
- **Язык ЦА** (из реальных комментов конкурентов)
- **Дедуп по истории** (не повторяемся)
- **Микс рубрик** (разнообразие)
- **Готовый экспорт** в Publisher

## Быстрый старт (MVP v0.1)

```bash
# 1. Заполнить профили
# profiles/lab-zhelanii-ca.md
# profiles/rubrics.md

# 2. Запустить генератор
python scripts/generate_ideas.py \
  --theme "навязанные желания" \
  --count 10 \
  --target vk

# 3. Собрать контент-план
python scripts/calendar_fill.py --month 2026-07 --posts-per-week 4
```

## Документация

- [`SKILL.md`](SKILL.md) — главный оркестратор (полная спецификация)
- [`docs/architecture.md`](docs/architecture.md) — архитектурная схема
- [`docs/sources-priority.md`](docs/sources-priority.md) — приоритеты источников
- [`docs/integration.md`](docs/integration.md) — интеграции с другими скилами
- [`docs/data-schema.md`](docs/data-schema.md) — схемы JSON

## Статус

**v0.1 (спецификация)** — структура создана, ключевые документы и скрипты — заглушки.

Roadmap: см. [`SKILL.md` → MVP v0.1](SKILL.md#mvp-v01--что-в-первой-версии)
