# Progress template — структура вывода `english.py progress`

```markdown
# 📊 Твой прогресс
===============

**Старт:** <started_at>
**Уровень:** <user_level>
**Цель:** <goal>
**Текущая позиция:** Week <W>, Day <D>
**Streak:** 🔥 <N> дней подряд
**Последняя активность:** <last_active_at>

---

## 📚 Уроки: <total_done> пройдено

| Неделя | Пройдено / Всего | % | Статус |
|---|---|---|---|
| 1 | 7/7 | 100% | ✅ готово |
| 2 | 4/7 | 57% | 🟡 в процессе |
| 3 | 0/7 | 0% | ⏳ |
| 4 | 0/7 | 0% | ⏳ |
| 5-12 | 0/7 | 0% | ⏳ |

## 📝 Quiz scores

| Tense | Score | % |
|---|---|---|
| `present-simple` | 9/10 | 90% |
| `past-simple` | 8/10 | 80% |
| `present-perfect` | 7/10 | 70% |

_Пока ни одного теста не пройдено..._

## 🎯 Следующие шаги
- Пройди сегодняшний урок: `python scripts/english.py lesson`
- Держи streak! 🔥 Осталось 3 дней до разблокировки Week 2.
- Можно переходить на следующую неделю: `week next`
- Пройди мини-тест: `quiz present-simple`

---

📂 Полный state: `state/progress.json`
📂 Логи уроков: `state/lessons/` (всего N файлов)
```

## Источники

- `state/progress.json` — основной
- `state/lessons/*.json` — по каждому уроку
- `data/curriculum.yaml` — для расчёта процентов

## Пример

См. `examples/progress-week-04.md`.
