---
name: english-lesson
description: Урок дня (грамматика + listening + mini-tasks + vocab)
---

# english-lesson — урок дня

Рендерит markdown-урок для текущего дня недели: грамматика, listening, мини-задания, vocab.

## Использование

```bash
# Урок текущего дня
python scripts/english.py lesson

# Конкретный день текущей недели
python scripts/english.py lesson --day=3

# Конкретная неделя + день
python scripts/english.py lesson --week=5 --day=2

# Пройти заново (игнорировать идемпотентность)
python scripts/english.py lesson --force
```

## Параметры

| Параметр | Описание |
|---|---|
| `--day=N` | День недели (1-7), default = `current_day` |
| `--week=N` | Неделя (1-12), default = `current_week` |
| `--force` | Пройти заново (перезапишет state/lessons/<slug>.json) |

## Что входит в урок

1. **Header** — Week/Day, тип урока (intro/grammar/listening/dialog/quiz/review), грамматика
2. **Content** — основной текст урока (rules, examples, tips)
3. **Listening** — ссылки на BBC/VOA + vocab + comprehension questions
4. **Mini-tasks** — задания (переведи, напиши, ...)
5. **Dialog** — ссылка на ролевой диалог (если есть)
6. **Quiz** — ссылка на мини-тест (если есть)
7. **Vocab дня** — слова для запоминания

## Идемпотентность

- **Без `--force`:** если `state/lessons/<w>_<d>_<type>.json` существует → "уже пройдено"
- **`--force`:** помечает как done повторно, обновляет `done_at`

## Streak

Каждый `lesson` (даже повторный) вызывает `update_streak_on_active()`.

## Связанные команды

- [[english-week]] — посмотреть расписание
- [[english-quiz]] — тест после урока
- [[english-dialog]] — speaking practice (если урок = dialog)
- [[english-listen]] — listening (если урок = listening)
