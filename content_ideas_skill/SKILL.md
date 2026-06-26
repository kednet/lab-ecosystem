---
name: content-ideas-skill
description: Генерация идей постов для VK/блога/TG под ЦА «Лаборатории желаний» с интеграцией WishLibrarian, WishCoach, SEO Advisor, Publisher и аналитикой конкурентов
metadata:
  version: 0.1.0-draft
  status: спецификация
  date: 2026-06-11
  ecosystem: pulabru
  depends_on: [wishlibrarian-project, wishcoach-project, seo-advisor-skill, publisher-skill-built, expert-reviews-hub]
---

# Content Ideas Skill — главный оркестратор

## Назначение

Генерация **готовых к производству** идей постов для соцсетей (VK, опционально TG) и блога на сайте «Лаборатории желаний» (далее — ЛЖ).

Идея — это не просто «о чём написать», а **карточка с темой, углом, источником, CTA, целевой метрикой и привязкой к ЦА**, которая может быть передана в Publisher Skill без переработки.

## Что НЕ делает скил

- ❌ Не пишет финальные тексты (это работа LLM/Copilot на этапе render в Publisher)
- ❌ Не публикует контент (это Publisher)
- ❌ Не оптимизирует готовые тексты под SEO (это SEO Advisor)
- ❌ Не генерирует визуал (это дизайнер / генератор картинок)

## Что делает

- ✅ Генерирует идеи с приоритезацией (что сработает, подкреплено данными)
- ✅ Тянет темы из 4 источников: WL-книги, Coach-модули, конкуренты, боли ЦА
- ✅ Считает дедуп (не повторяемся с историей)
- ✅ Собирает контент-планы (N дней/недель/месяцев)
- ✅ Экспортирует идеи в Publisher (рендер + публикация)
- ✅ Анализирует конкурентов и ЦА (mining)
- ✅ Ведает календарём сезонных тем

## Архитектура в одном абзаце

`generate_ideas.py` — CLI-оркестратор, который комбинирует **4 источника** (sources: WL/Coach, competitors, audience-mining, seasonal) с **фильтрами** (profiles: ЦА, тон, рубрикатор) и **историей** (data/history.json) → выдаёт `data/ideas-bank.json` + карточки в `data/generated/`. Побочные скрипты отвечают за сбор данных (парсинг VK, mining комментов, тренды). Экспорт в Publisher через `export_publisher.py`.

---

## Структура скила

```
content_ideas_skill/
├── SKILL.md                  ← вы здесь
├── README.md                 ← краткий обзор для быстрого старта
│
├── profiles/                 ← КТО мы и для КОГО пишем
│   ├── lab-zhelanii-ca.md           портрет ЦА ЛЖ
│   ├── tone-of-voice.md             гайд по тону (5 интенсивностей × 4 тона)
│   ├── rubrics.md                   рубрикатор (5-7 рубрик)
│   ├── vk-community.md              специфика VK-формата
│   ├── blog-on-site.md              специфика блога
│   └── telegram.md                  (опц.) специфика TG
│
├── sources/                  ← ОТКУДА берём идеи
│   ├── books-from-wl.md             как тянуть темы из WishLibrarian
│   ├── coach-modules.md             как тянуть темы из WishCoach
│   ├── seasonal-calendar.md         праздники/инфоповоды РФ
│   └── trends-watchlist.md          актуальные тренды ниши
│
├── competitors/              ← КТО наши конкуренты
│   ├── SKILL-competitors.md         гайд по анализу
│   ├── tracker.md                   список пабликов для мониторинга
│   ├── vk-pulabru-analysis.md       самоанализ своего паблика
│   └── references/
│       └── competitor-template.md   карточка одного конкурента
│
├── audience-mining/          ← ЧТО болит ЦА (её словами)
│   ├── SKILL-audience.md
│   ├── ca-deep-profile.md           расширенный портрет ЦА
│   ├── pain-language-bank.md        язык болей (из реальных комментов)
│   ├── hooks-from-comments.md       формулировки-крючки
│   └── hooks/
│       └── top-hooks.json           топ формулировок
│
├── templates/                ← ШАБЛОНЫ выхода
│   ├── post-idea.md                 карточка идеи для VK
│   ├── blog-idea.md                 карточка идеи для блога
│   ├── telegram-idea.md             (опц.) карточка для TG
│   └── batch-report.md              отчёт по пачке идей
│
├── formulas/                 ← КАК писать
│   ├── hook-formulas.md             20+ формул крючков
│   ├── cta-formulas.md              формулы CTA
│   ├── reformat-rules.md            правила VK ↔ блог ↔ TG
│   └── structure-patterns.md        структуры (AIDA, PAS, storytelling)
│
├── scripts/                  ← Python-движок
│   ├── generate_ideas.py            ← главный CLI-оркестратор
│   ├── fetch_vk_posts.py            парсер постов VK (VK API)
│   ├── fetch_comments.py            парсер комментов
│   ├── analyze_engagement.py        метрики постов
│   ├── extract_themes.py            LLM/NLP-извлечение тем
│   ├── mine_audience_pains.py       mining болей из комментов
│   ├── trending_topics.py           сезонные тренды + инфоповоды
│   ├── dedupe.py                    дедуп по history.json
│   ├── calendar_fill.py             сборка контент-плана
│   ├── export_publisher.py          мост в Publisher Skill
│   └── lib/
│       ├── vk_client.py             обёртка VK API
│       ├── llm_client.py            обёртка LLM (Claude/Yandex/GigaChat)
│       └── io_utils.py              I/O и JSON
│
├── data/                     ← ДАННЫЕ (state)
│   ├── history.json                 все сгенерированные идеи (дедуп)
│   ├── ideas-bank.json              банк идей
│   ├── competitors/                 кэш по конкурентам
│   │   ├── pulabru/                 свои посты + метрики
│   │   ├── competitor-1/
│   │   └── ...
│   ├── audience/                    выжимки по ЦА
│   │   ├── pains.md
│   │   ├── hooks.md
│   │   └── themes.md
│   └── generated/                   выгрузки
│       ├── 2026-07-vk-pack.md
│       ├── 2026-07-blog-articles.md
│       └── 2026-07-content-plan.md
│
├── examples/                 ← ПРИМЕРЫ (1-2 пачки)
│   ├── 10-post-pack.md              пример пачки VK
│   ├── 4-blog-articles.md           пример пачки блога
│   └── competitor-analysis-report.md
│
├── docs/                     ← ДОКУМЕНТАЦИЯ
│   ├── architecture.md              подробная схема
│   ├── sources-priority.md          приоритеты источников
│   ├── data-schema.md               схемы JSON
│   └── integration.md               интеграции с WL/Coach/SEO/Publisher
│
└── config.yaml               ← настройки (токены, группы, лимиты)
```

