---
name: english-quiz
description: Мини-тест по грамматическому времени
---

# english-quiz — мини-тест

10 вопросов (6 multiple_choice + 4 open) по конкретному грамматическому времени. Детерминированная проверка без LLM.

## Использование

```bash
# Пройти тест по Present Simple
python scripts/english.py quiz present-simple

# Проверить ответы из YAML
python scripts/english.py quiz present-simple --check=tmp/quiz_answers/present-simple.yaml

# Пройти заново (перезаписать score)
python scripts/english.py quiz present-simple --force
```

## Параметры

| Параметр | Описание |
|---|---|
| `tense` | Slug времени: `present-simple`, `past-simple`, `present-perfect`, ... |
| `--check=FILE` | YAML с ответами для проверки |
| `--force` | Пройти заново, перезаписать score |

## Доступные tense (11)

```
conditionals-1-2, future-will-going, passive-voice, past-continuous,
past-perfect, past-simple, present-continuous, present-perfect,
present-perfect-vs-past-simple, present-simple, reported-speech
```

## Workflow

### 1. Получить вопросы (без --check)

```
Mini-quiz: Present Simple
=========================
⏱ ~5 мин | 10 вопросов

## Как пройти
1. Прочитай вопросы ниже
2. Создай файл с ответами (шаблон в tmp/quiz_answers/present-simple.yaml)
3. Запусти с --check=...

## Вопрос 1
**She ___ on the auth service.**
- [ ] work
- [ ] works
- [ ] working
- [ ] worked
...
```

### 2. Заполнить шаблон

Открыть `tmp/quiz_answers/present-simple.yaml`:
```yaml
'# Заполни поле ''answer'' и запусти с --check=...': null
'1':
  prompt: 'She ___ on the auth service.'
  type: multiple_choice
  answer: works
'2':
  prompt: 'Переведи: ...'
  type: open
  answer: 'Yesterday I deployed the hotfix.'
```

### 3. Проверить (с --check)

```
# Результат: Present Simple
## 🎉 Score: 8/10 (80%)
_Отлично! Ты уверенно владеешь этим временем._

## Per-question feedback
### ✅ Вопрос 1
**She ___ on the auth service.**
- Твой ответ: `works`
- 💡 He/She/It + verb+s

### ❌ Вопрос 2
- Твой ответ: `yesterday i deploy hotfix`
- Правильный ответ: `Yesterday I deployed the hotfix.`
- 💡 Past Simple: V2 для завершённых действий
```

## Идемпотентность

- Score сохраняется в `state/progress.json:quiz_scores[<tense>]`
- Без `--force` повторный `quiz` покажет "уже проходила: 8/10"

## Проверка ответов

**multiple_choice:** точное совпадение (case-insensitive)
**open:** 3 уровня — exact / substring / acceptable_answers

Подробнее: [[../sub-skills/quiz-engine]]

## Связанные команды

- [[english-lesson]] — урок перед тестом
- [[english-progress]] — все quiz scores
- [[english-reset]] — сбросить scores
