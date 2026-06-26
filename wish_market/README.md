# Wish Market Skill

Куратор каталога желаний для экосистемы «Лаборатория желаний».

## Что делает

- Генерирует черновики желаний по 8 сферам жизни через YandexGPT-lite
- Привязывает каждое желание к книге из WishLibrarian (где возможно)
- Готовит финальный JSON для импорта в PostgreSQL
- Подаёт данные в VK/TG Mini App → карта желаний → конкурс

## Структура

- `SKILL.md` — описание скилла
- `commands/` — ручные триггеры (`/curate`, `/list`, `/merge`)
- `scripts/` — Python-скрипты (генератор, обёртка YandexGPT)
- `data/spheres/` — описания 8 сфер + привязанные книги WL
- `data/library/` — черновики (markdown) и финальный банк (JSON)
- `prompts/` — системные промпты для YandexGPT
- `examples/` — примеры хороших/плохих желаний
- `state/` — статусы сфер
- `tmp/` — промежуточные файлы

## Quick start

```bash
# Установить зависимости
pip install pyyaml requests python-dotenv

# Скопировать .env.example в .env и заполнить ключ YandexGPT
cp .env.example .env

# Сгенерировать черновик для одной сферы
python scripts/curate_wishes.py --sphere=health --out=data/library/_draft-health.md

# Сгенерировать все 8 сфер
python scripts/curate_wishes.py --all --out=data/library/

# Показать каталог
ls data/library/
```

## Команды (для Claude Code)

- `/curate <sphere>` — черновик 15–20 желаний для сферы
- `/curate-all` — все 8 сфер (120–160 штук)
- `/list` — каталог с статусами
- `/merge` — слить черновик + правки в финал
- `/import` — залить в PostgreSQL (для админа)
- `/preview` — показать первые 5 каждой сферы

## Связки

- **WishLibrarian** — книги-источники (`source_book_id`)
- **Mini App** (отдельный сервис `wish_market_api/`) — читает JSON/PostgreSQL
- **Конкурс** — билеты за выполнение, промокоды для победителей
- **Prodamus/ЮKassa** — оплата Premium

## План запуска

Полный план в `C:\Users\kfigh\plans\wish-market-launch-2026-08.md`.
Цель: MVP (ВК Mini App + каталог + карта) к 1 августа 2026.
