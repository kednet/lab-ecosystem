# Quiz template — структура вывода `english.py quiz`

## Без --check (получить вопросы)

```markdown
# Mini-quiz: <display_name>
**Уровень:** <level> | **Время:** ~<min> мин | **Вопросов:** 10

_<description>_

---

## Как пройти
1. Прочитай вопросы ниже и подумай над ответами
2. Создай файл с ответами (шаблон сохранён ниже):
   📄 Шаблон: `tmp/quiz_answers/<tense>.yaml`
3. Заполни поле `answer` в шаблоне и запусти:
   `python scripts/english.py quiz <tense> --check=<path>`

---

## Вопрос 1
**<prompt>**
- [ ] option1
- [ ] option2
- [ ] option3
- [ ] option4

## Вопрос 2
**<prompt>**
_Напишите свой ответ:_
```
[your answer here]
```

## Вопрос 3
...
```

## С --check (результат)

```markdown
# Результат: <display_name>
## 🎉 Score: 8/10 (80%)

_Отлично! Ты уверенно владеешь этим временем._

---

## Per-question feedback

### ✅ Вопрос 1
**<prompt>**
- Твой ответ: `<user_answer>`
- 💡 <explanation>

### ❌ Вопрос 2
**<prompt>**
- Твой ответ: `<user_answer>`
- Правильный ответ: `<correct_display>`
- 💡 <explanation>

### ✅ Вопрос 3
...
```

## Эмодзи по порогам

| Score | Эмодзи | Текст |
|---|---|---|
| ≥ 90% | 🎉 | Идеально! Время идти дальше. |
| ≥ 70% | 👍 | Отлично! Ты уверенно владеешь этим временем. |
| ≥ 50% | 💪 | Хорошо, но есть куда расти. Перечитай explanation. |
| < 50% | 📚 | Нужно повторить. Открой урок и пройди тест снова. |

## Пример

См. `examples/quiz-result-week-03.md`.