---

## Источники идей (4 канала)

| Приоритет | Источник | Что даёт | Скрипт |
|---|---|---|---|
| 🥇 1 | **WL-книги** | готовые темы, цитаты, ключевые идеи | `extract_themes.py --source wl` |
| 🥇 1 | **Coach-модули** | темы детектора «навязанное vs истинное» | `extract_themes.py --source coach` |
| 🥈 2 | **Боли ЦА** (комменты конкурентов) | язык аудитории, реальные формулировки | `mine_audience_pains.py` |
| 🥈 2 | **Конкуренты** (топовые темы) | валидация спроса, форматы | `analyze_engagement.py` |
| 🥉 3 | **Сезонный календарь** | привязка к датам | `trending_topics.py` |
| 🥉 3 | **Тренды ниши** | актуальные темы | `trending_topics.py --source trends` |

Подробно: [`docs/sources-priority.md`](docs/sources-priority.md)

---

## Фильтры (что НЕ пропускаем)

1. **`profiles/lab-zhelanii-ca.md`** — отсекает всё, что мимо ЦА
2. **`profiles/tone-of-voice.md`** — отсекает «успешный успех», эзотерику, токсичную мотивацию
3. **`profiles/rubrics.md`** — оставляет только то, что вписывается в рубрикатор
4. **`data/history.json`** — дедуп (не повторяем тему/угол/крючок)
5. **`data/competitors/pulabru/`** — не повторяем то, что сами недавно публиковали

---

## Формат идеи на выходе

`templates/post-idea.md` — карточка, которую можно сразу передать в Publisher:

```yaml
id: idea-2026-07-15-001
created: 2026-07-01
target: vk | blog | telegram
rubric: "разбор-цитаты" | "практика" | "история" | "миф-vs-правда" | "провокация" | "мини-урок" | "подборка"
title: "..."
hook: "..."
key_idea: "1-2 предложения, о чём пост"
structure_hint: AIDA | PAS | storytelling | list
source:
  type: wl | coach | competitor-pain | seasonal | trend
  ref: "книга WL-id-123, модуль Coach-detect-2, конкурент X пост от YYYY-MM-DD"
cta: "..."
target_metric: "комменты" | "репосты" | "сохранения" | "переходы"
priority: high | medium | low
reasoning: "почему эта идея сработает (1-2 предложения)"
notes: "ограничения, юмор, что не писать"
```

---

## Контент-план (calendar_fill.py)

На входе: `--month 2026-07 --mix "60%vk,30%blog,10%tg" --posts-per-week 4`

На выходе: `data/generated/2026-07-content-plan.md` с сеткой:

| Дата | День недели | Формат | Рубрика | Идея (id) | Цель |
|---|---|---|---|---|---|
| 2026-07-01 | среда | VK | разбор-цитаты | idea-2026-07-15-001 | комменты |
| ... | ... | ... | ... | ... | ... |

