"""
burn_text.py — text overlay для upscaled-картинок (Phase 2).

Используется в `cmd_auto.py` после upscale.

Что делает:
1. Открывает upscaled JPEG через Pillow
2. Загружает шрифт (Inter-Bold → arialbd → Segoe UI Bold → Pillow default)
3. Переносит длинный текст через textwrap (max chars по ширине safe_zone)
4. Рисует заголовок в верхней трети, центрированно
5. Полупрозрачная подложка под текстом — гарантирует читаемость
6. Сохраняет в tmp/images/<profile>/<slug>-<format>-texted.jpg

Стиль:
- Цвет текста: profile.branding.palette.text (тёмный на светлом)
- Цвет подложки: белый с alpha=180
- Drop shadow: белая, offset 2px (контраст на любой картинке)
- Шрифт: 6% от меньшей стороны (28-72px)
"""
from __future__ import annotations

import sys
import textwrap
from pathlib import Path
from typing import Optional, Tuple

from PIL import Image, ImageDraw, ImageFont


# Fallback chain для шрифтов
FONT_CANDIDATES = [
    Path(__file__).resolve().parent.parent / "assets" / "fonts" / "Inter-Bold.ttf",
    Path(r"C:\Windows\Fonts\arialbd.ttf"),
    Path(r"C:\Windows\Fonts\arial.ttf"),  # regular fallback
    Path(r"C:\Windows\Fonts\segoeuib.ttf"),  # Segoe UI Semibold
]


def load_font(preferred_size: int) -> Tuple[ImageFont.FreeTypeFont, str]:
    """Загрузить первый доступный шрифт из FONT_CANDIDATES. Возвращает (font, source_label)."""
    for cand in FONT_CANDIDATES:
        if cand.exists():
            try:
                font = ImageFont.truetype(str(cand), preferred_size)
                return font, str(cand.name)
            except Exception:
                continue
    # Последний resort — Pillow default (растровый, плохой, но работает)
    return ImageFont.load_default(), "PIL-default"


def _hex_to_rgb(hex_str: str) -> Tuple[int, int, int]:
    """#RRGGBB → (R, G, B)."""
    h = hex_str.lstrip("#")
    return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))


def _measure_block(
    draw: ImageDraw.ImageDraw,
    lines: list[str],
    font: ImageFont.FreeTypeFont,
    line_spacing: int = 8,
) -> Tuple[int, int]:
    """Посчитать (width, height) блока строк с учётом line_spacing."""
    widths = [draw.textlength(line, font=font) for line in lines]
    if not widths:
        return (0, 0)
    h = len(lines) * (font.size + line_spacing) - line_spacing
    return (int(max(widths)), int(h))


def _wrap_text(
    text: str,
    max_chars_per_line: int,
) -> list[str]:
    """Перенос строки с учётом max_chars_per_line. Разбивает по словам."""
    if len(text) <= max_chars_per_line:
        return [text]
    # textwrap уважает пробелы и переносы
    return textwrap.wrap(
        text,
        width=max_chars_per_line,
        break_long_words=False,
        break_on_hyphens=False,
    ) or [text]


