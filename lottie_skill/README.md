# Lottie Skill v0.1

Генерация Lottie JSON анимаций (Bodymovin v5.7+) с нуля руками — без After Effects. Создаёт файлы, которые работают в `lottie-web` (сайт), `Telegram Sticker` (TGS), `VK Store` (стикеры).

## Быстрый старт

1. Скопируй пример: `cp examples/heart_pulse_96.json my.json`
2. Открой в редакторе, поменяй w/h/цвета/keyframes
3. Положи в `lottie_preview/animation_data.json` и открой `lottie_preview/index.html` в браузере
4. Готово — файл валидный, можно грузить в VK Store / Telegram

## Структура

- `SKILL.md` — главная документация (спека Lottie, примеры, подводные камни)
- `commands/` — CLI-команды
- `scripts/` — Python-скрипты (check_render.py для sanity-check)
- `examples/` — готовые примеры (heart_pulse_96.json, heart_pulse_full.json)
- `lottie_preview/` — HTML-обёртка с lottie.min.js для локального просмотра
- `CHANGELOG.md` — история версий

## Версия 0.1 (2026-06-19)

- Создана структура скила на основе опыта генерации heart_pulse.json (2.9 КБ → 1.4 КБ)
- Главное открытие: в Lottie `layers[0]` = ВЕРХНИЙ по z-order, не нижний (обратно интуиции)
- Готовая палитра Лаборатории желаний (бордовый/розовый/золотой/тёмно-фиолетовый)
- Sanity-check через lottie-python + Playwright (обходной путь для бага headless Chromium)
