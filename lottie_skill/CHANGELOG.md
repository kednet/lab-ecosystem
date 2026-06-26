# Changelog

## v0.1 — 2026-06-19

**Создание скила.** Структура на основе опыта генерации `heart_pulse.json` для Лаборатории желаний (бордовое пульсирующее сердце 96×96, 1.4 КБ).

### Что внутри
- `SKILL.md` — полная спека Lottie v5.7+ с примерами, готовой палитрой Лаборатории, подводными камнями
- `examples/heart_pulse_96.json` — финальный 96×96 бордовый, 1.4 КБ, 1 сек loop
- `examples/heart_pulse_512.json` — расширенная 512×512 версия с 3 слоями (bg + heart + glow)
- `scripts/check_render.py` — sanity-check: рендерит 1 кадр через lottie-python, показывает top-5 цветов
- `lottie_preview/` — готовая HTML-обёртка с lottie.min.js, открыть в браузере для проверки

### Ключевые открытия
- **Порядок слоёв** в Lottie: `layers[0]` = ВЕРХНИЙ по z-order (как в AE), `layers[-1]` = нижний. Если поставить bg первым — он перекроет всё.
- **Path geometry**: для гладких форм без риска numerical issues используй `i=o=[0,0]` (tesselation даёт гладкий многоугольник).
- **Playwright pitfall**: lottie-web в headless Chromium возвращает пустой viewport PNG. Workaround: `lottie.exporters.svg.export_svg()` + Playwright screenshot статичной SVG.

### Roadmap (следующие шаги)
- Lottie → MP4 конвертер
- Lottie → GIF (требует cairosvg/wand)
- TGS-формат для Telegram
- Утилита palette-swap
- Генератор стикерпака из базового shape
