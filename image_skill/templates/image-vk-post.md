# Шаблон: пост ВКонтакте (1:1)

## Назначение

Markdown-каркас для генерации поста ВК 1:1 (1080×1080). Используется в `cmd_generate`
как часть логирования + в `examples/` как полный пример.

## Параметры (плейсхолдеры)

- `{title}` — заголовок (первые 100 символов `source_text`)
- `{format_meta.label}` — "Пост ВКонтакте"
- `{format_meta.aspect}` — "1:1"
- `{format_meta.target_size}` — [1080, 1080]
- `{prompt}` — финальный EN-промпт для YandexART
- `{output_path}` — `tmp/images/<profile>/<slug>-vk_post.png`
- `{palette}` — палитра профиля
- `{hashtags}` — хештеги (Phase 3, для автопубликации)

## Шаблон

```markdown
# {title}

**Формат:** {format_meta.label} ({format_meta.aspect}, target {format_meta.target_size})
**Промпт:** `{prompt}`
**Файл:** `{output_path}`
**Палитра:** {palette}

## Хештеги (для автопубликации, Phase 3)
{hashtags}
```

## Пример

См. `examples/lab-5-oshibok-karty-zhelaniy.md`.

## Связано с

- [[data-formats-yaml]] — формат vk_post
- [[generate-mode]] — где используется
