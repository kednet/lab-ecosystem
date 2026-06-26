---
name: English
description: 12-недельный тренажёр английского для IT/бизнеса (B1 → B2). Аудирование + говорение + грамматика времён. Phase 1 (MVP) — детерминированное ядро без LLM/TTS.
allowed-tools: [Read, Write, Bash, Glob, Grep]
---

# Skill v1.0 (Phase 1 MVP) — English Trainer

Ты — **оркестратор тренажёра английского** для kfigh. Ведёшь её по 12-недельному курикулуму: показываешь урок дня, гоняешь мини-тесты по временам, рекомендуешь аудио из каталога, проигрываешь role-play диалоги, ведёшь IT-глоссарий.

**Phase 1 (MVP, реализовано):** детерминированное ядро — весь контент в YAML/MD, прогресс в `state/progress.json`, без LLM и TTS. Работает офлайн, без API-ключей.

**Phase 2 (stub):** LLM-фидбек на ответы, TTS-озвучка эталонов, Anki .apkg экспорт, авто-парсинг BBC/VOA, speech recognition.

## 📋 КОМАНДЫ

| Маршрут | Команда | Что делает | Phase |
|---|---|---|---|
| `/english start` | `python scripts/english.py start` | Зарегистрировать прогресс (создать state/progress.json) | **1 ✅** |
| `/english week` | `python scripts/english.py week [show\|next\|--week=N]` | Показать / переключить текущую неделю | **1 ✅** |
| `/english lesson` | `python scripts/english.py lesson [--day=N]` | Урок дня: грамматика + 2 аудирования + мини-задания | **1 ✅** |
| `/english quiz` | `python scripts/english.py quiz <tense> [--check=answers.yaml]` | Мини-тест по указанному времени | **1 ✅** |
| `/english listen` | `python scripts/english.py listen [--week=N]` | 3 рекомендованных аудио для недели + comprehension questions | **1 ✅** |
| `/english dialog` | `python scripts/english.py dialog <name>` | Ролевой диалог (12 сценариев) | **1 ✅** |
| `/english glossary` | `python scripts/english.py glossary [--topic=X] [--export=csv] [--source=main\|xlsx] [--word=W]` | IT-глоссарий: main (80 фраз) + xlsx (244 термина), поиск, Anki-CSV | **1 ✅** |
| `/english progress` | `python scripts/english.py progress` | Статистика: неделя, streak, пройденные уроки | **1 ✅** |
| `/english reset` | `python scripts/english.py reset [--week=N\|--all] [--force]` | Сброс прогресса (с подтверждением или --force) | **1 ✅** |

## 🧠 ОБЩИЕ КОНВЕНЦИИ

- **Идемпотентность уроков:** `state/lessons/<week>_<day>_<type>.json` со `status="done"` означает «урок пройден». Повторный запуск без `--force` → «уже пройдено, используйте --force».
- **Streak:** считается по дням в `state/progress.json`, обнуляется при пропуске > 1 дня.
- **20-25 мин/день:** `lesson` выводит markdown на ~15 мин чтения, `quiz` добавляет ~5 мин, `listen` опционально.
- **cp1252 fix:** все скрипты начинают с `sys.stdout.reconfigure(encoding='utf-8')` (Windows 11).
- **Кодировка запуска:** `PYTHONIOENCODING=utf-8 python ...` (на Windows 11 обязательно для кириллицы).

## 🚦 СТАТУСЫ

### state/progress.json

```json
{
  "started_at": "2026-06-25T10:00:00Z",
  "user_level": "B1",
  "goal": "IT/business English",
  "current_week": 3,
  "current_day": 4,
  "streak_days": 12,
  "lessons_done": ["w1d1-intro", "w1d2-grammar", "w3d3-quiz"],
  "quiz_scores": {"present-simple": 9, "past-simple": 8, "present-perfect": 7},
  "last_active_at": "2026-06-28T19:30:00Z"
}
```

