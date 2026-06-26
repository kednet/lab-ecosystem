# Архитектура content-ideas-skill

## Высокоуровневая схема

```
┌─────────────────────────────────────────────────────────────┐
│                    SOURCES (источники)                       │
├─────────────────────────────────────────────────────────────┤
│  ┌────────────┐  ┌────────────┐  ┌────────────┐  ┌────────┐ │
│  │ WL-книги   │  │ Coach      │  │ Конкуренты │  │Сезон.  │ │
│  │ (приоритет │  │ (приоритет │  │ + боли ЦА  │  │календ. │ │
│  │  🥇)      │  │  🥇)      │  │  🥈        │  │ 🥉     │ │
│  └─────┬──────┘  └─────┬──────┘  └─────┬──────┘  └───┬────┘ │
│        │               │               │             │      │
│        └───────────────┴───────────────┴─────────────┘      │
│                          │                                   │
└──────────────────────────┼──────────────────────────────────┘
                           ▼
┌─────────────────────────────────────────────────────────────┐
│                  FILTERS (фильтры)                          │
├─────────────────────────────────────────────────────────────┤
│  • profiles/lab-zhelanii-ca.md (ЦА)                         │
│  • profiles/tone-of-voice.md (тон)                          │
│  • profiles/rubrics.md (рубрикатор)                         │
│  • data/history.json (дедуп)                                │
│  • data/competitors/pulabru/ (своё не повторяем)            │
└──────────────────────────┬──────────────────────────────────┘
                           ▼
┌─────────────────────────────────────────────────────────────┐
│           GENERATE_IDEAS (оркестратор)                      │
│           scripts/generate_ideas.py                         │
│  → data/ideas-bank.json                                     │
│  → data/generated/<date>-<pack>.md                          │
└──────────────────────────┬──────────────────────────────────┘
                           ▼
┌─────────────────────────────────────────────────────────────┐
│                  OUTPUT (выходы)                            │
├─────────────────────────────────────────────────────────────┤
│  • Карточки идей (markdown)                                 │
│  • Контент-план на месяц/неделю                             │
│  • Экспорт в Publisher (publisher-card)                     │
└─────────────────────────────────────────────────────────────┘
```

## Поток данных (Data Flow)

### 1. Сбор данных (раз в неделю/месяц)
```
VK API → fetch_vk_posts.py → data/competitors/<group>/posts.json
                                  ↓
                            analyze_engagement.py → data/competitors/<group>/metrics.json
                                  ↓
                            extract_themes.py → data/competitors/<group>/themes.json

fetch_comments.py → data/competitors/<group>/comments.json
                                  ↓
                            mine_audience_pains.py → data/audience/pains.md
```

### 2. Генерация (по запросу)
```
profiles/* + sources/* + data/audience/* + data/competitors/* + data/history.json
                              ↓
                    generate_ideas.py (LLM-вызов)
                              ↓
                    templates/post-idea.md (формат)
                              ↓
                    data/ideas-bank.json + data/generated/<pack>.md
                              ↓
                    dedupe.py → обновить data/history.json
```

### 3. Планирование (раз в месяц)
```
data/ideas-bank.json + data/competitors/pulabru/ (самоанализ) + sources/seasonal-calendar.md
                              ↓
                    calendar_fill.py
                              ↓
                    data/generated/<month>-content-plan.md
```

### 4. Экспорт (по запросу)
```
data/ideas-bank.json (или выбранные id)
                              ↓
                    export_publisher.py
                              ↓
                    → Publisher Skill (publisher-card формат)
```

## Компоненты по слоям

### Слой данных (data/)
- **history.json** — все когда-либо сгенерированные идеи (дедуп)
- **ideas-bank.json** — текущий банк идей
- **competitors/<group>/** — кэш по каждому конкуренту
- **audience/** — выжимки по ЦА (pains, hooks, themes)

### Слой скриптов (scripts/)
- **vk_client.py** — обёртка VK API
- **llm_client.py** — обёртка LLM (Claude по умолчанию, Yandex/GigaChat опц.)
- **generate_ideas.py** — главный оркестратор
- **fetch_*, analyze_*, extract_*, mine_*** — сбор и анализ
- **dedupe.py, calendar_fill.py** — постобработка
- **export_publisher.py** — мост в Publisher

### Слой профилей (profiles/)
- **lab-zhelanii-ca.md** — портрет ЦА
- **tone-of-voice.md** — гайд по тону
- **rubrics.md** — рубрикатор
- **vk-community.md, blog-on-site.md, telegram.md** — формат-специфика

### Слой источников (sources/)
- **books-from-wl.md** — как тянуть темы из WL
- **coach-modules.md** — как тянуть темы из Coach
- **seasonal-calendar.md** — праздники/инфоповоды
- **trends-watchlist.md** — тренды ниши

### Слой шаблонов (templates/)
- **post-idea.md** — карточка для VK
- **blog-idea.md** — карточка для блога
- **telegram-idea.md** — карточка для TG
- **batch-report.md** — отчёт по пачке

## Состояния и потоки

| Файл | Кто пишет | Кто читает |
|---|---|---|
| `data/history.json` | generate_ideas.py, dedupe.py | generate_ideas.py (дедуп) |
| `data/ideas-bank.json` | generate_ideas.py | calendar_fill.py, export_publisher.py |
| `data/competitors/*/posts.json` | fetch_vk_posts.py | analyze_engagement.py, extract_themes.py |
| `data/competitors/*/metrics.json` | analyze_engagement.py | generate_ideas.py (приоритезация) |
| `data/audience/pains.md` | mine_audience_pains.py | generate_ideas.py (формулировки) |
| `data/generated/*-plan.md` | calendar_fill.py | человек / Publisher |

## Принципы

1. **Один источник истины** — `data/ideas-bank.json` для идей, `data/history.json` для дедупа
2. **Детерминированный сбор, генеративное создание** — парсинг и метрики детерминированы, идеи генерирует LLM с жёсткими промптами
3. **Локальный state** — всё хранится в `data/`, не в облаке (кроме LLM-вызовов)
4. **Модульность** — каждый скрипт работает независимо, оркестратор склеивает
5. **Без токенов для сбора** — VK API + личный токен, остальное — локальные Python-скрипты
6. **LLM-вызовы только для генерации идей** — извлечение тем, mining болей — либо правила, либо LLM (если качество важнее)

## Расширения (out of scope v0.1)

- ⏸ Веб-интерфейс (командная строка пока)
- ⏸ A/B-тесты идей (отложено в аналитику Publisher)
- ⏸ Прямая интеграция с VK API для автопубликации (идёт через Publisher)
- ⏸ Мульти-платформенный календарь с разными каналами (Telegram, email, YouTube)
- ⏸ Генерация визуала (это дизайн-пайплайн, не наш)
