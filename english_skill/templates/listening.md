# Listening template — структура вывода `english.py listen`

```markdown
# 🎧 Аудио для Week N
Найдено: <M> источник(ов)

### 1. <title>
**Источник:** <source> | **Длительность:** ~<min> мин | **Уровень:** <level>

🔗 **URL:** <url>
📄 **Transcript:** <transcript_url>

_<summary>_

**🎯 Vocab для этого эпизода:**
- **word1**
- **word2**
- **word3**

**❓ Comprehension questions (ответь устно или письменно):**
1. *<q1>*
   - 💡 Sample: _<sample_answer>_
2. *<q2>*
   - 💡 Sample: _<sample_answer>_

---

### 2. <next source>
...

---

## Итого
⏱ Общая длительность: ~<total> мин (~<X.Y> ч)

## Как заниматься
1. **Первое прослушивание** — слушай без субтитров, пойми общий смысл
2. **Второе прослушивание** — с transcript, выпиши незнакомые слова
3. **Comprehension questions** — ответь устно (это и есть speaking-практика!)
4. **Vocab** — добавь 3-5 новых слов в свой список
```

## Где берётся

- Фильтр по `data/sources.yaml: weeks: [N]`
- Если 0 источников → "Для недели N нет рекомендаций"
- Если много → все, с подсчётом общего времени
