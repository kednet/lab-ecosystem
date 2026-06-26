# role-play-design.md — структура ролевых диалогов

## Зачем role-play

**Главная боль kfigh:** "писать не могу по английски вообще, мне нужно больше понимать и говорить".

Role-play решает **speaking** через:
1. **Чтение вслух** эталонных реплик (произношение, интонация)
2. **Генерация своих вариантов** — пользователь заполняет `[YOUR TURN]` своими словами
3. **Diff с эталоном** — после `--answer=file.yaml` видит свой вариант рядом с эталоном
4. **Альтернативы** — 2-3 варианта формулировки для одной и той же мысли

## 12 диалогов × 4 категории

### team-rituals (3)

- **standup** — daily meeting (yesterday/today/blockers)
- **retro** — что прошло хорошо / плохо / action items
- **one-on-one** — 1-на-1 с менеджером

### ceremonies (3)

- **estimate** — планирование спринта
- **demo** — показ фичи стейкхолдерам
- **onboarding** — первый день в команде

### customer (3)

- **customer-chat** — ответ пользователю в чате
- **negotiation** — обсуждение scope с клиентом
- **incident** — коммуникация во время продакшн-инцидента

### conflict (3)

- **code-review** — тактичный push-back на PR
- **blocker** — эскалация блокера вверх
- **push-back** — несогласие с решением менеджера

## Структура dialog YAML

```yaml
meta:
  name: standup
  display_name: Daily Standup
  category: team-rituals
  level: B1
  estimated_min: 5
  grammar_focus: "past-simple, going-to, present-continuous"
  why: "Standup — это daily routine в IT. Уверенность здесь = меньше стресса в команде."

context:
  role: "Backend developer on a 5-person team"
  team: "Pulse Lab — fintech project, microservices architecture"
  scenario: "It's your turn to speak at standup..."
  place: "Zoom call, 9:30 AM"

script:
  - id: 1
    speaker: facilitator
    line: "Good morning, team! Who's next?"

  - id: 2
    speaker: user
    line: "[YOUR TURN]"
    hint: "Good morning, everyone. Yesterday I <verb in Past Simple> the <task>."
    model_answer: "Good morning, everyone. Yesterday I finished the auth migration."
    alternatives:
      - "Morning, team. Yesterday I worked on the auth refactor."
      - "Hi all. Yesterday I shipped the hotfix."

  - id: 3
    speaker: facilitator
    line: "Great. What are you planning today?"

  - id: 4
    speaker: user
    line: "[YOUR TURN]"
    hint: "Today I'm planning to <verb> the <task>."
    model_answer: "Today I'm planning to review Maria's PR and start the new endpoint."
    alternatives:
      - "Today I'll continue with the auth tests, then pick up the new endpoint."

  # ... 4-6 реплик всего

after_dialog:
  recap_vocab:
    - "Good morning, everyone."
    - "Yesterday I finished / worked on / shipped ..."
    - "Today I'm planning to / going to / I'll ..."
    - "I'm blocked on ..."
    - "No blockers from my side."
    - "That's it from me."
  grammar_notes:
    - "Past Simple: 'Yesterday I finished...' (конкретное время)"
    - "Future (going to / will): 'Today I'm planning to...' / 'Today I'll...'"
    - "Present Continuous: 'I'm blocked on...'"
  next_dialog: one-on-one
```

## Методика прохождения

**Без `--answer`:**
1. Прочитать Setting (контекст) — понять роль
2. Произнести каждую реплику **facilitator** вслух
3. На `[YOUR TURN]` остановиться и **произнести** свой вариант (2-3 попытки)
4. Прочитать эталон + альтернативы
5. Заполнить YAML-шаблон своими вариантами

**С `--answer`:**
1. Заполнить `tmp/dialog_answers/<name>.yaml` своими вариантами
2. Запустить `python scripts/english.py dialog <name> --answer=...`
3. Получить diff: свой вариант / эталон / альтернативы
4. **Произнести вслух** свой вариант и эталон — закрепить в muscle memory

**Общее время:** 5-10 мин на диалог.

## Почему 3-5 user-реплик (не больше)

- **Меньше 3** — слишком мало exposure
- **Больше 5** — теряется фокус, пользователь устаёт
- **3-5** — оптимальный micro-sprint: одно задание → quick win

## Почему facilitator — на английском

- **Погружение** — пользователь слышит authentic English
- **Интонация** — facilitator реплики задают ритм
- **Контекст** — встречается с реальной речью, не с учебной

## Альтернативы (variety)

**Зачем 2-3 alternatives на каждую реплику:**

| Альтернатива | Что тренирует |
|---|---|
| Формальная vs неформальная | "Good morning" vs "Morning" |
| Active vs passive | "I'll review" vs "The review will be done by me" |
| Past Simple vs Present Perfect | "I shipped" vs "I have shipped" |
| Short vs detailed | "Yes" vs "Yes, I finished the migration" |

**Это и есть реальный English** — одну мысль можно выразить 5 способами. Учить **выбирать**, а не заучивать одну формулу.

## Связь с уроками

Каждый урок дня 5 в curriculum ссылается на конкретный dialog:
```yaml
- day: 5
  type: dialog
  dialog: standup
```

После прохождения dialog → `state/lessons/<w>_<d>_dialog.json` → идемпотентность.

## Phase 2

- **TTS** — facilitator реплики озвучены Yandex SpeechKit (привязка к audio_skill)
- **STT** — user произносит вслух, speech recognition проверяет близость к эталону
- **AI feedback** — LLM даёт комментарии по user-варианту

## Связь

- [[curriculum-design]] — где dialog стоит в 7-дневном ритме (день 5)
- [[listening-mode]] — listening день 3 тоже работает с transcripts
