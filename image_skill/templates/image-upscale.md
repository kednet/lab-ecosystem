# Шаблон: upscale (Phase 2 STUB)

## Назначение

Шаблон для upscale pipeline. Phase 2 будет использовать Pillow Lanczos для
масштабирования PNG до `format.target_size`.

## Phase 2 план

```python
from PIL import Image
img = Image.open("tmp/images/lab/...-vk_post.png")  # 512x512
upscaled = img.resize((1080, 1080), Image.LANCZOS)
upscaled.save("tmp/images/lab/...-vk_post-upscaled.png", optimize=True)
```

## Шаблон state-обновления

```json
{
  "status": "saved" → "upscaled",
  "upscaled_at": "2026-06-17T10:00:00Z",
  "upscaled_path": "tmp/images/lab/...-vk_post-upscaled.png",
  "upscaled_size_kb": 250
}
```

## Связано с

- [[upscaling-pipeline]] — детали
- [[auto-mode]] — upscale как шаг 1