Правила сборки:
- Минимум 4 рубрики в месяц (разнообразие)
- Сезонные темы привязаны к датам
- WL-книги — равномерно (не 3 поста подряд из одной книги)
- После провокации — не провокация (избегаем «крикливого» тона подряд)
- Блог — 1–2 раза в неделю, VK — 3–5 раз

---

## Интеграции

| Скил | Направление | Что передаём |
|---|---|---|
| **WishLibrarian** | ← | список книг, цитаты, идеи (источник 1-го приоритета) |
| **WishCoach** | ← | модули детектора, типы желаний (источник 1-го приоритета) |
| **SEO Advisor** | → | идеи для блога с ключами → SEO-пакет |
| **Publisher** | → | готовые карточки идей → рендер + публикация |
| **Expert & Reviews Hub** | ← | готовые обзоры книг → адаптация в посты |

Подробно: [`docs/integration.md`](docs/integration.md)

---

## Команды CLI (cheat sheet)

```bash
# === Сбор данных (раз в неделю/месяц) ===
python scripts/fetch_vk_posts.py --group pulabru --depth 200
python scripts/fetch_vk_posts.py --group competitor-1 --depth 200
python scripts/fetch_comments.py --group competitor-1 --top-posts 20
python scripts/mine_audience_pains.py --group competitor-1
python scripts/analyze_engagement.py --group competitor-1

# === Генерация идей ===
python scripts/generate_ideas.py \
  --theme "навязанные желания" \
  --count 10 \
  --target vk \
  --audience ca-zhelanii

python scripts/generate_ideas.py \
  --source wl \
  --count 5 \
  --target blog

python scripts/generate_ideas.py \
  --source pains \
  --count 8 \
  --target vk \
  --rubric "провокация"

# === Контент-план ===
python scripts/calendar_fill.py \
  --month 2026-07 \
  --mix "60%vk,30%blog,10%tg" \
  --posts-per-week 4

# === Экспорт ===
python scripts/export_publisher.py \
  --ideas data/ideas-bank.json \
  --target vk \
  --format publisher-card

# === Дедуп / история ===
python scripts/dedupe.py --show-stats
python scripts/dedupe.py --archive-old
```

---

## Юридические правила (вшить в скрипты)

- ✅ Берём **темы, структуры, рубрики** у конкурентов — это не защищено
- ✅ Цитируем **с указанием автора** и источника
- ❌ Не делаем машинный рерайт чужих текстов
- ❌ Не копируем чужие формулировки 1-в-1
- ✅ Используем VK API в рамках правил VK
- ⚠️ Парсинг открытых данных — серая зона; не злоупотребляем частотой

---

## MVP v0.1 — что в первой версии

**Включаем:**
- ✅ `generate_ideas.py` (генератор с 2 источниками: WL + ручной ввод)
- ✅ `profiles/lab-zhelanii-ca.md` (портрет ЦА)
- ✅ `profiles/rubrics.md` (5 рубрик)
- ✅ `templates/post-idea.md` (карточка идеи)
- ✅ `data/history.json` (дедуп)
- ✅ `dedupe.py` (минимальный)
- ✅ `calendar_fill.py` (минимальный)

**Отложим на v0.2:**
- ⏸ VK-парсеры (начнём с ручного ввода)
- ⏸ Mining болей (начнём с экспертных гипотез)
- ⏸ Интеграция с WL/Coach (начнём с копипаста из их выгрузок)
- ⏸ Publisher-экспорт (начнём с markdown)
- ⏸ Telegram (только если попросят)

**Оценка:** MVP v0.1 = 1–2 сессии, затем v0.2 с парсерами ещё 3–4.

---

## Метрики успеха скила

- Время от «нужен пост на завтра» до готовой идеи: **< 2 минуты**
- Идей, которые доходят до публикации: **> 70%** (не в стол)
- Средний ER (engagement rate) постов по идеям скила vs без: **+30%** через 3 месяца
- Дедуп-эффективность: **0 повторов** темы/угла за 6 месяцев
- Покрытие рубрик: **все 5+ рубрик** задействованы каждый месяц

---

## Открытые вопросы (на обсуждение)

1. **Telegram** — нужен ли в MVP или это v0.3?
2. **YouTube Shorts / Reels** — входит в нишу или нет?
3. **Email-рассылка** для подписчиков сайта — отдельный скил?
4. **Анализ VK Ads** — отдельный модуль или входит в competitors?
5. **LLM-провайдер** для generate_ideas.py — Claude (как основной в стеке) или Yandex/GigaChat (дешевле на больших объёмах)?

---

## Следующие шаги

1. **Согласовать `SKILL.md`** — отметить, что добавить/убрать
2. **Заполнить `profiles/lab-zhelanii-ca.md`** — фундамент (1 сессия)
3. **Заполнить `profiles/rubrics.md`** — 5–7 рубрик (0.5 сессии)
4. **Написать `generate_ideas.py` v0.1** — минимальный CLI (1–2 сессии)
5. **Дальше:** парсеры, mining, интеграции
