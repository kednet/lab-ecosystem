# Схемы данных (JSON)

## 1. data/history.json — история идей (дедуп)

```json
{
  "version": "1.0",
  "created": "2026-06-11",
  "ideas": [
    {
      "id": "idea-2026-07-01-001",
      "created": "2026-07-01T12:34:56",
      "title": "...",
      "rubric": "разбор-цитаты",
      "theme": "навязанные желания",
      "hook_keywords": ["не понимаю", "чего хочу", "на самом деле"],
      "source_type": "wl",
      "source_ref": "wl-book-id-123",
      "fingerprint": "abc123def456"
    }
  ]
}
```

**fingerprint** — хеш от (theme + rubric + hook_keywords), используется для дедупа.

## 2. data/ideas-bank.json — банк идей

```json
{
  "version": "1.0",
  "updated": "2026-07-01T12:34:56",
  "ideas": [
    {
      "id": "idea-2026-07-01-001",
      "created": "2026-07-01T12:34:56",
      "target": "vk",
      "rubric": "разбор-цитаты",
      "title": "5 фраз, которые выдают чужое желание",
      "hook": "«Я просто хочу как все» — и почему это красный флаг",
      "key_idea": "...",
      "structure_hint": "storytelling",
      "source": {
        "type": "wl",
        "ref": "wl-book-id-123",
        "quote": "..."
      },
      "cta": "А у вас было такое? Расскажите в комментах",
      "target_metric": "комменты",
      "priority": "high",
      "reasoning": "Тема в топе у конкурента X, адаптирована под тон ЛЖ",
      "notes": "Не использовать 'успешный успех', избегать нравоучения"
    }
  ]
}
```

## 3. data/competitors/<group>/posts.json — посты конкурента

```json
{
  "version": "1.0",
  "group": "competitor-1",
  "fetched": "2026-07-01T00:00:00",
  "posts": [
    {
      "id": "post-12345",
      "date": "2026-06-15T10:00:00",
      "text": "...",
      "views": 12345,
      "likes": 234,
      "reposts": 45,
      "comments": 67,
      "engagement_rate": 0.027,
      "themes_extracted": ["навязанные желания", "вина", "выбор"]
    }
  ]
}
```

## 4. data/competitors/<group>/comments.json — комменты

```json
{
  "version": "1.0",
  "group": "competitor-1",
  "fetched": "2026-07-01T00:00:00",
  "comments": [
    {
      "post_id": "post-12345",
      "date": "2026-06-15T10:30:00",
      "text": "Не понимаю, чего я на самом деле хочу...",
      "likes": 12,
      "classification": "боль",
      "pain_category": "непонимание себя"
    }
  ]
}
```

## 5. data/generated/<pack>.md — выгрузка

Markdown с заголовками и списком карточек идей. Шаблон в `templates/batch-report.md`.

## 6. data/audience/pains.md — боли ЦА

```markdown
# Боли ЦА «Лаборатории желаний»

Дата сбора: 2026-07-01
Источник: комментарии к 50 топовым постам 5 конкурентов

## Топ-5 болей

1. **«Не понимаю, чего хочу на самом деле»** (47 упоминаний)
   - Вариации: "не знаю, что хочу", "хочу, но не понимаю что", "вроде всё есть, а радости нет"
   - Цитаты: [...]

2. **«Всегда выбираю не то, что хочу, а что "правильно"»** (31 упоминание)
   ...

## Возражения (топ-3)

1. "Это эзотерика / ерунда / не работает" (12)
2. ...

## Инсайты (топ-3)

1. "Оказывается, я всю жизнь хотела [X], а делала [Y]" (8)
2. ...
```

## 7. config.yaml — настройки

```yaml
# Пути к зависимым скилам
paths:
  wishlibrarian: "C:\Users\kfigh\wish_librarian"
  wishcoach: "C:\Users\kfigh\coach_agent"
  publisher: "C:\Users\kfigh\publisher_skill"
  seo_advisor: "C:\Users\kfigh\seo-advisor-skill"

# VK API
vk:
  token_env: "VK_TOKEN"  # читается из .env
  rate_limit_per_sec: 3

# LLM
llm:
  provider: "claude"  # claude | yandex | gigachat
  model: "claude-sonnet-4-6"
  max_tokens: 2000
  temperature: 0.7

# Лимиты
limits:
  max_ideas_per_run: 50
  max_history_size: 5000
  archive_after_days: 365

# Конкуренты для мониторинга
competitors:
  - id: "competitor-1"
    name: "Название сообщества"
    url: "https://vk.com/competitor1"
    active: true
  - id: "pulabru"
    name: "Лаборатория желаний (своё)"
    url: "https://vk.com/pulabru"
    active: true  # self-analysis
```

## 8. publisher-card формат (экспорт в Publisher)

```yaml
- id: idea-2026-07-01-001
  target: vk
  payload:
    title: "..."
    hook: "..."
    key_idea: "..."
    source_ref: "..."
    cta: "..."
    target_metric: "комменты"
  meta:
    rubric: "разбор-цитаты"
    priority: "high"
    export_date: "2026-07-01"
```
