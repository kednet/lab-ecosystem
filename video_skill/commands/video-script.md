# /video script <platform> <goal> <tone> <duration> <source> [--profile=X]

Сгенерировать сценарий короткого видео для указанного профиля (по умолчанию `lab`).

## Команда

```bash
python scripts/video.py script <platform> <goal> <tone> <duration> <source> [опции]
```

## Позиционные аргументы

| # | Имя | Обязателен | Значения | Описание |
|---|---|---|---|---|
| 1 | `platform` | ✅ | tiktok \| youtube \| vk \| telegram \| reels | Целевая платформа |
| 2 | `goal` | ✅ | engagement \| traffic \| lead \| education \| viral | Цель ролика |
| 3 | `tone` | ✅ | soulful \| bold \| inspiring \| educational \| playful \| calm \| confident \| tender \| energetic \| reflective | Тон голоса |
| 4 | `duration` | ✅ | 15 \| 30 \| 45 \| 60 \| 90 | Длительность в секундах |
| 5 | `source` | ✅ | свободный текст | Тема/идея/заголовок |

## Опции

| Флаг | Default | Описание |
|---|---|---|
| `--profile=X` | `lab` (или `$PROFILE_DEFAULT`) | Профиль: `lab`/`wl`/`coach`/`experts`/`market` |
| `--voice=X` | из профиля | Переопределить голос (alena/filipp/ermil/...) |
| `--speed=X` | из профиля | Переопределить скорость речи (0.8–1.2) |
| `--music-mood=X` | из профиля | Переопределить настроение BGM (uplifting/calm/...) |
| `--cta=X` | из профиля | Переопределить CTA-фразу |
| `--out=path` | `tmp/scripts/<profile>/<slug>.md` | Куда сохранить |
| `--dry-run` | false | Показать промпт, не вызывать LLM, не сохранять файлы |
| `--force` | false | Перезаписать существующий сценарий |

## Алгоритм

1. Загрузить профиль из `data/profiles/<name>.yaml`
2. **Idempotency check**: если `state/<profile>/<slug>.json` существует со `status="script_ready"` и не передан `--force` → «уже есть сценарий»
3. **resolve_params()**: CLI-флаги > profile.defaults > profile.cta_profiles[tone][0] > profile.branding.cta_default
4. **build_prompt()**: собрать system + user с контекстом профиля
5. **LLM-вызов** через `llm_factory.generate_script_json()` или stub
6. **render_markdown()**: JSON → markdown с frontmatter + таблица шотов
7. Сохранить `tmp/scripts/<profile>/<slug>.md` + обновить `state/<profile>/<slug>.json`

## Примеры

```bash
# Полный прогон для lab
python scripts/video.py script reels engagement soulful 30 "5 ошибок карты желаний" --profile=lab

# Dry-run (посмотреть промпт)
python scripts/video.py script reels engagement soulful 30 "проверка" --dry-run --profile=lab

# Другая платформа
python scripts/video.py script tiktok traffic bold 15 "Конкурс желаний" --profile=market

# С переопределением голоса
python scripts/video.py script reels engagement soulful 30 "тема" --voice=filipp --profile=lab

# Force — перезаписать
python scripts/video.py script reels engagement soulful 30 "та же тема" --force --profile=lab
```

## Что на выходе

- `tmp/scripts/<profile>/<slug>.md` — markdown со сценарием (frontmatter-JSON + шоты + CTA)
- `state/<profile>/<slug>.json` — `status="script_ready"`, `script_path`, `script_at`

## Связано с

- `sub-skills/script-mode.md` — детали C-режима
- `sub-skills/profile-system.md` — override-матрица
- `prompts/script-generate.md` — LLM-промпт
- `prompts/profile-context.md` — инъекция профиля
- `templates/script-<platform>.md` — markdown-шаблон
