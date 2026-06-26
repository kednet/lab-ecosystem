# Шаблон: история ВКонтакте (9:16)

## Назначение

Вертикальный полноэкранный формат для сторис. Целевой 1080×1920.

## Параметры

- aspect: 9:16
- width_ratio: 5
- height_ratio: 9
- safe_zones: { top: 200, bottom: 250, left: 50, right: 50 }
  (сверху — аватарка/username ВК, снизу — кнопки/реакции)

## Шаблон

```markdown
# {title}

**Формат:** История ВК (9:16, target 1080×1920)
**Safe zones:** top 200px (для UI), bottom 250px (для кнопок)
**Промпт:** `{prompt}`
**Файл:** `{output_path}`
```

## Связано с

- [[data-formats-yaml]] — формат vk_story
- [[auto-mode]] — safe zones важны для text overlay
