# Expert & Reviews Hub

Универсальный навык для сбора и структурирования **отзывов** и **экспертных карточек** для экосистемы «Лаборатория желаний».

## Что делает

- **Эксперты** — карточки специалистов, поиск упоминаний, каталог ресурсов, связь с WL
- **Отзывы** — парсинг LiveLib / Литрес / Ozon / VK / Telegram / YouTube / собственного сайта, AI-суммаризация
- **Связи** — граф «эксперты ↔ книги ↔ отзывы» для перелинковки

## Структура

```
expert-reviews-hub/
├── SKILL.md                  # Оркестратор (13 команд)
├── sub-skills/
│   ├── experts.md            # 5 режимов работы с экспертами
│   └── reviews.md            # 7 режимов работы с отзывами
├── prompts/                  # 10 промптов (5 + 5)
│   ├── expert-card.md
│   ├── expert-mentions.md
│   ├── expert-resources.md
│   ├── expert-wl-link.md
│   ├── review-livelib.md
│   ├── review-litres.md
│   ├── review-ozon.md
│   ├── review-social.md
│   ├── review-own.md
│   └── review-summarize.md
├── data/                     # Справочные данные
│   ├── sources-rating.md     # Веса источников
│   ├── expert-domains.md     # Приоритетные домены
│   └── stop-words-experts.md # Чёрный список
├── templates/                # Шаблоны
│   ├── expert-card.md
│   ├── expert-schema.json
│   ├── review-bundle.md
│   └── review-summarize.md
├── scripts/                  # Python-парсеры
│   ├── parse_livelib.py
│   ├── parse_litres.py
│   ├── parse_vk_reviews.py
│   └── review_stats.py
└── examples/                 # Примеры готовых файлов
    ├── expert-card.md
    ├── review-bundle.md
    └── crosslink-report.md
```

## Быстрый старт

### 1. Собрать отзывы на книгу

```bash
# Спарсить из топ-3 источников
python scripts/parse_livelib.py "Трансерфинг реальности" "Вадим Зеланд"
python scripts/parse_litres.py "Трансерфинг реальности" "Вадим Зеланд"
python scripts/parse_ozon.py "Трансерфинг реальности"

# Сводная статистика
python scripts/review_stats.py reviews/transerfing-realnosti/
```

### 2. AI-суммаризация

В Claude Code вызвать:
```
/reviews summarize "Трансерфинг реальности"
```
→ получите markdown-отчёт с pros/cons, рейтингом, цитатами, трендами.

### 3. Карточка эксперта

```
/experts card "Марк Розин"
```
→ получите готовую markdown-карточку + Schema.org JSON-LD.

### 4. Граф связей

```
/experts link "Трансерфинг реальности"
```
→ узнаете, какие эксперты рекомендуют книгу, какие книги связаны.

## Интеграция с экосистемой

| Сервис | Как используется |
|--------|------------------|
| **WishLibrarian** (`C:\Users\kfigh\wish_librarian\`) | Ищет обработанные книги для `/experts link` |
| **SEO Advisor** (`C:\Users\kfigh\seo-advisor-skill\`) | Использует `weighted_average` для `AggregateRating`, `Person` schema для экспертов |
| **Publisher** (`C:\Users\kfigh\publisher_agent\`, план) | Будет читать `summary.json` для публикации |
| **WishCoach** (`C:\Users\kfigh\coach_agent\`) | Использует карточки экспертов-тренеров |
| **VK community** (id 237295798) | Парсинг отзывов подписчиков |

## Веса источников отзывов

| Источник | Вес | Почему |
|----------|-----|--------|
| Литрес, свои | 1.5 | Verified покупатели / клиенты |
| LiveLib | 1.2 | Крупнейшая база, без verified |
| Ozon | 0.7 | Много накруток |
| VK, Telegram, YouTube | 0.7-0.9 | Живой контент, но без формального рейтинга |

Подробнее: `data/sources-rating.md`

## Этические ограничения

- **Не покупаем отзывы** — только собираем
- **Не публикуем без модерации** — особенно свои
- **Уважаем robots.txt** и ToS площадок
- **YMYL-дисклеймеры** для психологии/здоровья
- **Указываем источник** при цитировании

## Лицензия и авторство

Часть экосистемы «Лаборатория желаний» (id 237295798, pulabru).
Используется для каталога книг, рассылок, лендингов.