### state/lessons/<week>_<day>_<type>.json

```json
{
  "week": 3,
  "day": 4,
  "type": "grammar",
  "status": "pending|done|skipped",
  "started_at": "2026-06-25T10:00:00Z",
  "done_at": "2026-06-25T10:20:00Z"
}
```

## 📂 ГДЕ ЧТО

```
english_skill/
├── SKILL.md (этот файл)              # оркестратор
├── README.md                          # быстрый старт
├── CHANGELOG.md                       # v1.0
├── .env.example                       # пустой в Phase 1
│
├── commands/                          # рецепты (9 файлов)
├── sub-skills/                        # детали режимов (6 файлов)
├── data/                              # весь контент
│   ├── curriculum.yaml                # 12 недель × 7 дней
│   ├── sources.yaml                   # 10 аудио (BBC + VOA + IT)
│   ├── it_glossary.yaml               # 80 IT-фраз в 8 группах (main)
│   ├── it_terms_xlsx.yaml             # 244 термина из рабочего xlsx (12 групп)
│   ├── tense-cheatsheet.yaml          # сводная таблица 12 времён
│   ├── dialogs/                       # 12 ролевых диалогов
│   └── quizzes/                       # 10 мини-тестов
├── scripts/                           # Python (13 файлов)
├── templates/                         # 5 шаблонов
├── examples/                          # 4 примера
├── references/                        # 4 справочника
├── state/                             # runtime
│   ├── progress.json
│   └── lessons/                       # <w>_<d>_<type>.json
├── tmp/                               # рабочие файлы
└── logs/
```

## 🚧 ИЗВЕСТНЫЕ ОГРАНИЧЕНИЯ (MVP v1.0)

- ❌ LLM-фидбек на ответы — Phase 2
- ❌ TTS-озвучка эталонов — Phase 2 (пока пользователь читает вслух сам)
- ❌ Скачивание новых эпизодов BBC/VOA — Phase 2 (только ссылки + ручная работа)
- ❌ Speech recognition — Phase 2
- ❌ Anki .apkg экспорт — Phase 2 (но `glossary --export=csv` уже работает)
- ❌ Адаптивный алгоритм (если quiz score < 7 → автодобавление урока) — Phase 2

## 📚 12-НЕДЕЛЬНАЯ ПРОГРАММА (краткий обзор)

| Недели | Фокус | Почему |
|---|---|---|
| **1-2** | Present Simple + Past Simple | База делового английского |
| **3-4** | **Present Perfect vs Past Simple** | Главная B1-проблема (жизненный опыт vs история) |
| **5-6** | Present Continuous + Future (will / going to) | Текущие задачи и планы |
| **7-8** | Past Continuous + Past Perfect | Контекст в прошлом |
| **9-10** | Conditionals (1st + 2nd) | Деловые допущения и планы |
| **11-12** | Passive Voice + Reported Speech (базовое) | Чтение IT-документации |

## 🔗 СВЯЗИ

**Phase 1:** изолирован. Самодостаточен.

**Phase 2 (план):**
- `wish_librarian/agent/ai/factory.py` — LLM-фидбек
- `audio_skill/scripts/tts_yandex.py` — TTS-озвучка эталонов
- `C:/Users/kfigh/wish_librarian` — общая LLM-фабрика

## Следующая версия

**v1.1 — Phase 1.1 (доводка контента):**
- ✅ Расширение IT-глоссария: 80 → 324 фраз (xlsx импорт 2026-06-25)
- Все 12 диалогов с полными текстами (сейчас 4 полных, 8 схематичных)
- Anki .apkg экспорт

**v1.2 — Phase 2 (LLM + TTS):**
- LLM-фидбек через wish_librarian factory
- TTS-озвучка эталонов диалогов
- Авто-парсинг новых эпизодов BBC/VOA
- Speech recognition для говорения

Требует: `YANDEX_GPT_API_KEY`, `YANDEX_SPEECHKIT_API_KEY`.
