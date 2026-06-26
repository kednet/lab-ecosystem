---
name: english-dialog
description: Ролевой диалог для speaking practice
---

# english-dialog — ролевой диалог

12 IT-диалогов (standup, code-review, demo, ...) для speaking-практики. Читайте facilitator вслух, на [YOUR TURN] — произнесите свой вариант.

## Использование

```bash
# Standup диалог
python scripts/english.py dialog standup

# Все 12:
#   standup, one-on-one, code-review, customer-chat, blocker,
#   estimate, push-back, demo, retro, onboarding,
#   incident, negotiation

# С самопроверкой (сравнить свои ответы с эталоном)
python scripts/english.py dialog standup --answer=tmp/dialog_answers/standup.yaml
```

## Параметры

| Параметр | Описание |
|---|---|
| `name` | Slug диалога |
| `--answer=FILE` | YAML с user-репликами (заполняется вручную) |

## Workflow

### 1. Получить скрипт (без --answer)

```
🎭 standup
=========

# 🎭 Диалог: Daily Standup

**Твоя роль:** Backend developer on a 5-person team
**Команда:** Pulse Lab — fintech project
**Сценарий:** It's your turn to speak at standup...

## 📜 Script

**🗣️ Собеседник:** Good morning, team! Who's next?

---

### ✍️ [YOUR TURN] — Step 2
💡 **Hint:** Good morning, everyone. Yesterday I <verb in Past Simple> the <task>.
**Что сказать:** _Good morning, everyone. Yesterday I finished the auth migration._
**Или так:**
- _Morning, team. Yesterday I worked on the auth refactor._
- _Hi all. Yesterday I shipped the hotfix._
```

### 2. Произнести вслух

- 🗣️ facilitator реплики — прочитать с интонацией
- ✍️ [YOUR TURN] — остановиться, придумать свой вариант (2-3 попытки)
- Прочитать эталон + альтернативы

### 3. Создать файл с ответами

Заполнить `tmp/dialog_answers/<name>.yaml`:
```yaml
'# Заполни поле ''answer'' для каждой [YOUR TURN] реплики': null
'1':
  hint: Good morning, everyone...
  answer: Good morning everyone. Yesterday I shipped the auth migration.
'2':
  hint: Today I'm planning to...
  answer: Today I'll review Maria's PR.
```

### 4. Самопроверка (с --answer)

Получить diff: свой вариант / эталон / альтернативы — для каждой user-реплики.

## 12 диалогов × 4 категории

- **team-rituals:** standup, retro, one-on-one
- **ceremonies:** estimate, demo, onboarding
- **customer:** customer-chat, negotiation, incident
- **conflict:** code-review, blocker, push-back

## Идемпотентность

Dialog не имеет отдельного state — идемпотентность через `lesson` (день 5 = dialog).

## Связанные команды

- [[english-lesson]] — день 5 = dialog
- [[english-quiz]] — после dialog
- [[english-glossary]] — vocab из dialog