def burn_text(
    image_path: Path,
    text: str,
    format_meta: dict,
    profile: dict,
    out_path: Optional[Path] = None,
) -> Tuple[Path, float]:
    """
    Наложить текст на картинку с учётом safe_zones.

    Args:
        image_path: upscaled JPEG
        text: заголовок (state.title, до 100 символов)
        format_meta: dict из formats.yaml (safe_zones, aspect)
        profile: dict из profiles/<name>.yaml (branding.palette.text)
        out_path: куда сохранить (default: <image>-texted.jpg)

    Returns:
        (Path, size_kb)
    """
    if not text or not text.strip():
        raise ValueError("text пустой")

    image_path = Path(image_path)
    if not image_path.exists():
        raise FileNotFoundError(f"Не найден исходник: {image_path}")

    img = Image.open(image_path).convert("RGB")
    W, H = img.size
    draw = ImageDraw.Draw(img)

    safe = format_meta.get("safe_zones", {})
    safe_top = int(safe.get("top", 0))
    safe_bottom = int(safe.get("bottom", 0))
    safe_left = int(safe.get("left", 0))
    safe_right = int(safe.get("right", 0))

    safe_w = W - safe_left - safe_right
    safe_h = H - safe_top - safe_bottom

    # Размер шрифта: 6% от меньшей стороны, clamp 28-72px
    font_size = max(28, min(72, int(min(W, H) * 0.06)))
    font, font_source = load_font(font_size)

    # Wrap
    avg_char_w = font_size * 0.55  # эмпирика для sans-serif
    max_chars = max(8, int(safe_w / avg_char_w))
    lines = _wrap_text(text.strip(), max_chars)
    print(f"  → Text: {len(lines)} строк, font={font_source} ({font_size}px), max_chars/line={max_chars}",
          file=sys.stderr)

    line_spacing = 8
    block_w, block_h = _measure_block(draw, lines, font, line_spacing)

    # Позиция: верхняя треть, центрировано
    # Y — блок помещаем в верхнюю треть safe zone (центр верхней трети)
    y_start = safe_top + int((safe_h * 0.20))  # 20% от safe_h сверху
    x_center = safe_left + safe_w // 2

    # Подложка: rounded rect с alpha (создаём overlay)
    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    overlay_draw = ImageDraw.Draw(overlay)
    pad_x, pad_y = 24, 16
    box_x0 = x_center - block_w // 2 - pad_x
    box_y0 = y_start - pad_y
    box_x1 = x_center + block_w // 2 + pad_x
    box_y1 = y_start + block_h + pad_y
    overlay_draw.rounded_rectangle(
        [box_x0, box_y0, box_x1, box_y1],
        radius=12,
        fill=(255, 255, 255, 180),  # белая подложка alpha=180
    )

    # Склеиваем подложку с картинкой
    img_rgba = img.convert("RGBA")
    img_rgba.alpha_composite(overlay)
    img = img_rgba.convert("RGB")
    draw = ImageDraw.Draw(img)

    # Цвет текста
    palette = profile.get("branding", {}).get("palette", {})
    text_color_hex = palette.get("text", "#1F2937")
    text_color = _hex_to_rgb(text_color_hex)

    # Рисуем текст построчно
    y = y_start
    for line in lines:
        line_w = int(draw.textlength(line, font=font))
        x = x_center - line_w // 2
        # Drop shadow (белая, offset 2px) — контраст на любой картинке
        for dx, dy in [(2, 2), (-2, -2), (2, -2), (-2, 2)]:
            draw.text((x + dx, y + dy), line, font=font, fill=(255, 255, 255))
        draw.text((x, y), line, font=font, fill=text_color)
        y += font.size + line_spacing

    # Save
    if out_path is None:
        stem = image_path.stem
        out_path = image_path.with_name(f"{stem}-texted.jpg")
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    img.save(out_path, format="JPEG", quality=92, optimize=True, progressive=True)
    size_kb = out_path.stat().st_size / 1024
    return out_path, round(size_kb, 1)


if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser(description="Text overlay на JPEG/PNG")
    p.add_argument("image", help="Upscaled JPEG")
    p.add_argument("text", help="Заголовок (RU/EN)")
    p.add_argument("--profile", default="lab")
    p.add_argument("--format", default="vk_post", help="Format name для safe_zones")
    p.add_argument("--out", default=None)
    args = p.parse_args()

    from _image_common import get_format
    from cmd_profile import load_profile
    profile = load_profile(args.profile)
    fmt = get_format(args.format)
    out, kb = burn_text(Path(args.image), args.text, fmt, profile, Path(args.out) if args.out else None)
    print(f"✅ {out} ({kb} КБ)")
