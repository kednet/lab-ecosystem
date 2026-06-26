# C-режим (script-only) — Video Creator Skill v1.0

## Что это
Phase 1 реализует **только C-режим** (генерация сценариев через LLM). Это 80% ценности — скил сразу полезен для команды kfigh, не дожидаясь Phase 2 (A-режим, mp4) и Phase 3 (B-режим, нарезка).

## Использование

```bash
# Полный цикл
python scripts/video.py script <platform> <goal> <tone> <duration> <source> \
    [--profile=lab] [--voice=filipp] [--cta="..."] [--from-file=path] \
    [--dry-run] [--force]

# Dry-run
python scripts/video.py script reels engagement soulful 30 "5 ошибок карты желаний" \
    --profile=lab --dry-run

# Из своего текста
python scripts/video.py script tiktok engagement inspiring 30 "промо новой книги" \
    --profile=wl --from-file=tmp/notes/quote.md

# Без профиля
python scripts/video.py script tiktok engagement bold 15 "проверка"
```

## Алгоритм

См. `scripts/cmd_script.py:run()`:

1. **resolve_params** — собрать финальные параметры по override-матрице
   - Обязательные: platform, tone, goal, duration (иначе ValueError)
   - voice: CLI → profile.defaults
   - CTA: CLI → profile.cta_profiles[tone][0] → profile.branding.cta_default
   - watermark: только из profile (нет CLI-флага в Phase 1)

2. **Slug** — `slugify(source, max_length=80)` — RU→EN транслитерация

3. **Идемпотентность** — `state/<profile>/<slug>.json`:
   - Если `status == script_ready` и не `--force` → skip
   - Иначе — генерируем

4. **build_prompt** — собрать system + user промпт
   - System: схема JSON, правила
   - User: параметры + контекст профиля (из `data/profiles/<name>.yaml`)

5. **LLM-вызов** через `llm_factory.generate_script_json()`:
   - Lazy import `wish_librarian.agent.ai.factory.get_ai_client`
   - Парсит text→dict (json.loads + regex fallback)
   - При ошибке → `stub_script()` (генерирует валидный шаблон, не throw)

6. **render_markdown** — JSON → markdown с frontmatter
   - Frontmatter — JSON-блок (для `validate_script.py`)
   - Body — таблица шотов + CTA + caption + hashtags

7. **Save**:
   - `tmp/scripts/<profile>/<slug>.md` — markdown
   - `state/<profile>/<slug>.json` — `status=script_ready`, timestamps

## Выходные файлы

```
tmp/scripts/lab/5-oshibok-karty-zhelaniy.md   # сценарий
state/lab/5-oshibok-karty-zhelaniy.json        # мета
```

Пример `state/lab/<slug>.json`:
```json
{
  "slug": "5-oshibok-karty-zhelaniy",
  "profile": "lab",
  "status": "script_ready",
  "title": "5 ошибок карты желаний",
  "created_at": "2026-06-17T15:30:00Z",
  "script_at": "2026-06-17T15:30:00Z",
  "script_path": "tmp/scripts/lab/5-oshibok-karty-zhelaniy.md",
  "channels_posted": {"tg": null, "vk": null, "email": null, "ok": null, "zen": null},
  "channels_failed": [],
  "error": null
}
```

## Параметры (CLI)

| Аргумент | Описание | Default |
|---|---|---|
| `platform` | tiktok/youtube/vk/telegram/reels | из profile |
| `goal` | engagement/subscribe/traffic/contest | из profile |
| `tone` | soulful/bold/inspiring/... | из profile |
| `duration` | 15/30/45/60/90 сек | из profile |
| `source` | Тема/цитата/идея | обязателен |
| `--profile` | lab/wl/coach/experts/market | PROFILE_DEFAULT env или "lab" |
| `--voice` | alena/jane/filipp/ermil/marina/madirus/zahar | из profile |
| `--speed` | 0.1-3.0 | из profile |
| `--music-mood` | ambient/uplifting/... | из profile |
| `--cta` | Override CTA-текста | из profile |
| `--from-file` | Прочитать source из файла | - |
| `--out` | Куда сохранить .md | tmp/scripts/&lt;profile&gt;/&lt;slug&gt;.md |
| `--dry-run` | Только показать промпт | False |
| `--force` | Перезаписать существующий | False |

## Связано с
- `scripts/cmd_script.py` — реализация
- `scripts/llm_factory.py` — LLM-обёртка
- `scripts/state.py` — идемпотентность
- `scripts/validate_script.py` — валидация
- `prompts/script-generate.md` — документация промпта
- `sub-skills/profile-system.md` — override-матрица
