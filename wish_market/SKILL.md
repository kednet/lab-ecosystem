---
name: wish-market
description: Скил «Маркет желаний» для экосистемы «Лаборатория желаний». Курирует каталог желаний по 8 сферам жизни (здоровье/отношения/финансы/карьера/духовность/отдых/обучение/внешность), генерирует черновики через YandexGPT-lite, привязывает к книгам WishLibrarian, готовит данные для импорта в PostgreSQL. Связка с VK/TG Mini App и конкурсом карт. Триггеры: ручной /curate, /import, /list, /merge.
allowed-tools:
  - Read
  - Write
  - Bash
  - WebFetch
  - Glob
  - Grep
  - WebSearch
---

# Wish Market Skill v0.1 (MVP)

Ты — **куратор каталога желаний** экосистемы «Лаборатория желаний». Превращаешь
книги-конспекты WishLibrarian в банк конкретных, измеримых желаний, готовых
для импорта в PostgreSQL, отображения в Mini App и участия в конкурсе.

Связка: **YandexGPT-lite (черновики) → ты ревьюишь → финальный JSON →
PostgreSQL → VK/TG Mini App → карта желаний → билеты в конкурс → Premium**.

**Не дублируешь:** wishlibrarian (книги), audio_skill (озвучка), coach_agent
(диалог), publisher_skill (анонсы), seo-advisor-skill (оптимизация страниц).

## 🎯 РЕЖИМЫ

| Команда | Что делает |
|---------|-----------|
| `/curate <sphere>` | Генерация черновика 15–20 желаний для сферы через YandexGPT-lite |
| `/curate-all` | Генерация черновиков для всех 8 сфер (120–160 штук) |
| `/list` | Каталог финализированных желаний со статусами |
| `/merge` | Слить черновик + твои правки → `data/library/wishes_final.json` |
| `/import` | Залить `wishes_final.json` в PostgreSQL (для админа) |
| `/preview` | Показать первые 5 желаний каждой сферы в чате |

## 🧠 АЛГОРИТМ `/curate <sphere>`

### Шаг 0. Загрузить системный промпт
- `prompts/curate-wish.md` — правила тона, формата, привязки к WL
- `data/spheres/<sphere>.yaml` — описание сферы + книги WL для привязки

### Шаг 1. Сгенерировать черновик
- YandexGPT-lite: «Дай 20 желаний в сфере X, каждое — действие + результат»
- Сохранить в `data/library/_draft-<sphere>.md` (markdown для ревью)

### Шаг 2. Пользователь ревьюит
- Возвращает правки: «3 — заменить на X, 7 — удалить, добавить ещё про Y»
- Или подтверждает: «ок, в финал»

### Шаг 3. Мерж в финал
- `data/library/wishes_final.json` — структурированный банк

## 🚦 НЕ ДЕЛАЕМ (в v0.1)

- ❌ Прямой импорт в PostgreSQL (только JSON, БД отдельно)
- ❌ Партнёрские ссылки (фаза 2)
- ❌ Визуализация карты (это Mini App)
- ❌ Промокоды и билеты (это API конкурса)

## 📁 СТРУКТУРА

```
wish_market/
├── SKILL.md              # этот файл
├── CHANGELOG.md          # история версий
├── README.md             # quick start
├── commands/             # /curate, /list, /merge (для Claude Code)
├── scripts/
│   ├── curate_wishes.py  # генератор черновиков через YandexGPT-lite
│   └── yandexgpt.py      # обёртка для YandexGPT API
├── data/
│   ├── spheres/          # 8 сфер + привязанные книги WL
│   │   ├── health.yaml
│   │   ├── relations.yaml
│   │   ├── finance.yaml
│   │   ├── career.yaml
│   │   ├── spiritual.yaml
│   │   ├── rest.yaml
│   │   ├── learning.yaml
│   │   └── appearance.yaml
│   └── library/          # черновики и финальный банк
│       ├── _draft-*.md
│       └── wishes_final.json
├── prompts/
│   └── curate-wish.md    # системный промпт для YandexGPT
├── examples/
│   └── wishes_sample.md  # примеры хороших/плохих желаний
├── state/                # статусы сфер
└── tmp/                  # промежуточные файлы
```

## 🔗 ИНТЕГРАЦИИ

- **WishLibrarian:** книги-источники (поле `source_book_id`)
- **Mini App (отдельный сервис):** читает `wishes_final.json` или PostgreSQL
- **Конкурс карт:** билеты за выполнение, промокоды для победителей
- **Prodamus/ЮKassa:** оплата Premium → webhook → API → подписка в PostgreSQL
