# Dialog template — структура вывода `english.py dialog`

## Без --answer (получить скрипт)

```markdown
# 🎭 Диалог: <display_name>

**Категория:** <category>
**Сложность:** <level>
**Длительность:** ~<min> мин
_<why>_

---

## 🎬 Setting

- **Твоя роль:** <context.role>
- **Команда:** <context.team>
- **Сценарий:** <context.scenario>
- **Место:** <context.place>

---

## 📜 Script
_Читай вслух. Где видишь **[YOUR TURN]** — остановись и произнеси свою реплику._

**🗣️ Собеседник:** <line>

---

### ✍️ [YOUR TURN] — Step 1
💡 **Hint:** <hint>

**Что сказать:** _<model_answer>_

**Или так:**
- _<alternative1>_
- _<alternative2>_

---

**🗣️ Собеседник:** <line>

### ✍️ [YOUR TURN] — Step 2
💡 **Hint:** <hint>
**Что сказать:** _<model_answer>_
...

---

## 📚 Vocab из диалога
- **phrase1**
- **phrase2**
- **phrase3**

## 🧠 Grammar notes
- <note1>
- <note2>

## ➡️ Следующий диалог
`python scripts/english.py dialog <next>`

---

## 📝 Как записать свои ответы
1. Произнеси вслух каждую [YOUR TURN] реплику 2-3 раза
2. Создай файл с вариантами (шаблон ниже):
   📄 Шаблон: `tmp/dialog_answers/<name>.yaml`
3. Заполни `answer` для каждой реплики и запусти:
   `python scripts/english.py dialog <name> --answer=<path>`

💡 **Совет:** произноси вслух, даже если не записываешь. Цель — speaking muscle memory.
```

## С --answer (diff с эталоном)

Та же структура, но в [YOUR TURN] секциях:

```markdown
### ✍️ [YOUR TURN] — Step 1
💡 **Hint:** <hint>

**Твой ответ:** _<user_answer>_

**Эталон:** _<model_answer>_

**Альтернативы:**
- _<alt1>_
- _<alt2>_

---

📊 Заполнено: <N>/<M> [YOUR TURN] реплик
```

## Пример

См. `examples/dialog-standup-example.md`.
