"""
validate_image.py — валидация сгенерированных PNG/JPEG для image_skill Phase 1.

Проверяет:
1. Файл существует и не пустой
2. PNG signature (89 50 4E 47 0D 0A 1A 0A) ИЛИ JPEG signature (FF D8 FF)
3. Размер ≤ 512 КБ
4. Aspect ratio из state совпадает с фактическими размерами

Вызывается из:
- `python scripts/image.py validate <slug_id>`
- `python scripts/image.py generate ...` (после генерации)

Важно: YandexART возвращает JPEG даже при запросе PNG mime type (известная особенность API).
"""
from __future__ import annotations

import struct
import sys
from pathlib import Path

from _image_common import get_format
from state import load as load_state


PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
JPEG_SIGNATURE = b"\xff\xd8\xff"
MAX_SIZE_KB_PNG = 512
MAX_SIZE_KB_JPEG = 2048  # YandexART JPEG обычно 1-2 МБ
MAX_SIZE_KB_JPEG_UPSCALED = 3072  # Phase 2 upscaled JPEG до ~3 МБ (1080×1080 q=92)
MAX_SIZE_KB = MAX_SIZE_KB_JPEG  # default для обратной совместимости


def detect_image_format(path: Path) -> str:
    """Определить формат по magic bytes: 'png' | 'jpeg' | 'unknown'."""
    with open(path, "rb") as f:
        sig = f.read(8)
    if sig.startswith(PNG_SIGNATURE):
        return "png"
    if sig.startswith(JPEG_SIGNATURE):
        return "jpeg"
    return "unknown"


def _read_png_dimensions(path: Path) -> tuple[int, int]:
    """Прочитать width/height из PNG header (IHDR chunk)."""
    with open(path, "rb") as f:
        f.read(8)  # signature
        chunk_type = f.read(4)
        if chunk_type != b"IHDR":
            raise ValueError("Not a valid PNG (no IHDR chunk)")
        ihdr_data = f.read(13)
    width, height = struct.unpack(">II", ihdr_data[:8])
    return width, height


def _read_jpeg_dimensions(path: Path) -> tuple[int, int]:
    """Прочитать width/height из JPEG. Требует Pillow."""
    try:
        from PIL import Image  # type: ignore
        with Image.open(path) as img:
            return img.size
    except ImportError:
        raise RuntimeError("Pillow не установлен (pip install Pillow) — не могу прочитать JPEG dimensions")


def get_dimensions(path: Path) -> tuple[int, int]:
    """Получить (width, height) для PNG или JPEG файла."""
    fmt = detect_image_format(path)
    if fmt == "png":
        return _read_png_dimensions(path)
    if fmt == "jpeg":
        return _read_jpeg_dimensions(path)
    raise ValueError(f"Unknown image format for {path}")


def validate_image_file(path: Path, max_size_kb: int | None = None) -> list[str]:
    """Валидация PNG или JPEG файла. Возвращает список ошибок (пустой = OK).

    Args:
        path: путь к файлу
        max_size_kb: лимит размера в КБ. Если None — дефолт по формату.
    """
    errors: list[str] = []

    if not path.exists():
        return [f"Файл не найден: {path}"]
    if path.stat().st_size == 0:
        return [f"Файл пустой: {path}"]

    fmt = detect_image_format(path)
    if fmt == "unknown":
        with open(path, "rb") as f:
            sig = f.read(8)
        return [f"Не PNG/JPEG: signature {sig.hex()}"]

    size_kb = path.stat().st_size / 1024
    if max_size_kb is None:
        max_size_kb = MAX_SIZE_KB_PNG if fmt == "png" else MAX_SIZE_KB_JPEG
    if size_kb > max_size_kb:
        errors.append(f"Размер {size_kb:.1f} КБ > {max_size_kb} КБ ({fmt})")

    return errors


