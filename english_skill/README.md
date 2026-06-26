# English Trainer Skill v1.0 (Phase 1 MVP)

12-недельный тренажёр английского (B1 → B2 для IT/бизнеса). Аудирование + говорение + грамматика времён. **Без LLM, без TTS** — всё работает офлайн, без API-ключей.

## Что умеет (Phase 1)

- 🎓 **12-недельный курикулум** с фокусом на времена (Present Simple → Reported Speech)
- 🎧 **Аудирование** — каталог BBC/VOA/IT-подкастов с comprehension questions (только ссылки, без скачивания)
- 🗣 **Говорение через role-play** — 12 ситуаций (standup, 1:1, code review, …) с эталонами реплик
- 📝 **Мини-тесты по временам** — 10-вопросов с детерминированной автопроверкой
- 📚 **IT-глоссарий** — 80 must-know фраз + экспорт в CSV (Anki-friendly)
- 📊 **Прогресс-трекинг** — неделя/день/streak, идемпотентность уроков

## Быстрый старт

```bash
cd C:/Users/kfigh/english_skill
export PYTHONIOENCODING=utf-8   # ⚠️ обязательно на Windows 11 (cp1252)

# 1. Зарегистрироваться
python scripts/english.py start

# 2. Посмотреть текущую неделю
python scripts/english.py week

# 3. Урок дня (грамматика + 2 аудирования + мини-задания)
python scripts/english.py lesson

# 4. Мини-тест
python scripts/english.py quiz present-perfect-vs-past-simple

# 5. Аудио для недели
python scripts/english.py listen

# 6. Ролевой диалог
python scripts/english.py dialog standup

# 7. IT-глоссарий
python scripts/english.py glossary --topic=meetings

# 8. Прогресс
python scripts/english.py progress
```

## ⚠️ Важно для Windows 11

Без `PYTHONIOENCODING=utf-8` кириллица в выводе превращается в «кракозябры» (cp1252). Всегда ставьте env-переменную перед запуском.

## Структура

```
english_skill/
├── SKILL.md          # оркестратор (полная документация команд)
├── README.md         # этот файл
├── CHANGELOG.md      # что реализовано / нет
├── data/             # весь контент (curriculum, sources, glossary, dialogs, quizzes)
├── scripts/          # 13 Python-скриптов
├── templates/        # шаблоны вывода
├── commands/         # 9 рецептов для пользователя
├── sub-skills/       # детали режимов
├── examples/         # полные примеры
├── references/       # справочные материалы
├── state/            # runtime (progress.json + lessons/)
└── tmp/, logs/       # runtime
```

## Что будет в Phase 2

| Фича | Что нужно |
|---|---|
| LLM-фидбек на ответы | `YANDEX_GPT_API_KEY` |
| TTS-озвучка эталонов | `YANDEX_SPEECHKIT_API_KEY` (через `audio_skill`) |
| Anki .apkg экспорт | (без ключей) |
| Авто-парсинг новых эпизодов BBC/VOA | онлайн-режим (PySocks + MITM bypass) |
| Speech recognition | Azure Speech или Yandex STT |

## Первые 7 дней: что ожидать

| День | Тема | Время |
|---|---|---|
| 1 | Знакомство + Present Simple: правило | 20 мин |
| 2 | Present Simple: отрицания и вопросы | 25 мин |
| 3 | Standup-фразы (аудирование BBC) | 20 мин |
| 4 | Наречия частоты (always, usually…) | 20 мин |
| 5 | Dialog: standup | 15 мин |
| 6 | Mini-quiz: Present Simple | 10 мин |
| 7 | Review недели | 15 мин |

**После 1 недели:** понятен формат, 1 тест пройден, 1 диалог отработан, ~20 IT-фраз в глоссарии, streak 7 дней.

**После 4 недель:** Present Perfect vs Past Simple — главная B1-проблема структурно решена.

## Связи

- `C:/Users/kfigh/wish_librarian/` — фабрика LLM (Phase 2)
- `C:/Users/kfigh/audio_skill/` — TTS-озвучка (Phase 2)
- `C:/Users/kfigh/video_skill/` — референс архитектуры скилов
- `C:/Users/kfigh/excel_skill/` — референс минималистичного CLI-скила

## Планы

- `C:/Users/kfigh/.claude/plans/mighty-wobbling-moonbeam.md` — полный план v1.0
- Phase 1.1 (v1.1) — доводка контента: расширение глоссария до 120 фраз, полные тексты всех 12 диалогов, Anki .apkg
- Phase 2 (v1.2) — LLM + TTS + авто-парсинг + speech recognition
