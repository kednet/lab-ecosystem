---
name: english-listen
description: Аудирование — рекомендации BBC/VOA/IT-подкастов для недели
---

# english-listen — аудирование

Подбирает BBC/VOA/IT-подкасты для текущей/указанной недели. Печатает URL, transcript, vocab, comprehension questions.

## Использование

```bash
# Аудио для текущей недели
python scripts/english.py listen

# Конкретная неделя
python scripts/english.py listen --week=3
```

## Параметры

| Параметр | Описание |
|---|---|
| `--week=N` | Неделя (1-12), default = `current_week` |

## Что выводится

Для каждого источника:
- **Title** + source (BBC, VOA, CodeNewbie, ...)
- **URL** для прослушивания
- **Transcript URL** для чтения
- **Длительность** в минутах
- **Vocab** — 5-10 ключевых слов
- **Comprehension questions** с sample answers

## Источники (10 в `data/sources.yaml`)

- **BBC (4):** 6 Minute English, The English We Speak, Idioms about time
- **VOA (3):** Everyday Grammar, Health Report, Education Report
- **IT (3):** CodeNewbie, Soft Skills Engineering, Developer Voices

## Методика (3 прохода)

1. **Pass 1** — слушать без transcript, понять 60%+
2. **Pass 2** — с transcript, выписать незнакомые слова
3. **Pass 3** — ответить на comprehension questions **устно**

**Общее время:** ~20-25 мин на один source.

## Связанные команды

- [[english-lesson]] — listening часть урока
- [[english-glossary]] — поиск vocab из listening
