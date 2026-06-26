# Шаблон: OG-image (2:1)

## Назначение

Превью статьи в соцсетях (Open Graph). 1200×630.

## Параметры

- aspect: 2:1
- width_ratio: 6
- height_ratio: 3
- safe_zones: { top: 60, bottom: 60, left: 80, right: 80 }

## Шаблон

```markdown
# {title}

**Формат:** OG-image (2:1, target 1200×630)
**Промпт:** `{prompt}`
**Файл:** `{output_path}`
**Use case:** Превью статьи в VK, TG, FB, Twitter
```

## Связано с

- [[data-formats-yaml]] — формат og
- [[publisher-skill-built]] — целевой интеграционный партнёр (Phase 3)
