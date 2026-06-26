# /image auto

**STUB.** Реализация в Phase 2.

## Что будет (Phase 2)

Автоматический пайплайн обработки сгенерированного PNG:
1. **Upscale** до `format.target_size` (например 1080×1080) через Pillow Lanczos.
2. **Text overlay** — заголовки/CTA из `profile.branding.cta_default` + `state.title`.
3. **Watermark burn** — `@pulab_ru` в правом нижнем углу с semi-transparent фоном.
4. **Safe zones** — текст и CTA в пределах `format.safe_zones`.

## Текущее поведение

```bash
$ python scripts/image.py auto lab/5-oshibok-karty-zhelaniy --profile=lab
⚠ cmd_auto — STUB. Реализация в Phase 2.

Что будет в Phase 2:
  1. upscale_pillow.py — Lanczos upscale PNG до target_size формата
  2. burn_watermark.py — текстовый watermark (@pulab_ru) в углу
  3. text_overlay.py — заголовки и CTA поверх картинки

Требования:
  pip install Pillow
  положить шрифты в assets/fonts/ (например Inter-Bold.ttf)
```

## Требования для Phase 2

- `pip install Pillow`
- Шрифт `assets/fonts/Inter-Bold.ttf` (или аналог)
- Опционально: `assets/overlays/lab-frame.png` (рамка/бренд-элемент)

## Связано с

- [[SKILL]]
- [[sub-skill-auto-mode]] — детали STUB
- [[sub-skill-upscaling-pipeline]] — upscale pipeline
- [[phase-2-plan]] — общий план
