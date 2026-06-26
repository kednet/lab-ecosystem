---
name: lottie-skill
description: Генерация Lottie JSON анимаций с нуля. Анимированные иконки, стикеры, пульсирующие элементы, превью для сайта. Создаёт валидный Bodymovin v5.7+ файл руками по спеке (без After Effects). Поддерживает scale/opacity/position/rotation keyframes, paths, ellipses, rounded rects, gradients. Включает sanity-check через lottie-python.
---

# Lottie Skill v0.1

Генерация Lottie JSON анимаций (Bodymovin v5.7+) с нуля руками — без After Effects. Создаёт файлы, которые работают в `lottie-web` (сайт), `lottie-react-native` (мобилка), `Telegram Sticker` (TGS), `VK Store` (стикеры).

## Когда использовать

- **Стикер ВК / Telegram** — анимированная иконка 96×96 / 512×512, ≤500 КБ (обычно 1-5 КБ)
- **Анимированная иконка для сайта** (loading state, success/error, decorative)
- **Превью-картинка товара** (мини-анимация на карточке)
- **Hero-элемент** (анимированный логотип/символ на лендинге)
- **Empty state / placeholder** в мобильном приложении
- **Notification badge** (пульсирующая точка уведомлений)

## Когда НЕ использовать

- Полноценные motion-graphics со сложной анимацией персонажей → After Effects + Bodymovin
- Анимации > 30 сек → лучше видео
- GIF/MP4 нужен как финальный формат → Lottie не нужен, используй ffmpeg / image-skill

## Главное правило: порядок слоёв

**В `layers[]` ПЕРВЫЙ элемент = самый ВЕРХНИЙ по z-order** (как в After Effects), последний = самый нижний. Это обратно интуиции "первый = фон".

Пример правильного порядка (heart_pulse_96):
1. `center_glow` (top) — пульсирующая точка
2. `heart` (mid)
3. `bg_pink` (bottom) — фон-подложка

Если перепутать и поставить `bg_pink` первым — он перекроет всё, в lottie-web будешь видеть только розовый квадрат.

## Структура Lottie v5.7+

```json
{
  "v": "5.7.6",          // версия Bodymovin
  "fr": 30,               // fps
  "ip": 0,                // in point (стартовый кадр)
  "op": 60,               // out point (конечный кадр)
  "w": 512,               // ширина канваса
  "h": 512,               // высота канваса
  "nm": "animation_name", // имя
  "ddd": 0,               // 3D flag (0 = 2D)
  "assets": [],           // внешние ресурсы (для нашего уровня пусто)
  "layers": [
    {
      "ddd": 0, "ind": 1, "ty": 4,        // ty:4 = shape layer
      "nm": "layer_name",
      "sr": 1,                            // time stretch
      "ks": {                             // transform
        "o": {"a": 0, "k": 100},          // opacity (0-100, или keyframes)
        "r": {"a": 0, "k": 0},            // rotation в градусах
        "p": {"a": 0, "k": [x, y, 0]},    // position (3D координаты, Z обычно 0)
        "a": {"a": 0, "k": [0, 0, 0]},    // anchor (центр трансформации, обычно [0,0,0])
        "s": {"a": 0, "k": [100, 100, 100]} // scale в % (X, Y, Z)
      },
      "ao": 0,
      "shapes": [
        // shape primitives
      ],
      "ip": 0, "op": 60, "st": 0, "bm": 0
    }
  ],
  "markers": []
}
```

## Анимированные свойства (keyframes)

Любое свойство transform (`s`, `p`, `o`, `r`) может быть анимировано через массив `k`:

```json
"s": {
  "a": 1,                 // a:1 = animated, a:0 = static
  "k": [
    {"i": {"x": [0.4, 0.4, 0.4], "y": [1, 1, 1]},
     "o": {"x": [0.6, 0.6, 0.6], "y": [0, 0, 0]},
     "t": 0, "s": [100, 100, 100]},   // t = frame, s = value at this frame
    {"i": {...}, "o": {...}, "t": 30, "s": [108, 108, 100]},
    {"t": 60, "s": [100, 100, 100]}    // последний frame без i/o = финальный
  ]
}
```

Easing `i/o`: `x:0.4 y:1 o:0.6 y:0` = smooth ease-in-out. Без easing = линейная интерполяция.

## Shape primitives

### 1. Rounded rectangle (ty:rc)
```json
{"ty": "rc", "p": {"a": 0, "k": [0, 0]}, "s": {"a": 0, "k": [width, height]}, "r": {"a": 0, "k": corner_radius}}
```

