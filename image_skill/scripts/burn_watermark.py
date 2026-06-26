"""
burn_watermark.py — watermark в правом нижнем углу (Phase 2).

Используется в `cmd_auto.py` после burn_text.

Что делает:
1. Открывает texted JPEG через Pillow
2. Загружает шрифт (Inter-Bold → arialbd → Segoe UI Bold → Pillow default)
3. Рисует watermark в правом нижнем углу с полупрозрачной подложкой
4. Цвет watermark: profile.branding.palette.primary (rose-pink #E11D48 для lab)
5. Сохраняет в tmp/images/<profile>/<slug>-<format>-final.jpg
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Optional, Tuple

from PIL import Image, ImageDraw, ImageFont

from burn_text import FONT_CANDIDATES, _hex_to_rgb, load_font  # type: ignore


def burn_watermark(
    image_path: Path,
    watermark_text: str,
    profile: dict,
    out_path: Optional[Path] = None,
) -> Tuple[Path, float]:
    """
    Наложить watermark в правый нижний угол.

    Args:
        image_path: JPEG (текстed или upscaled если --no-text)
        watermark_text: "@pulab_ru"
        profile: dict из profiles/<name>.yaml (branding.palette.primary)
        out_path: default <image>-final.jpg

    Returns:
        (Path, size_kb)
    """
    if not watermark_text or not watermark_text.strip():
        raise ValueError("watermark_text пустой")

    image_path = Path(image_path)
    if not image_path.exists():
        raise FileNotFoundError(f"Не найден исходник: {image_path}")

    img = Image.open(image_path).convert("RGB")
    W, H = img.size

    # Шрифт watermark: 24px (мелкий, ненавязчивый)
    font_size = max(18, min(28, int(min(W, H) * 0.025)))
    font, font_source = load_font(font_size)

    text = watermark_text.strip()
    text_w = int(ImageDraw.Draw(img).textlength(text, font=font))
    text_h = font.size

    # Отступы от края (прямо как safe_zones.right/bottom, но минимум 24px)
    margin = max(24, int(min(W, H) * 0.025))

    x = W - text_w - margin - 16  # 16px padding подложки
    y = H - text_h - margin - 12

    # Подложка: rounded rect alpha=180
    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    overlay_draw = ImageDraw.Draw(overlay)
    overlay_draw.rounded_rectangle(
        [x - 16, y - 8, x + text_w + 16, y + text_h + 8],
        radius=8,
        fill=(255, 255, 255, 200),
    )

    img_rgba = img.convert("RGBA")
    img_rgba.alpha_composite(overlay)
    img = img_rgba.convert("RGB")
    draw = ImageDraw.Draw(img)

    # Цвет: profile.branding.palette.primary
    palette = profile.get("branding", {}).get("palette", {})
    primary_hex = palette.get("primary", "#E11D48")
    color = _hex_to_rgb(primary_hex)

    draw.text((x, y), text, font=font, fill=color)

    print(f"  → Watermark '{text}' ({font_size}px, {color}) в правом нижнем углу, font={font_source}",
          file=sys.stderr)

    if out_path is None:
        stem = image_path.stem
        out_path = image_path.with_name(f"{stem}-final.jpg")
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    img.save(out_path, format="JPEG", quality=92, optimize=True, progressive=True)
    size_kb = out_path.stat().st_size / 1024
    return out_path, round(size_kb, 1)


if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser(description="Watermark на JPEG")
    p.add_argument("image", help="Texted JPEG")
    p.add_argument("watermark", help="Текст watermark (например @pulab_ru)")
    p.add_argument("--profile", default="lab")
    p.add_argument("--out", default=None)
    args = p.parse_args()

    from cmd_profile import load_profile
    profile = load_profile(args.profile)
    out, kb = burn_watermark(Path(args.image), args.watermark, profile, Path(args.out) if args.out else None)
    print(f"✅ {out} ({kb} КБ)")