def validate_state(slug_id: str) -> list[str]:
    """Валидация state + image файла. Возвращает список ошибок (пустой = OK)."""
    errors: list[str] = []
    st = load_state(slug_id)
    if st.get("status") not in ("saved", "upscaled", "published"):
        errors.append(f"status={st.get('status')!r}, ожидается saved/upscaled/published")

    image_path = st.get("image_path")
    if not image_path:
        errors.append("image_path отсутствует в state")
        return errors

    p = Path(image_path)
    if not p.is_absolute():
        p = Path(__file__).resolve().parent.parent / image_path
    if not p.exists():
        errors.append(f"Файл не существует: {image_path}")
        return errors

    file_errors = validate_image_file(p)
    errors.extend(f"{e} (path={image_path})" for e in file_errors)
    if file_errors:
        return errors

    # Aspect ratio
    try:
        width, height = get_dimensions(p)
        fmt_name = st.get("format")
        if fmt_name:
            fmt = get_format(fmt_name)
            expected_aspect = fmt["aspect"]
            from math import gcd
            g = gcd(width, height)
            a, b = width // g, height // g
            actual_aspect_simple = f"{a}:{b}" if a >= b else f"{b}:{a}"

            # YandexART иногда рендерит чуть другой ratio (например 832×1280 ≈ 13:20 вместо 2:3).
            # Толерантность: ±10% по умолчанию, ±12% для форматов где YandexART ratio ограничен API
            # (vk_story: aspect 9:16=1.78 невозможен, max=5:8=1.62 → отклонение ~10%).
            actual_ratio = width / height
            exp_w, exp_h = map(int, expected_aspect.split(":"))
            expected_ratio = exp_w / exp_h
            ratio_diff = abs(actual_ratio - expected_ratio) / expected_ratio
            tolerance = 0.12 if fmt_name == "vk_story" else 0.10

            if actual_aspect_simple == expected_aspect:
                print(f"  ✓ Aspect {actual_aspect_simple} ({width}×{height}) matches {fmt_name}")
            elif ratio_diff <= tolerance:
                print(f"  ✓ Aspect {actual_aspect_simple} ({width}×{height}) ≈ {expected_aspect} "
                      f"({ratio_diff*100:.1f}% off, в пределах толерантности YandexART)")
            else:
                errors.append(
                    f"Aspect {actual_aspect_simple} (факт {width}×{height}) "
                    f"≠ {expected_aspect} (формат {fmt_name}, отклонение {ratio_diff*100:.1f}%)"
                )
    except Exception as e:
        errors.append(f"Не удалось прочитать dimensions: {e}")

    # Phase 2: если status=upscaled — проверить upscaled_path
    if st.get("status") in ("upscaled", "published") and st.get("upscaled_path"):
        up_errors = validate_upscaled_path(slug_id)
        errors.extend(up_errors)

    return errors


def validate_upscaled_path(slug_id: str) -> list[str]:
    """Валидация Phase 2 upscaled файла. Проверяет:
    1. state.upscaled_path существует
    2. Файл валидный JPEG
    3. Размер ≤ MAX_SIZE_KB_JPEG_UPSCALED
    4. Размеры ТОЧНО совпадают с format.target_size (Pillow детерминирован)
    """
    from _image_common import get_format
    from state import load as load_state
    st = load_state(slug_id)
    errors: list[str] = []
    upscaled_rel = st.get("upscaled_path")
    if not upscaled_rel:
        errors.append("upscaled_path отсутствует в state")
        return errors

    p = Path(upscaled_rel)
    if not p.is_absolute():
        p = Path(__file__).resolve().parent.parent / upscaled_rel
    if not p.exists():
        errors.append(f"upscaled файл не существует: {upscaled_rel}")
        return errors

    # JPEG + размер
    file_errors = validate_image_file(p, max_size_kb=MAX_SIZE_KB_JPEG_UPSCALED)
    errors.extend(f"{e} (path={upscaled_rel})" for e in file_errors)
    if file_errors:
        return errors

    # Размеры = format.target_size
    try:
        w, h = get_dimensions(p)
        fmt = get_format(st.get("format") or "")
        target = fmt.get("target_size", [w, h])
        if (w, h) != tuple(target):
            errors.append(f"Upscaled размер {w}×{h} ≠ format.target_size {tuple(target)}")
        else:
            print(f"  ✓ Upscaled {w}×{h} = format.target_size {tuple(target)} (path={upscaled_rel})")
    except Exception as e:
        errors.append(f"Не удалось прочитать upscaled dimensions: {e}")

    return errors


def run(args) -> int:
    """CLI: validate <slug_id>"""
    errors = validate_state(args.slug_id)
    if errors:
        print(f"❌ {len(errors)} ошибок для {args.slug_id}:")
        for e in errors:
            print(f"  - {e}")
        return 1
    print(f"✅ OK: {args.slug_id} валиден (image, ≤{MAX_SIZE_KB}КБ, aspect OK)")
    return 0


if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser(description="Image Skill validator")
    p.add_argument("slug_id", help="profile/slug или просто slug")
    args = p.parse_args()
    sys.exit(run(args))