### 2. Ellipse (ty:el)
```json
{"ty": "el", "p": {"a": 0, "k": [cx, cy]}, "s": {"a": 0, "k": [rx*2, ry*2]}}
```
`s` — это полный диаметр (rx*2), не радиус.

### 3. Path (ty:sh) — фигуры через bezier
```json
{
  "ty": "sh",
  "ks": {
    "a": 0,
    "k": {
      "i": [[ix0, iy0], [ix1, iy1], ...],  // in-control points
      "o": [[ox0, oy0], [ox1, oy1], ...],  // out-control points
      "v": [[vx0, vy0], [vx1, vy1], ...],  // vertices
      "c": true                              // closed path
    }
  }
}
```

**Лайфхак для гладких кривых без риска numerical issues**: `i=o=[0,0]` для всех точек — shape tesselate'ится прямолинейными сегментами между vertices, получается гладкий многоугольник (без вырожденных bezier).

### 4. Fill (ty:fl)
```json
{"ty": "fl", "c": {"a": 0, "k": [r, g, b, 1]}, "o": {"a": 0, "k": 100}}
```
`c` — RGB в диапазоне 0.0–1.0, alpha всегда 1. `o` — opacity 0-100.

## Палитра Лаборатории желаний (готовая)

```json
{"r": 0.50, "g": 0.05, "b": 0.18}  // бордовый #800F2E (тёмное сердце)
{"r": 1.00, "g": 0.85, "b": 0.86}  // розовый #FFD9DB (фон)
{"r": 1.00, "g": 0.85, "b": 0.40}  // золотой #FFD966 (свечение)
{"r": 0.12, "g": 0.10, "b": 0.18}  // тёмно-фиолетовый #1F1A2E (тёмный текст/обводка)
```

## Quick start

### Создать новую анимацию

```bash
# 1. Скопировать пример
cp examples/heart_pulse_96.json my_animation.json

# 2. Отредактировать в любом редакторе
# - поменять w/h на нужный размер
# - поменять цвета в c
# - поменять координаты v (для path)
# - поменять keyframes в k

# 3. Проверить в браузере
cp my_animation.json lottie_preview/animation_data.json
# открой lottie_preview/index.html в браузере
```

### Проверить sanity (есть ли рендер)

```bash
python scripts/check_render.py my_animation.json
```

Скрипт рендерит 1 кадр через lottie-python + Playwright и показывает top-5 цветов. Если 3+ цвета видны — слои в правильном порядке и рендер работает. Если только 1-2 цвета — слои перекрыты, нужно развернуть порядок.

## Подводные камни

1. **Порядок слоёв** — bg первым = bg наверху. Перевёрнуто.
2. **Path geometry с большими control points** (типа `i:[-220,-160]`) может дать numerical issues. Используй `i=o=[0,0]` для простых форм.
3. **Bodymovin v5.7+** — старые версии (5.5) не поддерживают некоторые effects.
4. **Размер канваса должен совпадать с w/h** — иначе lottie-web растянет/сожмёт.
5. **Frame range**: `ip:0, op:60` = 60 кадров = 2 сек @ 30fps. Для loop: последний кадр должен вернуться к стартовому значению.
6. **Easing `i/o`** — без них анимация линейная, выглядит дёшево. Стандартный ease-in-out: `i.x:0.4 i.y:1 o.x:0.6 o.y:0`.

## Интеграция с другими скилами

- **image-skill** — сгенерированный PNG-стикер → конвертация в Lottie не работает, но можно использовать image-skill для статичных превью-кадров Lottie
- **video-skill** — для видео-финального результата (Lottie → MP4 через lottie-python)
- **publisher-skill** — готовая Lottie анимация заливается в VK/TG как вложение (пока руками через VK Store / TG Stickers)

## Roadmap (не реализовано)

- [ ] Lottie → MP4 конвертер через lottie-python + ffmpeg
- [ ] Lottie → GIF конвертер (требует cairosvg или wand, нужны системные библиотеки)
- [ ] TGS-формат для Telegram (gzipped Lottie)
- [ ] Утилита palette-swap (заменить все `#1F1A2E` на `#800F2E` во всех слоях одной командой)
- [ ] Генератор стикерпака из темы (5-30 вариаций из одного базового shape с разными цветами)
- [ ] Web-валидатор через lottie-web в headless (если починим Playwright screenshot issue)

## Подводный камень Playwright в этой системе

`lottie-web` в headless Chromium Playwright возвращает пустой viewport PNG. Workaround — рендерить через `lottie-python` (`pip install lottie`) + `lottie.exporters.svg.export_svg(anim, buf, frame)` + Playwright screenshot статичной SVG. См. `scripts/check_render.py`.

Связано: [[image-skill]], [[video-skill]], [[publisher-skill]]
