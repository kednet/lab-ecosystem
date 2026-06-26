# SEO Advisor Skill v2.0

Полноценный SEO-скил для Claude Code / Claude: оптимизация страниц под Яндекс + Google, Schema.org, E-E-A-T, FAQ, OG/VK-превью, аудиты.

**Заточен под:**
- Нишу саморазвития, психологии, исполнения желаний (YMYL)
- Страницы книг, блога, экспертов, лендингов
- Экосистему «Лаборатории желаний» (WishLibrarian, Publisher, Coach, Landings)

## 🚀 Быстрый старт

### Команды (вызывай скил и говори)
```
/seo optimize <URL или HTML>    — полная оптимизация страницы
/seo keywords "<тема>"         — семантическое ядро + LSI + PAA
/seo audit <URL>                — аудит сайта с приоритетами
/seo competitor <URL>           — SERP-анализ конкурента
/seo schema <Book|Article|FAQ>  — генерация JSON-LD
/seo eeat <URL>                 — E-E-A-T аудит (YMYL)
/seo faq "<тема>"              — FAQ-блок + PAA
/seo og <URL>                   — OG/VK/Twitter превью
/seo slug "<заголовок>"        — URL-slug
/seo readability <file>         — анализ читаемости
```

### Установка
```bash
# Скопировать в .claude/skills/
cp -r C:/Users/kfigh/seo-advisor-skill ~/.claude/skills/

# Перезапустить Claude Code
# Активировать: /skill use seo-advisor
```

### Python-скрипты
```bash
# Slug
python scripts/slugify.py "Трансерфинг реальности — Вадим Зеланд"
# → transerfing-realnosti-vadim-zeland

# Readability
python scripts/readability.py page.txt
# → скоры Flesch-Kincaid + вода

# Schema-validate
python scripts/schema-validate.py page.html
# → проверка JSON-LD блоков
```

## 📁 Структура
```
seo-advisor-skill/
├── SKILL.md                    ← главный файл (начни с него)
├── prompts/                    ← 7 промптов по режимам
│   ├── page-optimization.md    ← ядро: оптимизация страницы
│   ├── keywords.md             ← семантика + LSI + PAA
│   ├── schema.md               ← Schema.org генератор
│   ├── eeat.md                 ← E-E-A-T аудит (YMYL)
│   ├── faq.md                  ← FAQ-генератор
│   ├── url-slug.md             ← Slug-генератор
│   └── seo-audit.md            ← Аудит сайта
├── templates/
│   ├── meta-template.md        ← мета-теги по типу страницы
│   ├── og-template.md          ← OG/VK/Twitter
│   └── schema/                 ← 8 готовых JSON-LD
│       ├── book.json
│       ├── article.json
│       ├── faq.json
│       ├── person.json
│       ├── organization.json
│       ├── breadcrumb.json
│       ├── review.json
│       └── website.json
├── examples/
│   ├── book-page.md            ← пример оптимизации
│   └── report.md               ← пример аудита
├── data/                       ← база знаний
│   ├── yandex-factors.md       ← факторы Яндекса 2026
│   ├── google-factors.md       ← факторы Google 2026
│   ├── lsibase.md              ← LSI по нишам
│   ├── intent-patterns.md      ← поисковые интенты
│   └── stop-words.md           ← стоп-слова для slug
└── scripts/                    ← Python-хелперы
    ├── slugify.py
    ├── readability.py
    └── schema-validate.py
```

## 🔗 Интеграция
- **WishLibrarian** — встроить `/seo optimize` как последний шаг генерации конспекта
- **Publisher** — автозапуск `/seo audit` перед публикацией
- **Landing agent** — `/seo keywords` + `/seo topical-map` на этапе проектирования
- **WishCoach** — `/seo optimize` для лендинга тренера

## 📚 Документация
- Главный файл: `SKILL.md`
- Все режимы: `prompts/*.md`
- База знаний: `data/*.md`
- Примеры: `examples/*.md`

## 🎯 Приоритеты (P0 → P3)

**P0 — критично для YMYL-ниши саморазвития:**
- E-E-A-T (дисклеймеры, авторы, источники, даты)
- FAQ + FAQPage schema (featured snippets)
- Schema.org (Book, Article, FAQ, Person, Organization)
- OG/VK-превью (важно для экосистемы)

**P1 — заметный буст:**
- LSI + интент (топикальное покрытие)
- Яндекс.Вебмастер (Оригинальные тексты, sitemap)
- URL-slug оптимизация

**P2 — полировка:**
- Readability, Flesch-Kincaid
- Content-refresh
- Snippet-оптимизатор

**P3 — удобство:**
- Python-скрипты (slugify, readability, schema-validate)

## ⚖️ Этика
- Не накручиваем
- Не гарантируем позиции
- Не используем чёрное SEO
- Не оптимизируем мед.темы без дисклеймера
- YMYL → обязательный E-E-A-T
