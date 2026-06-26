# Пример: диалог standup с заполненными user-репликами

> **Команды:**
> ```bash
> # 1. Получить скрипт
> python scripts/english.py dialog standup
>
> # 2. После заполнения шаблона
> python scripts/english.py dialog standup --answer=tmp/dialog_answers/standup.yaml
> ```

---

# 🎭 Диалог: Daily Standup

**Категория:** team-rituals
**Сложность:** B1
**Длительность:** ~5 мин
_Standup — это daily routine в IT. Уверенность здесь = меньше стресса в команде._

---

## 🎬 Setting

- **Твоя роль:** Backend developer on a 5-person team
- **Команда:** Pulse Lab — fintech project, microservices architecture
- **Сценарий:** It's your turn to speak at standup. The team uses a "yesterday / today / blockers" format. Yesterday you finished the auth migration and pushed it to staging. Today you're planning to review Maria's PR and start on the new endpoint. You have one blocker: the design review for the new endpoint hasn't happened yet.
- **Место:** Zoom call, 9:30 AM

---

## 📜 Script

_Читай вслух. Где видишь **[YOUR TURN]** — остановись и произнеси свою реплику._

**🗣️ Собеседник:** Good morning, team! Who's next?

---

### ✍️ [YOUR TURN] — Step 1

💡 **Hint:** Good morning, everyone. Yesterday I <verb in Past Simple> the <task>.

**Твой ответ:** _Good morning everyone. Yesterday I finished the auth migration and pushed the first version to staging._

**Эталон:** _Good morning, everyone. Yesterday I finished the auth migration and pushed the first version to staging._

**Альтернативы:**
- _Morning, team. Yesterday I worked on the auth refactor._
- _Hi all. Yesterday I shipped the hotfix and started on the new endpoint._
- _Hey everyone. Yesterday I migrated the auth module to v3 and ran the smoke tests._

> **Self-review:** Твой ответ совпадает с эталоном. ✅ Произнеси вслух 2-3 раза для muscle memory.

---

**🗣️ Собеседник:** Great. What are you planning today?

---

### ✍️ [YOUR TURN] — Step 2

💡 **Hint:** Today I'm planning to <verb> the <task>.

**Твой ответ:** _Today I'm going to review Maria's PR and then dig into the new endpoint._

**Эталон:** _Today I'm planning to review Maria's PR and then dig into the new endpoint._

**Альтернативы:**
- _Today I'm going to review Maria's PR and then dig into the new endpoint._
- _Today I'll continue with the auth tests, and after that I'll pick up the new endpoint._

> **Self-review:** Отлично, использовал(а) "going to" вместо планирования в эталоне — обе формы правильные. ✅

---

**🗣️ Собеседник:** Sounds good. Any blockers?

---

### ✍️ [YOUR TURN] — Step 3

💡 **Hint:** I'm blocked on <dependency>. OR: No blockers from my side.

**Твой ответ:** _Yes, one blocker — I'm waiting on the design spec for the new endpoint. The design review hasn't happened yet._

**Эталон:** _Yes, one blocker: I'm waiting on the design spec for the new endpoint._

**Альтернативы:**
- _Yes, one blocker: I'm waiting on the design spec for the new endpoint._
- _No blockers from my side. I'm good to go._

> **Self-review:** Хорошо, что уточнил(а) детали блокера. В реальном standup так делать **не надо** — длинные обсуждения выноси в offline. Говори кратко: "Blocked on design review. Will follow up offline."

---

**🗣️ Собеседник:** Got it. Thanks for the update. Anyone have questions for Maria before she starts?

---

### ✍️ [YOUR TURN] — Step 4

💡 **Hint:** That's it from me. / Nope, that's it.

**Твой ответ:** _Nope, that's it. Thanks._

**Эталон:** _Nope, that's it. Thanks._

**Альтернативы:**
- _Nope, that's it. Thanks._
- _Nothing else from my side._

> **Self-review:** Идеально. ✅ Лаконично и по-деловому.

---

## 📚 Vocab из диалога

- **Good morning, everyone.**
- **Yesterday I finished / worked on / shipped ...**
- **Today I'm planning to / going to / I'll ...**
- **I'm blocked on ...**
- **No blockers from my side.**
- **That's it from me.**

## 🧠 Grammar notes

- **Past Simple:** 'Yesterday I finished...' (конкретное время — yesterday)
- **Future (going to / will):** 'Today I'm planning to...' / 'Today I'll...'
- **Present Continuous (action right now):** 'I'm blocked on...'

## ➡️ Следующий диалог

`python scripts/english.py dialog one-on-one`

---

📊 Заполнено: 4/4 [YOUR TURN] реплик

💡 **Методика:** этот диалог пройден 3 раза (при каждом запуске с другим контекстом):
1. **Раз** — прочитать + произнести эталон вслух
2. **Два** — придумать свой вариант, записать, сверить
3. **Три** — произнести свой вариант и эталон без подсказок

После 3 проходов — диалог "запоминается" в muscle memory и реальный standup будет естественным.
