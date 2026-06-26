---
name: publish-mode
description: "STUB. Phase 3: интеграция с publisher_skill + автопубликация"
metadata:
  type: sub-skill
  phase: 3
---

# Publish Mode (Phase 3 STUB)

## Что это будет

Автопубликация сгенерированной и обработанной картинки в каналы:
1. Загрузка PNG в Cloudflare R2 (или локально в `lab_site/public/images/`).
2. Опционально: авто-attach к статье в `publisher_skill/data/<slug>.json` как `og:image`.
3. Опционально: постинг с подписью (через `prompts/announce-text.md`) в VK/TG/OK.

## Требования

- Cloudflare R2 bucket + `R2_*` ключи
- VK/TG/OK/Zen токены (уже есть в `publisher_skill/.env`)
- Phase 2 сначала (нужен upscaled PNG, не 512×512)

## Команды (планируемые)

```bash
# Загрузить в R2 + вернуть public URL
python scripts/image.py publish lab/5-oshibok --profile=lab --upload=r2

# Прикрепить к статье в publisher_skill
python scripts/image.py publish lab/5-oshibok --attach-to-article

# Полный цикл: upload + attach + post в VK/TG
python scripts/image.py publish lab/5-oshibok --channels=vk,tg
```

## Алгоритм (планируемый)

```
1. Load state → status должен быть "upscaled" (иначе ошибка)
2. Загрузить upscaled_path в R2 → public_url
3. Если --attach-to-article:
   a. Найти статью в publisher_skill/data/<slug>.json
   b. Дописать в frontmatter: og_image: <public_url>
4. Если --channels:
   a. LLM-генерация подписи (prompts/announce-text.md)
   b. Постинг через publisher_skill.post_channels
5. state.update(published_at=now, live_url=...)
6. status: upscaled → published
```

## Что НЕ делается в Phase 1

В Phase 1 режим publish — STUB. Просто печатает требования. Полезный результат будет
в Phase 3 (~4-6 ч разработки после Phase 2).

## Связано с

- [[image-skill-v1-phase1-built]]
- [[publisher-skill-built]] — целевой интеграционный партнёр
- [[phase-2-plan]] — должно быть реализовано после auto-mode
