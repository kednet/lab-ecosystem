# Changelog — English Trainer Skill

## v1.0 (2026-06-25) — Phase 1 (MVP)

**Первая рабочая версия. Детерминированное ядро без LLM/TTS. Работает офлайн.**

### Реализовано

- ✅ Структура папок (~73 файла, 13 директорий)
- ✅ **SKILL.md** — оркестратор с YAML-фронтматтер, таблица 9 команд, статусы state, Phase 1 vs Phase 2
- ✅ **README.md** — быстрый старт, 9 команд, что ожидать через 1/4/12 недель
- ✅ **data/curriculum.yaml** — 12-недельная программа × 7 дней = 84 урока (структурно, с полными темами/grammar_focus)
- ✅ **data/sources.yaml** — 10 аудио-источников (4 BBC + 3 VOA + 3 IT-подкаста) с vocab + comprehension questions
- ✅ **data/it_glossary.yaml** — 80 IT-фраз в 8 группах (main набор)
- ✅ **data/it_terms_xlsx.yaml** — 244 термина в 12 группах, импортировано из рабочего xlsx kfigh (2026-06-25)
- ✅ **data/tense-cheatsheet.yaml** — сводная таблица 12 времён
- ✅ **data/dialogs/*.yaml** — 12 ролевых диалогов (standup полный эталон, 11 схематичных)
- ✅ **data/quizzes/*.yaml** — 11 мини-тестов по временам (10 вопросов в каждом, 6 multiple_choice + 4 open)
- ✅ **scripts/_english_common.py** — load_env, paths, cp1252 fix, week_resolver
- ✅ **scripts/state.py** — идемпотентность: `state/progress.json` + `state/lessons/<w>_<d>_<type>.json`, streak-логика
- ✅ **scripts/quiz.py** — детерминированная проверка: multiple_choice точное совпадение, open — case-insensitive substring + `acceptable_answers`
- ✅ **scripts/english.py** — orchestrator с argparse (9 sub-команд), lazy imports
- ✅ **scripts/cmd_*.py** — 9 sub-команд: start, week, lesson, quiz, listen, dialog, glossary, progress, reset
- ✅ **glossary** — два набора (`--source=main|xlsx`), поиск (`--word=`), CSV-экспорт для Anki
- ✅ **templates/lesson.md** — формат урока дня (Grammar/Listening/Mini-tasks/Vocab)
- ✅ **templates/quiz.md** — формат мини-теста (вопросы + recap)
- ✅ **templates/listening.md** — формат рекомендаций аудио (3 эпизода + вопросы)
- ✅ **templates/dialog.md** — формат ролевого диалога (script + YOUR TURN + model_answer)
- ✅ **templates/progress.md** — формат статистики (week/day/streak/scores)
- ✅ **examples/lesson-week-03-day-1.md** — ПОЛНЫЙ эталон урока (Present Perfect vs Past Simple, ~350 строк)
- ✅ **examples/quiz-result-week-03.md** — пример пройденного теста (8/10)
- ✅ **examples/dialog-standup-example.md** — диалог с заполненными user-репликами
- ✅ **examples/progress-week-04.md** — статистика после 4 недель (streak 28)
- ✅ **references/tenses-12-table.md** — markdown-таблица 12 времён с примерами
- ✅ **references/irregular-verbs.md** — топ-50 неправильных глаголов
- ✅ **references/it-phonetics.md** — произношение IT-терминов (API, deploy, async, queue, …)
- ✅ **references/bbc-voa-links.md** — прямые ссылки на разделы BBC/VOA Learning English
- ✅ **commands/*.md** — 9 рецептов (по образцу video_skill/commands/)
- ✅ **sub-skills/*.md** — 6 деталей режимов (curriculum/progress/quiz/listening/role-play/glossary)
- ✅ Verification V1.1–V1.15 end-to-end

### Не реализовано (Phase 2, ~8-10 ч)

- ❌ LLM-фидбек на ответы пользователя (нужен `YANDEX_GPT_API_KEY` через `wish_librarian/agent/ai/factory.py`)
- ❌ TTS-озвучка эталонов диалогов и глоссария (нужен `YANDEX_SPEECHKIT_API_KEY` через `audio_skill/scripts/tts_yandex.py`)
- ❌ Авто-парсинг новых эпизодов BBC/VOA (нужен онлайн + PySocks/MITM bypass)
- ❌ Anki .apkg экспорт с привязкой к `state/progress.json:lessons_done` (сейчас работает CSV)
- ❌ Speech recognition для говорения (Azure Speech / Yandex STT)
- ❌ Адаптивный алгоритм (если quiz score < 7 → автодобавление урока по слабому времени)
- ❌ Полные тексты всех 12 диалогов (сейчас 1 полный + 11 схематичных)

### Известные особенности Phase 1

- Контент уроков (тексты грамматики, мини-задания) — частично схематичный в `curriculum.yaml`. Полные тексты — для Week 1, 3, 4 (ключевые для B1). Остальные недели — заголовки и темы, тексты добавляются в Phase 1.1.
- Идемпотентность по `--force` — отдельный флаг, без подтверждения для автоматизации.
- `streak_days` обновляется при вызове `lesson` или `quiz`. Если пропустить > 1 дня → сбрасывается в 1.
- `glossary --export=csv` создаёт UTF-8 BOM CSV (для Excel на Windows).

### Следующая версия

**v1.1 — Phase 1.1 (доводка контента, ~6-8 ч):**
- Полные тексты всех 12 диалогов (сейчас 1 эталон)
- Расширение глоссария с 80 до 120 фраз
- Полные тексты уроков для всех 12 недель (сейчас приоритет W1, W3-W4)
- Anki .apkg экспорт через `genanki`
- 3 дополнительных IT-подкаста в `sources.yaml`

**v1.2 — Phase 2 (LLM + TTS + онлайн, ~12-16 ч):**
- LLM-фидбек через `wish_librarian/agent/ai/factory.py`
- TTS-озвучка эталонов через `audio_skill/scripts/tts_yandex.py`
- Авто-парсинг новых эпизодов BBC/VOA
- Speech recognition

Требует: `YANDEX_GPT_API_KEY`, `YANDEX_SPEECHKIT_API_KEY`.
