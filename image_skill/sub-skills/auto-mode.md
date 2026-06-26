---
name: auto-mode
description: "Phase 2: upscale + text overlay + watermark burn pipeline через Pillow"
metadata:
  type: sub-skill
  phase: 2
---

# Auto Mode (Phase 2 — готов)

`python scripts/image.py auto <slug_id> --profile=lab` — Phase 2 пайплайн обработки
сгенерированной картинки: upscale → text overlay → watermark → state update.

## Алгоритм

```
1. load state → проверить status in (saved, upscaled)
2. load profile (YAML) + format_meta (formats.yaml)
3. upscale_to_target(state.image_path, format.target_size)
   → Pillow LANCZOS, JPEG q=92 progressive
   → tmp/images/<profile>/<slug>-<format>-upscaled.jpg
4. burn_text(upscaled, state.title, format_meta, profile) — если не --no-text
   → текст в верхней трети, центрирован, в пределах safe_zones
   → цвет: profile.branding.palette.text + drop shadow white
   → подложка: rounded rect RGBA(255,255,255,180)
   → tmp/images/<profile>/<slug>-<format>-texted.jpg
5. burn_watermark(texted, profile.branding.watermark, profile) — если не --no-watermark
   → @pulab_ru в правом нижнем углу
   → цвет: profile.branding.palette.primary (#E11D48 для lab)
   → подложка: rounded rect RGBA(255,255,255,200)
   → tmp/images/<profile>/<slug>-<format>-final.jpg
6. state.update(status=upscaled, upscaled_path, upscaled_at, upscaled_size_kb, ...)
```

## Артефакты

На каждый запуск `auto` создаются файлы:

```
tmp/images/lab/5-oshibok-karty-zhelanii-vk_post.jpg              ← Phase 1 (YandexART)
tmp/images/lab/5-oshibok-karty-zhelanii-vk_post-upscaled.jpg     ← Phase 2 step 1 (Pillow Lanczos)
tmp/images/lab/5-oshibok-karty-zhelanii-vk_post-upscaled-texted.jpg  ← Phase 2 step 2 (text overlay)
tmp/images/lab/5-oshibok-karty-zhelanii-vk_post-upscaled-texted-final.jpg  ← Phase 2 step 3 (watermark)
```

Каждый шаг перезаписывает файл. Идемпотентность — через `state.upscaled_path`:
если `status=upscaled` и `upscaled_path` есть, второй запуск без `--force` пропустит pipeline.

## CLI

```bash
# Полный пайплайн (default)
python scripts/image.py auto lab/5-oshibok-karty-zhelanii --profile=lab

# Кастомный target (любой WxH, не только из format)
python scripts/image.py auto lab/... --to=1200x1200

# Без text overlay (только upscale + watermark)
python scripts/image.py auto lab/... --no-text

# Без watermark (только upscale + text)
python scripts/image.py auto lab/... --no-watermark

# Только upscale (без text и watermark)
python scripts/image.py auto lab/... --no-text --no-watermark

# Force (перезаписать существующий upscaled)
python scripts/image.py auto lab/... --force
```

## Требования

- `pip install Pillow` (уже стоит в стеке kfigh, 12.2.0)
- Шрифт: `assets/fonts/Inter-Bold.ttf` ИЛИ fallback `C:\Windows\Fonts\arialbd.ttf`
- Profile должен иметь: `branding.palette.text`, `branding.palette.primary`, `branding.watermark`

## Что делает каждый скрипт

| Скрипт | Назначение |
|---|---|
| `scripts/upscale_pillow.py` | `upscale_to_target(src, w, h, out=None) -> (Path, kb)` |
| `scripts/burn_text.py` | `burn_text(image, text, fmt, profile, out=None) -> (Path, kb)` |
| `scripts/burn_watermark.py` | `burn_watermark(image, wm_text, profile, out=None) -> (Path, kb)` |
| `scripts/cmd_auto.py` | Orchestrator: проверяет state, вызывает 3 функции, обновляет state |

Все три скрипта независимы и могут быть вызваны как standalone CLI (`python scripts/burn_text.py ...`).

## Известные ограничения

- ❌ **Lanczos не добавляет деталей** (мыло при сильном upscale). Для 1024→1080 (+5%) OK, для 832→1000 (+20%) видно. Real-ESRGAN — Phase 3+.
- ❌ **Text overlay 1 заголовок**. Многострочный CTA, подзаголовки — Phase 3+.
- ❌ **Watermark только текстовый**. PNG-рамка/логотип — Phase 3+ (assets/overlays/).
- ❌ **Шрифт arialbd** на Windows fallback (Inter-Bold скачать не получается из-за корпоративного MITM).
  Метрики чуть шире, кириллица есть — для прод-кейса достаточно.

## Связано с

- [[image-skill-v1-phase1-built]] — Phase 1 baseline
- [[upscaling-pipeline]] — детали по апскейлу
- [[yandex-art-api]] — контракт YandexART
- [[profile-system]] — override-матрица и параметры profile
