# Profile system — Video Creator Skill v1.0 (NEW)

## Что это
Универсальный скил работает с **5 проектами** через механизм профилей. Каждый профиль — это YAML-файл в `data/profiles/<name>.yaml`, который задаёт дефолты, брендинг, CTA-варианты, и подсказки для LLM.

## Доступные профили
| Профиль | Проект | Описание |
|---|---|---|
| `lab` | Лаборатория желаний | Женщины 35-44, ниша саморазвития, soulful/bold |
| `wl` | WishLibrarian | Промо новых книг, конспекты, inspiring/educational |
| `coach` | WishCoach | AI-коуч, объясняйки по модулям, educational/calm |
| `experts` | Экспертный хаб | Мини-интервью, обзоры, confident/inspiring |
| `market` | Wish Market | Анонсы маркет-плейса, конкурсы, bold/playful |

## Схема профиля (YAML)

```yaml
name: <slug>                              # ОБЯЗАТЕЛЬНО = stem файла
display_name: "..."                        # Человеческое имя (показывается в логах/state)
description: "..."                         # 1-2 предложения про ЦА и нишу

defaults:                                   # Дефолтные параметры для script
  platform: reels
  tone: soulful
  goal: engagement
  duration: 30
  voice: alena
  speed: 0.95
  music_mood: ambient

voice_tones: [soulful, bold, ...]          # Разрешённые тона (warning если не в списке)

branding:
  watermark: "@pulab_ru"                   # Текст в правом нижнем углу видео
  watermark_handle: "pulab_ru"
  cta_default: "..."                       # Fallback CTA
  cta_url: "https://..."
  accent_color: "#E11D48"                  # Для OG/субтитров/CTA
  palette: { primary, text, bg }
  gradients: [[c1, c2], ...]               # Опц.: 5 контентных градиентов

hashtags_base: ["#тег1", ...]             # Базовые хештеги (merge с LLM)

cta_profiles:                              # CTA-варианты по тону
  soulful: ["...", "..."]
  bold: ["...", "..."]

source_domains: ["...", "..."]             # Подсказки для LLM о темах

output:
  filename_template: "{slug}-lab"          # Чтобы не пересекаться между профилями
  state_subdir: "lab"                      # state/lab/<slug>.json
```

## Override-матрица (ГЛАВНОЕ)

Приоритеты (от высшего к низшему):

| Параметр | CLI-флаг | profile.defaults | profile.cta_profiles | profile.branding |
|---|---|---|---|---|
| `platform` | `--platform=vk` | `defaults.platform` | — | — |
| `tone` | `--tone=soulful` | `defaults.tone` | — | — |
| `goal` | `--goal=engagement` | `defaults.goal` | — | — |
| `duration` | `--duration=30` | `defaults.duration` | — | — |
| `voice` | `--voice=filipp` | `defaults.voice` | — | — |
| `speed` | `--speed=0.95` | `defaults.speed` | — | — |
| `music_mood` | `--music-mood=ambient` | `defaults.music_mood` | — | — |
| `cta` | `--cta="..."` | — | `cta_profiles[tone][0]` | `branding.cta_default` |
| `watermark` | — (Phase 1) | — | — | `branding.watermark` |
| `hashtags_base` | — (Phase 1) | — | — | (нет, merge с LLM) |
| `accent_color` | — (Phase 2) | — | — | `branding.accent_color` |

**Правило:** CLI-флаг бьёт профиль, профиль бьёт хардкод. Хардкода нет (universal v1.0).

**Обязательные параметры** (иначе ValueError): `platform`, `tone`, `goal`, `duration`.

## Примеры

### Пример 1: Использовать дефолты lab
```bash
python scripts/video.py script reels engagement soulful 30 "5 ошибок карты желаний" --profile=lab
# → берёт voice=alena (из lab.defaults), watermark=@pulab_ru, CTA из lab.cta_profiles.soulful
```

### Пример 2: Override голоса
```bash
python scripts/video.py script reels engagement soulful 30 "..." --profile=lab --voice=filipp
# → voice=filipp (CLI бьёт lab.defaults.voice=alena)
```

### Пример 3: Без профиля
```bash
python scripts/video.py script tiktok engagement bold 15 "проверка"
# → warning, используется defaults из platforms.yaml/voice_map.yaml, watermark пустой
```

### Пример 4: Другой профиль
```bash
python scripts/video.py script tiktok engagement inspiring 30 "Новая книга: Трансерфинг" --profile=wl
# → voice=filipp, watermark=@wishlibrarian, state в state/wl/
```

## Валидация профиля

`python scripts/video.py profile validate <name>` — проверяет обязательные поля. Ошибки:
- `name` не совпадает с именем файла
- `display_name` пустой
- `defaults.{platform,tone,goal,duration,voice}` пустые
- `branding.watermark` / `branding.accent_color` / `branding.palette.primary` пустые
- `hashtags_base` пустой
- `cta_profiles` пустой
- `output.state_subdir` пустой

## Создание нового профиля

1. Скопировать `data/profiles/<existing>.yaml` → `data/profiles/<new>.yaml`
2. Изменить `name`, `display_name`, `description`, `branding`, `hashtags_base`
3. Запустить `python scripts/video.py profile validate <new>`
4. Исправить ошибки (если есть)
5. Запустить `python scripts/video.py profile list` — новый профиль должен появиться

## Связано с
- `data/profiles/*.yaml` — сами профили
- `scripts/cmd_profile.py` — list/show/validate
- `scripts/cmd_script.py:resolve_params()` — override-матрица в коде
- `prompts/profile-context.md` — как блок профиля попадает в LLM-промпт
- `sub-skills/script-mode.md` — где resolve_params используется
