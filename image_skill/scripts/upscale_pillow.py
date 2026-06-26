"""
upscale_pillow.py — Pillow Lanczos upscale до format.target_size.

Используется в `cmd_auto.py` (Phase 2 pipeline).

Алгоритм:
1. Открыть JPEG/PNG через Pillow (auto-detect по расширению)
2. Конвертировать в RGB (RGBA → на белый фон, иначе JPEG падает)
3. Image.LANCZOS resize до (target_w, target_h)
4. Save как JPEG (quality=92, optimize=True, progressive=True)
5. Вернуть (path, size_kb)

Pillow Lanczos даёт гладкое увеличение без aliasing. Лучший choice для
upscale фотографий и иллюстраций. Для сильного увеличения (>2x) появится
мыло — тогда Phase 3+ переключится на Real-ESRGAN.
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Optional, Tuple

from PIL import Image

JPEG_QUALITY = 92


def upscale_to_target(
    src_path: Path,
    target_w: int,
    target_h: int,
    out_path: Optional[Path] = None,
) -> Tuple[Path, float]:
    """
    Upscale JPEG/PNG до (target_w, target_h) через Lanczos.

    Args:
        src_path: исходный файл (PNG/JPEG)
        target_w: целевая ширина (px)
        target_h: целевая высота (px)
        out_path: куда сохранить (если None — заменяет расширение на -upscaled.jpg)

    Returns:
        (Path к сохранённому файлу, size_kb)
    """
    src_path = Path(src_path)
    if not src_path.exists():
        raise FileNotFoundError(f"Не найден исходник: {src_path}")

    img = Image.open(src_path)
    # RGBA → RGB (иначе JPEG ругается)
    if img.mode in ("RGBA", "LA", "P"):
        background = Image.new("RGB", img.size, (255, 255, 255))
        if img.mode == "P":
            img = img.convert("RGBA")
        background.paste(img, mask=img.split()[-1] if img.mode == "RGBA" else None)
        img = background
    elif img.mode != "RGB":
        img = img.convert("RGB")

    src_w, src_h = img.size
    print(f"  → Upscale {src_w}×{src_h} → {target_w}×{target_h} (Lanczos)", file=sys.stderr)

    upscaled = img.resize((target_w, target_h), Image.LANCZOS)

    # Path
    if out_path is None:
        # /foo/bar-vk_post.jpg → /foo/bar-vk_post-upscaled.jpg
        stem = src_path.stem
        # отрезать -<format> если есть
        out_path = src_path.with_name(f"{stem}-upscaled.jpg")
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    upscaled.save(
        out_path,
        format="JPEG",
        quality=JPEG_QUALITY,
        optimize=True,
        progressive=True,
    )

    size_kb = out_path.stat().st_size / 1024
    return out_path, round(size_kb, 1)


def parse_target(arg: Optional[str]) -> Optional[Tuple[int, int]]:
    """
    Распарсить --to=1080x1080 → (1080, 1080). None если arg пустой.
    """
    if not arg:
        return None
    if "x" not in arg.lower():
        raise ValueError(f"--to ожидает формат WIDTHxHEIGHT, получил: {arg!r}")
    w, h = arg.lower().split("x", 1)
    return (int(w), int(h))


if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser(description="Upscale JPEG/PNG через Pillow Lanczos")
    p.add_argument("src", help="Исходный файл")
    p.add_argument("--to", required=True, help="Целевой размер: WIDTHxHEIGHT (например 1080x1080)")
    p.add_argument("--out", default=None, help="Путь сохранения (default: <src>-upscaled.jpg)")
    args = p.parse_args()

    target = parse_target(args.to)
    assert target is not None
    out_path, size_kb = upscale_to_target(Path(args.src), target[0], target[1], Path(args.out) if args.out else None)
    print(f"✅ {out_path} ({size_kb} КБ)")
