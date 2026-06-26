---
name: english-week
description: Управление неделей (show/next/jump)
---

# english-week — управление неделей

Показывает текущую неделю, переключает на следующую или прыгает на указанную.

## Использование

```bash
# Показать текущую неделю
python scripts/english.py week

# Показать конкретную неделю
python scripts/english.py week --week=5

# Переключиться на следующую (с проверкой что все 7 дней done)
python scripts/english.py week next

# Прыгнуть на указанную (force-jump, без проверок)
python scripts/english.py week --week=8 --force
```

## Параметры

| Параметр | Описание |
|---|---|
| `action` | `show` (default) или `next` |
| `--week=N` | Показать/прыгнуть на неделю N (1-12) |
| `--force` | Не спрашивать подтверждение при --week=N |

## Логика

**`week` (show):**
- Печатает: theme, grammar_focus, block, why
- Таблица всех 7 дней со статусом ✅/⏳

**`week next`:**
- Проверяет: все 7 дней текущей недели в `lessons_done`?
- Если да → переключает на `current_week + 1`
- Если нет → печатает список missing дней

**`week --week=N`:**
- Печатает неделю N
- Спрашивает "Переключиться?" (или `--force`)
- Без проверок (force-jump)

## Связанные команды

- [[english-lesson]] — урок внутри недели
- [[english-progress]] — streak и quiz scores
- [[english-reset]] — сбросить прогресс конкретной недели
