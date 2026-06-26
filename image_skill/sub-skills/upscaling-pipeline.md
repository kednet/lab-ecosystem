---
name: upscaling-pipeline
description: "Pillow Lanczos upscale (Phase 2, используется) + Real-ESRGAN / Yandex SuperResolution (Phase 3+, опционально)"
metadata:
  type: sub-skill
  phase: 2
---

# Upscaling Pipeline (Phase 2 — Pillow Lanczos в проде)

Phase 1 генерирует JPEG через YandexART: 1024×1024 для 8:8, 832×1280 для 4:6 и т.д.
Для прод-кейса (1080×1080, 1000×1500) нужен upscale. Phase 2 использует Pillow Lanczos.

## Используется сейчас: Pillow Lanczos

### Реализация

`scripts/upscale_pillow.py`:

```python
from PIL import Image
img = Image.open(src_path)
if img.mode in ("RGBA", "LA", "P"):
    # RGBA → RGB: на белый фон, иначе JPEG ругается
    background = Image.new("RGB", img.size, (255, 255, 255))
    if img.mode == "P":
        img = img.convert("RGBA")
    background.paste(img, mask=img.split()[-1] if img.mode == "RGBA" else None)
    img = background
elif img.mode != "RGB":
    img = img.convert("RGB")

upscaled = img.resize((target_w, target_h), Image.LANCZOS)
upscaled.save(out_path, format="JPEG", quality=92, optimize=True, progressive=True)
```

### Бенчмарк (текущий)

| From | To | Ratio | Размер JPEG | Время |
|---|---|---|---|---|
| 1024×1024 | 1080×1080 | +5% | 400 КБ | <1 сек |
| 832×1280 | 1000×1500 | +20% | 460 КБ | <1 сек |
| 1024×1024 | 2048×2048 | +100% | ~1.5 МБ | <2 сек |
| 832×1280 | 1920×2880 | +140% | ~2.5 МБ | <3 сек |

Lanczos — лучший выбор для гладкого увеличения без aliasing. Детерминированный.

### Ограничения

- ❌ **Не добавляет деталей**. На лицах/текстурах при сильном (>50%) увеличении видно мыло.
- ❌ **JPEG q=92**: для превью OK, для печати мало. Phase 3+ — Real-ESRGAN + PNG.

## Phase 3+: Real-ESRGAN (нейросетевой)

### Модель

- **Real-ESRGAN x4plus** (Apache 2.0), https://github.com/xinntao/Real-ESRGAN
- Размер модели: ~60 МБ
- 4× апскейл за один проход, дальше downscale до нужного target

### Плюсы

- Реалистичные детали (волосы, текстуры, края)
- 4× за один проход, потом можно Pillow downscale до нужного размера
- Работает на CPU (медленно) и GPU (быстро)

### Минусы

- 60 МБ модель скачать надо (см. corporate-mitm-proxy — может быть заблокировано)
- CPU ~10-30 сек на 1024→4096, GPU <1 сек
- Сложнее интеграция (subprocess к бинарю или pip install realesrgan)

### Когда подключать

- Если качество Pillow становится узким местом (Pinterest 832→1000 уже видно мыло)
- Для печати (300 dpi на A4 = 2480×3508)
- Для OG-image статей (1200×630 → 2400×1260 ретина)

## Phase 4+: Yandex SuperResolution

- Не в Yandex Cloud Foundation Models catalog на 2026-06-17
- Если появится — интегрировать как fallback #3

## Связано с

- [[auto-mode]] — upscale это шаг 1 пайплайна
- [[yandex-art-api]] — что YandexART отдаёт на входе
- [[image-skill-v1-phase1-built]]
