# Контекст профиля (инъекция в LLM-промпт) — Video Creator Skill v1.0

## Назначение
NEW v1.0: документирует КАК собрать блок "Контекст профиля" для подстановки в user-prompt скрипт-генератора (см. `prompts/script-generate.md`).

## Откуда берутся данные
Из YAML-файла `data/profiles/<name>.yaml`. Поля:

| Поле YAML | Куда идёт в промпте | Пример |
|---|---|---|
| `display_name` | "Контекст профиля '{display_name}'" | "Лаборатория желаний" |
| `description` | "Описание: {description}" | "Женщины 35-44..." |
| `branding.watermark` | "Бренд watermark: {watermark}" | "@pulab_ru" |
| `branding.accent_color` | "Акцентный цвет: {accent_color}" | "#E11D48" |
| `hashtags_base` | "Базовые хештеги: {hashtags_base}" | "#лабжеланий, #pulabru" |
| `source_domains` | "Подсказки по темам: {source_domains}" | "self-help, психология" |
| `cta_profiles[tone]` | "CTA-варианты для тона '{tone}': {cta_list}" | "Если откликнулось..." |
| `branding.cta_url` | (используется в render_markdown как **URL:**) | "https://app.pulab.ru/detector/" |

## Шаблон блока

```
## Контекст профиля "{display_name}"
- Описание: {description}
- Бренд watermark: {watermark}
- Акцентный цвет: {accent_color}
- Базовые хештеги: {hashtags_base_str}
- Подсказки по темам: {source_domains_str}
- CTA-варианты для тона '{tone}': {cta_for_tone_str}
```

## Реализация
См. `scripts/cmd_script.py:build_prompt()`. Функция собирает блок автоматически из `profile` (dict) + `params` (dict). Используется `profile.get('cta_profiles', {}).get(tone, [])` для подбора CTA под текущий тон.

## Edge-cases

1. **`source_domains` пустой** → блок "Подсказки по темам" опускается
2. **`hashtags_base` пустой** → LLM генерирует хештеги сама, но минимум 5
3. **`cta_profiles[tone]` пустой** → используется `profile.branding.cta_default`
4. **`branding.accent_color` пустой** → блок "Акцентный цвет" опускается

## Phase 2 расширения
- `accent_color` пойдёт в drawtext / подложку в ffmpeg
- `palette.gradients` (только в lab.yaml) — для обложек/фреймов
- `branding.cta_url` — в URL-кнопку в анонсах
