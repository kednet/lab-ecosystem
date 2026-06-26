# progress-tracking.md — state/progress.json + идемпотентность

## Структура state/

```
state/
├── progress.json              ← глобальный state
└── lessons/                   ← per-lesson state (для идемпотентности)
    ├── 1_1_intro.json
    ├── 1_2_grammar.json
    └── ...
```

## state/progress.json

```json
{
  "started_at": "2026-06-25T13:38:35Z",
  "user_level": "B1",
  "goal": "IT/business English",
  "current_week": 1,
  "current_day": 1,
  "streak_days": 7,
  "last_active_date": "2026-06-25",
  "lessons_done": [
    "1_1_intro",
    "1_2_grammar",
    "1_3_listening",
    "1_4_grammar",
    "1_5_dialog",
    "1_6_quiz",
    "1_7_review"
  ],
  "quiz_scores": {
    "present-simple": 9,
    "past-simple": 8
  },
  "last_active_at": "2026-06-25T13:45:00Z"
}
```

## Идемпотентность уроков

**Slug урока:** `{week}_{day}_{type}`, например `1_3_listening`.

**Правило:** если `state/lessons/<slug>.json` существует — урок **не выполняется заново** без `--force`.

**Файл per-lesson:**
```json
{
  "slug": "1_3_listening",
  "week": 1,
  "day": 3,
  "type": "listening",
  "started_at": "2026-06-25T14:00:00Z",
  "done_at": "2026-06-25T14:25:00Z"
}
```

**Зачем это нужно:**
- kfigh может прервать урок на полпути — запуск `lesson` не дублирует
- Нет накопления фантомных "пройдено" если контент урока поменялся
- `--force` для явного re-do

## Streak tracking

**Логика:**
1. При любой активности (`lesson`, `quiz --check`, `dialog --answer`) → `update_streak_on_active()`
2. Сравниваем `last_active_date` с сегодня:
   - **Тот же день** → streak не меняется
   - **Следующий день** (delta = 1) → streak + 1
   - **Пропуск** (delta > 1) → streak = 1 (начинаем заново)
3. `last_active_date = today`

**Почему не +1 за каждый запуск?**
Это даёт "ложный streak" — 10 запусков в один день = 10 дней. Мы считаем именно **calendar days with activity**.

**Целевые вехи:**
- 7 дней → разблокировка Week 2 (моральный reward)
- 30 дней → полный месяц (можно сказать "привычка сформирована")
- 84 дня (12 недель × 7) → курикулум завершён

## Защита от потери прогресса

**Транзакции не используются** (это не БД), но есть защиты:

1. **Атомарная запись** — каждый JSON пишется через `json.dump` в tempfile + rename
2. **Backup перед reset** — `reset --all` не делает backup автоматически, но печатает список того, что удалит
3. **Source of truth** — `state/progress.json` единственный, lessons_done — derived (но тоже хранится для скорости)

## Что НЕ хранится в state/

- **Содержимое уроков** — захардкожено в `data/curriculum.yaml`
- **Quiz ответы** — только итоговый score, не детальные ответы
- **User-реплики из dialog** — хранятся в `tmp/dialog_answers/` (не критично)

## API (state.py)

```python
init_progress() -> dict
load_progress() -> dict                    # читает progress.json
save_progress(progress: dict) -> None     # атомарная запись

mark_lesson_done(week, day, type) -> None
is_lesson_done(week, day, type) -> bool
start_lesson(week, day, type) -> None     # помечает как начатый

set_quiz_score(tense, score) -> None
get_quiz_score(tense) -> Optional[int]

set_current(week, day) -> None             # переключает current_week/day
update_streak_on_active() -> int          # возвращает новый streak

reset_week(week) -> None
reset_all() -> None                       # удаляет всё state/
```

## Связь

- [[curriculum-design]] — почему 12 недель
- [[quiz-engine]] — как записывается quiz_score
