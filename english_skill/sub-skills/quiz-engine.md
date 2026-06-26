# quiz-engine.md — детерминированная проверка (без LLM)

## Принципы

1. **Детерминизм** — один и тот же ответ → один и тот же результат. Никакой случайности.
2. **Прозрачность** — пользователь видит правильный ответ + объяснение после `quiz --check`.
3. **Без LLM** — Phase 1 не требует API-ключей, всё работает офлайн.

## Типы вопросов

### 1. multiple_choice

```yaml
- id: 1
  type: multiple_choice
  prompt: She ___ on the auth service.
  options:
    - "work"
    - "works"
    - "working"
  correct: "works"
```

**Проверка:** case-insensitive точное сравнение `user_answer` с `correct`.

### 2. open

```yaml
- id: 2
  type: open
  prompt: Переведи: "Вчера я задеплоил хотфикс."
  correct_answer: "Yesterday I deployed the hotfix."
  acceptable_answers:
    - "I deployed the hotfix yesterday."
    - "Yesterday I shipped the hotfix."
```

**Проверка:** три уровня:
1. **Точное совпадение** после нормализации (lowercase, strip, схлопывание пробелов)
2. **Substring match** — ответ пользователя содержит правильный ИЛИ правильный содержит ответ
3. **acceptable_answers** — проверка по списку альтернатив (US/UK варианты, перестановки слов)

## Структура quiz YAML

```yaml
meta:
  name: present-simple
  display_name: Present Simple
  description: "Факты, регулярные действия, расписания..."
  level: B1
  estimated_min: 5

questions:
  - id: 1
    type: multiple_choice
    prompt: ...
    options: [...]
    correct: ...
    explanation: "..."
    grammar_point: "He/She/It + verb+s"

after_quiz:
  recap: "Present Simple используется для..."
  next_tense: "past-simple"
  recommended_review: "data/curriculum.yaml#week-2"
```

## Алгоритм проверки (run_quiz)

```python
def check_answer(question, user_answer):
    user_norm = _normalize(user_answer)
    
    if question.type == "multiple_choice":
        return user_norm == _normalize(question.correct)
    
    if question.type == "open":
        if not user_norm: return False
        correct_norm = _normalize(question.correct_answer)
        # Точное совпадение
        if user_norm == correct_norm: return True
        # Substring (любой порядок слов)
        if correct_norm in user_norm or user_norm in correct_norm: return True
        # Альтернативы
        for alt in question.acceptable_answers:
            alt_norm = _normalize(alt)
            if user_norm == alt_norm or alt_norm in user_norm or user_norm in alt_norm:
                return True
        return False
```

**`_normalize(s)`:**
```python
" ".join(str(s).lower().strip().split())
# "  I  DEPLOYED it  " → "i deployed it"
```

## Anti-cheat

**Substring match может быть слишком мягким** — но это by design:
- "yesterday I deployed the hotfix" vs правильное "I deployed the hotfix" → True (substring)
- Но "hotfix" vs правильное "I deployed the hotfix" → False (правильный не входит в user)

**Когда это плохо:**
- User пишет "hotfix" — получит False (substring не сработает)
- Это **намеренно** — требуем минимальный смысловой ответ

## Результат (run_quiz return)

```python
{
    "score": 8,              # из 10
    "total": 10,
    "per_question": [
        {
            "id": 1,
            "prompt": "...",
            "user_answer": "works",
            "correct": True,
            "correct_display": "works",
            "explanation": "He/She/It + verb+s",
            "grammar_point": "3rd person singular",
        },
        ...
    ],
    "recap": "...",
    "next_tense": "past-simple",
    "recommended_review": "..."
}
```

## Markdown rendering

**`render_quiz_markdown(quiz, with_answers=False)`:**
- `with_answers=False` — пустые чекбоксы `[ ]`, `[your answer here]`
- `with_answers=True` — `✅` рядом с правильным, `Правильный ответ: ...`

**`render_result_markdown(quiz, result)`:**
- Score + per-question feedback
- Эмодзи по порогам: 🎉 (≥90%), 👍 (≥70%), 💪 (≥50%), 📚 (<50%)
- Объяснения для **неправильных** ответов

## Идемпотентность

**`quiz --force`** — позволяет пройти заново, перезаписав score.
**Без `--force`** — если `quiz_scores[tense]` есть → "уже проходила: 8/10".

## Расширение (Phase 2)

1. **LLM-feedback** — после `quiz --check` опционально передать ответы в YandexGPT для развёрнутого фидбэка
2. **Adaptive quiz** — следующие вопросы зависят от ошибок
3. **Anki-export** — вопросы с `user_answer` сразу в формате Anki

## Связь

- [[progress-tracking]] — куда пишется score
- [[curriculum-design]] — какой quiz к какому уроку
