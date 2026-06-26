# curriculum-design.md — почему 12 недель и именно эти темы

## Принципы построения

### 1. Фокус на боли B1

Целевой пользователь — **B1 Intermediate**, IT/бизнес контекст. Главные боли по диагностике:

| Боль | Где проявляется | Когда решаем |
|---|---|---|
| **Present Perfect vs Past Simple** | "I have visited Paris" vs "I visited Paris" | Week 3-4 (главный блок!) |
| Артикли (a/the/-) | носители всё время поправляют | Week 1 (intro), дальше — reinforcement |
| Времена группы Continuous | "I'm working" vs "I work" | Week 5, 7 |
| Условные (1st vs 2nd) | "If I have time" vs "If I had time" | Week 9-10 |
| Passive Voice | письменная коммуникация (PRs, доки) | Week 11 |
| Reported Speech | пересказ чужих слов (meetings, ретро) | Week 12 |

### 2. 12 недель = 3 месяца

Это **оптимальный цикл мотивации**:
- Слишком короткий (4-6 недель) — ощущение "не успел"
- Слишком длинный (6 месяцев) — теряется momentum
- 12 недель = квартал, легко вписать в OKR/спринт

### 3. Блочная структура (6 блоков × 2 недели)

```
Block 1 (W1-2):  База          — Present Simple, Past Simple
Block 2 (W3-4):  B1-проблема   — Present Perfect vs Past Simple ⭐
Block 3 (W5-6):  События       — Continuous, Future
Block 4 (W7-8):  Сложное прошлое — Past Continuous, Past Perfect
Block 5 (W9-10): Условия       — 1st, 2nd Conditional
Block 6 (W11-12): Форма        — Passive Voice, Reported Speech
```

Каждый блок = **2 недели на тему**: первая — введение + практика, вторая — закрепление + quiz.

### 4. 7 дней в неделе, но ритм 5-6

```
День 1: intro / grammar (новый материал)
День 2: grammar (углубление)
День 3: listening (BBC/VOA)
День 4: grammar (нюансы)
День 5: dialog (speaking practice)
День 6: quiz (проверка)
День 7: review (закрепление)
```

6 продуктивных дней, 1 день отдыха. Streak трекает именно дни с активностью.

### 5. Принцип "input before output"

- **Дни 1-2** — reading/writing grammar (input)
- **Дни 3-4** — listening + comprehension (input)
- **День 5** — speaking (output через dialog)
- **День 6** — quiz (проверка всего)
- **День 7** — review + reflection

Этот ритм — обратный "Comprehensible Input" (Krashen), но с активной проверкой на день 6.

## Почему не 4 недели (минимальный English)?

- 4 недели → только Block 1-2 → **главная B1-проблема не решена полностью**
- 12 недель → все 6 блоков → B1 → B1+ с запасом

## Почему не 24 недели (полный B2)?

- 24 недели = 6 месяцев — слишком долго для самостоятельной мотивации
- Для полного B2 нужен **регулярный разговорный партнёр** (не скилл)
- Phase 2 скила может добавить speech recognition + AI feedback — это второй этап

## Адаптация под уровень

Если пользователь уже B1+ — пропускает Block 1-2 (Week 1-4):
```bash
python scripts/english.py week --week=5 --force
```

Если A2 — добавляется подготовительный модуль (Phase 2).

## Как измеряется прогресс

- **Quiz scores** — оценка грамматики (0-10 по каждой теме)
- **Streak** — ежедневная регулярность (главный predictor успеха)
- **Lessons done** — покрытие курикулума
- **Dialog completion** — speaking exposure

**Целевые метрики после 12 недель:**
- Quiz scores ≥ 8/10 на каждой теме
- Streak ≥ 50 дней
- 80% уроков done
- Способность прочитать IT-статью без частого обращения к словарю

## Связь с другими sub-skills

- [[progress-tracking]] — как ведётся streak и идемпотентность
- [[quiz-engine]] — детерминированная проверка quiz
- [[role-play-design]] — почему dialog именно 3-5 реплик
