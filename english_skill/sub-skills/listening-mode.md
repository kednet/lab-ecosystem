# listening-mode.md — каталог BBC/VOA + IT-подкастов

## Принципы

1. **Без скачивания** — Phase 1 только ссылки. Пользователь слушает в браузере/приложении.
2. **Curated** — 10 источников на 12 недель, не тысячи. Каждый источник = 1 конкретный навык.
3. **С comprehension questions** — каждое аудио имеет 3-5 вопросов на понимание.
4. **BBC + VOA + IT-подкасты** — микс общего English и IT-специфики.

## Источники (data/sources.yaml)

### BBC Learning English (4)

| ID | Title | Weeks | Уровень | Фокус |
|---|---|---|---|---|
| bbc-6min-job-titles | Job titles: what's the difference? | 1 | B1 | Рабочие роли в IT |
| bbc-podcast-working-from-home | Working from home | 2 | B1 | Remote work лексика |
| bbc-6min-meetings | Meetings: love them or hate them? | 3 | B1 | Meeting фразы |
| bbc-idioms-time | Idioms about time | 4 | B1-B2 | Идиомы времени |

### VOA Learning English (3)

| ID | Title | Weeks | Уровень | Фокус |
|---|---|---|---|---|
| voa-everyday-grammar-routines | Everyday Grammar: Daily Routines | 1 | B1 | Present Simple в действии |
| voa-health-sleep | Health Report: Sleep | 5 | B1 | Continuous tenses |
| voa-education-report | Education Report | 6 | B1-B2 | Future tenses |

### IT-подкасты (3)

| ID | Title | Weeks | Уровень | Фокус |
|---|---|---|---|---|
| code-review-podcast | CodeNewbie: First week at new job | 8 | B1-B2 | Past Simple, истории |
| developer-voices-standup | Developer Voices: Standup vs status | 3 | B1 | Meeting ритуалы |
| soft-skills-engineering | Soft Skills Engineering: Code review etiquette | 9 | B2 | Diplomatic language |

## Структура source в YAML

```yaml
- id: bbc-6min-meetings
  title: Meetings: love them or hate them?
  source: BBC Learning English — 6 Minute English
  url: https://www.bbc.co.uk/learningenglish/...
  transcript_url: https://www.bbc.co.uk/...
  duration_min: 6
  level: B1
  weeks: [3, 4]              # рекомендованные недели
  summary: "Episode about different meeting cultures..."
  vocab:
    - "to attend a meeting"
    - "action item"
    - "to wrap up"
  comprehension_questions:
    - q: "What's the main complaint about meetings?"
      sample_answer: "They're often too long and unproductive."
    - q: "What does 'to wrap up' mean?"
      sample_answer: "To finish/conclude."
```

## Как используется (cmd_listen)

```bash
# Аудио для текущей недели
python scripts/english.py listen

# Конкретная неделя
python scripts/english.py listen --week=3
```

**Алгоритм:**
1. Загрузить `data/sources.yaml`
2. Отфильтровать по `weeks: [N]` (текущая неделя пользователя)
3. Распечатать:
   - Title + source + duration + URL + transcript URL
   - Vocab список с переводом
   - Comprehension questions с sample answers
4. Подсчёт общего времени

## Методика прослушивания

**3 прохода:**

1. **Pass 1 — Global understanding** (без субтитров)
   - Понять общий смысл (60% comprehension достаточно)
   - Засечь время (обычно 5-7 мин)

2. **Pass 2 — Detailed listening** (с transcript)
   - Читать transcript одновременно с аудио
   - Выписать незнакомые слова в отдельный блокнот
   - Заметить collocations (e.g., "take it offline")

3. **Pass 3 — Comprehension check**
   - Ответить на comprehension questions **устно** (это speaking practice!)
   - Сверить с sample_answer
   - Повторить вслух 1-2 ключевые фразы из аудио

**Общее время:** ~20-25 мин на один source.

## Почему не делаем авто-скачивание

- **MITM/SOCKS** — корпоративная сеть может ломать HTTPS
- **Размер** — mp3 весят 5-10 МБ, не нужны в state
- **Привычка** — пользователь сам выбирает когда слушать (утро в метро, вечер дома)
- **Subtitles** — BBC/VOA имеют transcripts рядом, не нужны .srt файлы

## Phase 2: что можно добавить

- **Pocket/Telegram integration** — кидать ссылку в Pocket
- **Anki auto-flashcards** — vocab сразу в Anki
- **Transcripts offline** — кешировать transcripts в `tmp/`
- **Speech recognition** — проверять произношение user-повторов

## Связь

- [[curriculum-design]] — где listening встраивается в 7-дневный ритм
- [[progress-tracking]] — listening не имеет отдельного score, помечается как lesson_done
