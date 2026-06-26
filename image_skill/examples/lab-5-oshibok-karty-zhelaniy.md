# 5 ошибок карты желаний — VK пост (1:1, watercolor, soft)

**Формат:** Пост ВКонтакте (1:1, target 1080×1080)
**Профиль:** lab (rose-pink palette)
**Стиль:** watercolor (default из lab.yaml)
**Настроение:** soft (default из lab.yaml)

## Исходный запрос

```
5 ошибок карты желаний
```

## Финальный EN-промпт

```
Five mistakes on a dream board, soft watercolor illustration, gentle gradients,
no hard edges, dreamy, tender, warm, peaceful mood, gentle light,
rose-pink color scheme, #E11D48 accents, no text, no watermark,
high quality, detailed, professional composition.
```

## Phase 1 — generate (YandexART)

```bash
python scripts/image.py generate vk_post "5 ошибок карты желаний" --profile=lab
```

**Артефакт:** `tmp/images/lab/5-oshibok-karty-zhelanii-vk_post.jpg` — 1024×1024 JPEG, ~1.3 МБ (YandexART JPEG всегда; определяем по magic bytes)

**State:** `state/lab/5-oshibok-karty-zhelanii.json` → `status="saved"`, заполнены `image_path`, `seed`, `prompt_text`, `image_size_kb=1332`.

## Phase 2 — auto (upscale + text + watermark)

```bash
python scripts/image.py auto lab/5-oshibok-karty-zhelanii --profile=lab
```

**Pipeline:**

| Шаг | Артефакт | Размер |
|---|---|---|
| 1. Pillow Lanczos upscale 1024→1080 | `...-vk_post-upscaled.jpg` | ~390 КБ |
| 2. Text overlay «5 ошибок карты желаний» | `...-vk_post-upscaled-texted.jpg` | ~395 КБ |
| 3. Watermark `@pulab_ru` в углу | `...-vk_post-upscaled-texted-final.jpg` | ~392 КБ |

**Что появилось после Phase 2:**

- ✅ Размер 1080×1080 (точно = `format.target_size`)
- ✅ Заголовок «5 ошибок карты желаний» в верхней трети, центрированно
- ✅ Цвет текста `palette.text` (`#1F2937` — графит) с белым drop shadow (контраст на любой картинке)
- ✅ Полупрозрачная подложка под текстом (alpha=180)
- ✅ Watermark `@pulab_ru` в правом нижнем углу, цвет `palette.primary` (`#E11D48` — rose)
- ✅ State → `status="upscaled"`, `upscaled_path`, `upscaled_at`, `upscaled_size_kb`

**Кастомизация:**

```bash
# Кастомный target (любой WxH, не из format)
python scripts/image.py auto lab/... --to=1200x1200

# Без text (только upscale + watermark)
python scripts/image.py auto lab/... --no-text

# Без watermark (только upscale + text)
python scripts/image.py auto lab/... --no-watermark
```

## Параметры

| Поле | Значение |
|------|----------|
| format | vk_post |
| width_ratio | 8 |
| height_ratio | 8 |
| aspect | 1:1 |
| target_size | [1080, 1080] |
| safe_zones | {top:80, bottom:80, left:60, right:60} |
| style | watercolor |
| mood | soft |
| seed | 986490999 |
| Размер Phase 1 | 1024×1024 JPEG ~1.3 МБ |
| Размер Phase 2 final | 1080×1080 JPEG ~400 КБ |

**Note:** Phase 2 JPEG значительно меньше Phase 1 (q=92 progressive + оптимизация).

## Палитра lab

- primary: `#E11D48` (rose) — watermark
- primary_deep: `#881337` (rose-deep)
- primary_soft: `#FDA4AF` (rose-soft)
- bg: `#FFF1F2` (rose-bg)
- text: `#1F2937` (graphite) — text overlay

## Валидация

```bash
python scripts/image.py validate lab/5-oshibok-karty-zhelanii
```

✅ Проверяет:
- saved JPEG (1024×1024, ≤2 МБ)
- aspect 1:1
- upscaled JPEG (1080×1080 = target_size, ≤3 МБ)

## Связано с

- [[profile-lab]] — полный профиль
- [[template-vk-post]] — формат vk_post
- [[yandex-art-api]] — API контракт
- [[auto-mode]] — Phase 2 пайплайн
- [[upscaling-pipeline]] — детали Pillow Lanczos
