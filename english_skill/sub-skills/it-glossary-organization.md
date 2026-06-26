# it-glossary-organization.md — как организован IT-глоссарий

## Два набора

В `english_skill` есть **два независимых глоссария**, доступных через единый CLI:

| Набор | Файл | Фраз | Групп | Когда использовать |
|---|---|---|---|---|
| **main** | `data/it_glossary.yaml` | 80 | 8 | Must-know фразы по 8 темам |
| **xlsx** | `data/it_terms_xlsx.yaml` | 244 | 12 | Полный словарь из рабочего xlsx kfigh |

## main набор (80 фраз)

### Структура

**8 тематических групп:**

| Группа | Фраз | Фокус |
|---|---|---|
| `meetings` | 10 | Sync up, take it offline, circle back, parking lot |
| `code-review` | 10 | Push back, loop in, ship, cut a release, roll back |
| `standup` | 10 | Worked on / planning to / blocked on / no blockers |
| `delivery` | 10 | Ship, deploy, roll out, roll back, hotfix |
| `incidents` | 10 | Investigating, root cause, regression, post-mortem |
| `negotiation` | 10 | Push back, deadline, scope creep, MVP |
| `onboarding` | 10 | First week, ramp up, mentor, buddy |
| `retrospectives` | 10 | What went well, what didn't, action items |

**Каждая фраза имеет:**
- `phrase` — английский текст
- `translation_ru` — русский перевод
- `example_en` — пример на английском
- `example_ru` — перевод примера
- `tags` — категории для фильтрации

### Пример записи

```yaml
- phrase: "Let's sync up on this."
  translation_ru: "Давай синхронизируемся по этому."
  example_en: "I think we need to sync up on the deployment plan before tomorrow."
  example_ru: "Думаю, надо синхронизироваться по плану деплоя до завтра."
  tags: ["meeting", "collaboration"]
```

## xlsx набор (244 термина)

### Источник

`C:\Users\kfigh\Downloads\Списание недостач по Амазон_05.2026 для переоценки.xlsx`

Это рабочий словарь kfigh — 251 строка (en→ru). После импорта:
- 244 уникальных термина (некоторые дубли объединены)
- Автоматическая категоризация по 12 группам

### 12 групп по частотности

| Группа | Терминов | Примеры |
|---|---|---|
| `core_dev` | 180 | software, hardware, develop, compile, debug |
| `data_structures` | 26 | class, object, method, array, dict |
| `security` | 9 | auth, token, encrypt, hash, key |
| `databases` | 8 | SQL, query, table, index, schema |
| `architecture` | 4 | pattern, microservice, monolith, layer |
| `principles` | 4 | DRY, KISS, YAGNI, SOLID |
| `git_files` | 3 | commit, branch, repository, merge |
| `ui_frontend` | 3 | UI, design, layout, responsive |
| `web_network` | 3 | HTTP, API, REST, JSON |
| `testing` | 2 | debug, regression, smoke |
| `errors` | 1 | exception |
| `devops_cloud` | 1 | deployment |

**Примечание:** в `core_dev` попали 180 терминов — это **базовая лексика**, не категоризированная по домену. Это именно та лексика, которую нужно учить **первой** (глаголы, наречия, общие IT-слова).

## CLI использование

### Просмотр

```bash
# Main (default)
python scripts/english.py glossary
python scripts/english.py glossary --topic=meetings

# xlsx
python scripts/english.py glossary --source=xlsx
python scripts/english.py glossary --source=xlsx --topic=core_dev
```

### Поиск одного слова

```bash
# Ищет во всех наборах (main + xlsx)
python scripts/english.py glossary --word=deploy
python scripts/english.py glossary --word=auth
```

**Возвращает:**
- Все совпадения (EN или RU подстрока)
- Группа + source
- Пример (если есть)

### CSV экспорт (для Anki)

```bash
# Весь main
python scripts/english.py glossary --export=csv

# Только meetings
python scripts/english.py glossary --topic=meetings --export=csv

# Весь xlsx
python scripts/english.py glossary --source=xlsx --export=csv

# Только security из xlsx
python scripts/english.py glossary --source=xlsx --topic=security --export=csv
```

**Файлы:**
- `tmp/glossary_export/glossary_main_<topic>.csv`
- `tmp/glossary_export/glossary_xlsx_<topic>.csv`

**Импорт в Anki:**
1. File → Import
2. Field 1 = phrase
3. Field 2 = translation_ru
4. Field 3 = example_en
5. Field 4 = example_ru
6. Field 5 = tags

## Как учить

### Рекомендуемый порядок (B1)

**Неделя 1-2: main + core_dev (must-know)**
- `glossary --source=main --topic=meetings` (10 фраз)
- `glossary --source=main --topic=standup` (10 фраз)
- `glossary --source=main --topic=code-review` (10 фраз)
- `glossary --source=xlsx --topic=core_dev` (180 — по 15 в день = 12 дней)

**Неделя 3-4: тематические группы xlsx**
- `principles` (DRY, KISS, YAGNI, SOLID)
- `security` (auth, encrypt, token)
- `databases` (SQL, query, schema)

**Неделя 5+: всё остальное**
- `architecture`, `data_structures`, `web_network`, и т.д.

### Anki-режим (если есть время)

1. `glossary --source=xlsx --export=csv`
2. Импортировать в Anki
3. По 20 новых карточек в день (default Anki pace)
4. За 12-14 дней все 244 пройдут initial learning

## Phase 2

- **Quiz для glossary** — генерация вопросов из glossary (en→ru, ru→en)
- **Spaced repetition** — свой движок или экспорт в Anki
- **Audio** — TTS для каждой фразы
- **Context examples** — автогенерация через LLM

## Связь

- [[curriculum-design]] — где glossary встречается в уроках
- [[listening-mode]] — vocab из listening vs glossary
