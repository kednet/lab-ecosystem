# Lesson template — структура вывода `english.py lesson`

## Frontmatter (всегда)

```markdown
# Week N | Day M: <title>

**Тема недели:** <week.theme>
**Тип урока:** <day.type>
**Грамматика:** <day.grammar_focus>
**Топик:** <day.grammar_topic>   (если есть)

---
```

## Body (если есть `content` в curriculum.yaml)

```markdown
<day.content — многострочный markdown, может содержать таблицы/списки/код>

---
```

## Listening (если есть `listening: [id, id, ...]`)

```markdown
## 🎧 Аудирование

### <source.title>
_(<source.source>, ~<duration> мин)_
🔗 <source.url>
📄 Transcript: <source.transcript_url>

**Vocab:** word1, word2, word3, ...

**Comprehension questions:**
1. *<q1>*
   - Sample: _<sample_answer>_
2. *<q2>*
   - Sample: _<sample_answer>_

---

### <next source>
...
```

## Mini-tasks (если есть `task`)

```markdown
## ✏️ Мини-задания

<day.task — многострочный markdown>

---
```

## Dialog (если есть `dialog: <slug>`)

```markdown
## 🎭 Ролевой диалог

Открой: `python scripts/english.py dialog <day.dialog>`

---
```

## Quiz (если есть `quiz: <tense>`)

```markdown
## 📝 Мини-тест

Пройди: `python scripts/english.py quiz <day.quiz>`

---
```

## Vocab дня (если есть `vocab: [...]`)

```markdown
## 📚 Vocab дня

- **word1**
- **word2**
- **word3**
...
```

## Footer (всегда)

```markdown
---

✅ Урок Week N Day M (<type>) пройден!
📅 Прогресс сохранён в state/lessons/<N>_<M>_<type>.json
🔥 Текущий streak: <N> дней

Следующий шаг: `python scripts/english.py lesson --day=<M+1>`
```

## Полный пример

См. `examples/lesson-week-03-day-1.md`.
