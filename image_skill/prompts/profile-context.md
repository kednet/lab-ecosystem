# Profile Context — инъекция профиля в промпт

## Назначение

Сформировать блок "контекст профиля" для подстановки в LLM-промпт (image-prompt.md).

Используется в `cmd_generate.py:build_prompt()`.

## Формат

```
## Контекст профиля "{display_name}"
- Описание: {description}
- Watermark: {branding.watermark}
- Акцентный цвет: {branding.accent_color}
- Палитра: primary={palette.primary}, deep={palette.primary_deep}, soft={palette.primary_soft}, bg={palette.bg}
- Базовые хештеги: {hashtags_base}
- Стили (style → подсказка): {prompt_styles}
- Настроения (mood → подсказка): {prompt_moods}
- Negative prompts: {negative_prompts}
- Подсказки по темам: {source_domains}
```

## Edge-cases

- `source_domains` пустой → блок пропускается
- `hashtags_base` пустой → блок пропускается
- `prompt_styles[style]` отсутствует → используется сам `style` как подсказка
- `prompt_moods[mood]` отсутствует → используется сам `mood` как подсказка
- `negative_prompts` пустой → строка "no text, no watermark"

## Реализация

Сейчас в `cmd_generate.py` инъекция вшита в `image-prompt.md` напрямую (формат str.format()).
Phase 2 можно вынести в отдельную функцию `build_profile_context(profile, style, mood) -> str`.

## Связано с
- [[image-skill-v1-phase1-built]]
- [[prompts/image-prompt]]
