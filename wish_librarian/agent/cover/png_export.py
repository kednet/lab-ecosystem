"""
PNG-экспорт SVG-обложек через Playwright (Node CLI) — fallback на cairosvg.

Использование:
  from agent.cover.png_export import svg_to_png
  svg_to_png(svg_bytes, Path("output/cover.jpg"), width=1200, height=1800)

Стратегия:
  1. Сначала пробуем Playwright (Node) — точно рендерит кириллицу.
  2. Если Node не установлен или playwright не работает — fallback на cairosvg.
  3. Если ничего нет — None + warning.

Playwright CLI: `npx playwright screenshot --viewport-size WxH URL OUTPUT`.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Optional, Union

from agent.utils.logger import get_logger


logger = get_logger()


# Проверяем доступность бэкендов один раз при импорте
def _find_npx() -> Optional[str]:
    """Найти npx (включая .cmd на Windows)."""
    for name in ("npx", "npx.cmd", "npx.exe"):
        path = shutil.which(name)
        if path:
            return path
    return None


def _has_npx() -> bool:
    return _find_npx() is not None


def _has_cairo() -> bool:
    try:
        import cairosvg  # noqa: F401
        return True
    except (ImportError, OSError):
        # OSError — cairocffi не нашёл libcairo.so.2 на этой машине
        return False


_HAS_NPX   = _has_npx()
_NPX_PATH  = _find_npx()  # полный путь, для subprocess на Windows
_HAS_CAIRO = _has_cairo()


def has_playwright() -> bool:
    """Доступен ли Node-based Playwright (после `npx playwright install chromium`)."""
    return _HAS_NPX


def has_cairo() -> bool:
    """Доступен ли cairosvg (pip)."""
    return _HAS_CAIRO


def has_any_backend() -> bool:
    """Хотя бы один бэкенд PNG-конверсии доступен."""
    return _HAS_NPX or _HAS_CAIRO


# ── Основной API ────────────────────────────────────────────────────
def svg_to_png(
    svg_bytes: bytes,
    output_path: Union[str, Path],
    *,
    width: int = 1200,
    height: int = 1800,
    output_format: str = "jpg",
    jpeg_quality: int = 92,
    timeout_sec: int = 30,
) -> Optional[Path]:
    """
    Сконвертировать SVG → PNG/JPG.

    Пробует в порядке:
      1) Playwright (Node) — точно рендерит кириллицу, тяжелее.
      2) cairosvg — легче, но хуже с шрифтами.

    Args:
        svg_bytes: SVG-файл в байтах.
        output_path: куда сохранить результат (расширение добавится автоматически).
        width/height: размер канвы.
        output_format: 'png' | 'jpg'.
        jpeg_quality: качество JPEG (1-100), только для cairosvg.
        timeout_sec: таймаут Playwright.

    Returns:
        Path к записанному файлу или None при неудаче.
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Определяем финальный путь
    if output_format == "jpg":
        final_path = output_path.with_suffix(".jpg")
    else:
        final_path = output_path.with_suffix(".png")

    # 1) Playwright
    if _HAS_NPX:
        result = _via_playwright(
            svg_bytes, final_path, width, height, timeout_sec
        )
        if result is not None:
            return result
        logger.info("Playwright не сработал, пробую cairosvg...")

    # 2) cairosvg
    if _HAS_CAIRO:
        result = _via_cairo(
            svg_bytes, final_path, width, height, output_format, jpeg_quality
        )
        if result is not None:
            return result

    logger.warning(
        "⚠️  Не удалось сгенерировать PNG/JPG. "
        "Установи: pip install cairosvg или npx playwright install chromium"
    )
    return None


# ── Бэкенды ────────────────────────────────────────────────────────
def _via_playwright(
    svg_bytes: bytes,
    output_path: Path,
    width: int,
    height: int,
    timeout_sec: int,
) -> Optional[Path]:
    """
    Скриншот SVG через Playwright CLI.

    Стратегия: сохраняем SVG в .html с <img src="data:..."/>, открываем
    Chromium с нужным viewport, делаем скриншот. Кириллица рендерится
    системными шрифтами Chromium.
    """
    try:
        # Оборачиваем SVG в HTML с правильным viewport.
        # ВАЖНО: используем inline SVG (не data: URI в <img>) — Chromium
        # нестабильно рендерит SVG через <img src="data:image/svg+xml;base64,...">
        # когда в SVG есть <tspan> + text-anchor (text уходит за пределы viewBox).
        # Inline SVG рендерится корректно.
        svg_str = svg_bytes.decode("utf-8")
        html = (
            f"<!DOCTYPE html><html><head>"
            f"<meta charset=\"utf-8\">"
            f"<style>html,body{{margin:0;padding:0;background:transparent}}"
            f"svg{{display:block}}</style></head><body>"
            f"{svg_str}"
            f"</body></html>"
        )
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            html_path = tmp_path / "page.html"
            html_path.write_text(html, encoding="utf-8")
            png_path = tmp_path / "out.png"
            # Path.as_uri() корректно генерирует file:// URL и на Windows
            # (с тремя слешами для абсолютного пути).
            url = html_path.as_uri()

            # На Windows .CMD-файлы не запускаются напрямую через subprocess —
            # их нужно выполнять через cmd.exe /c
            # wait-for-timeout 500мс: для inline SVG с кириллицей + tspan Chromium
            # нужно время на layout, 200мс иногда даёт пустой/обрезанный PNG.
            if _NPX_PATH and _NPX_PATH.lower().endswith((".cmd", ".bat")):
                cmd = [
                    "cmd.exe", "/c",
                    _NPX_PATH, "playwright", "screenshot",
                    "--viewport-size", f"{width},{height}",
                    "--wait-for-timeout", "500",
                    url, str(png_path),
                ]
            else:
                cmd = [
                    _NPX_PATH or "npx", "playwright", "screenshot",
                    "--viewport-size", f"{width},{height}",
                    "--wait-for-timeout", "500",
                    url, str(png_path),
                ]
            t0 = time.time()
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                encoding="utf-8",       # cp1252 → UnicodeDecodeError на stdout Playwright
                errors="replace",       # безопасный fallback для бинарных байтов
                timeout=timeout_sec,
            )
            elapsed = time.time() - t0
            if proc.returncode != 0:
                logger.warning(
                    "Playwright вернул код {} за {:.1f}с: {}",
                    proc.returncode, elapsed, (proc.stderr or "")[:200],
                )
                return None
            if not png_path.exists():
                logger.warning("Playwright не создал выходной файл")
                return None
            # Конвертируем PNG → JPG если нужно
            if output_path.suffix.lower() == ".jpg":
                _png_to_jpg(png_path, output_path)
            else:
                shutil.copy2(png_path, output_path)
            logger.info("🎨 Playwright → {} ({:.1f}с, {} KB)",
                       output_path.name, elapsed,
                       output_path.stat().st_size // 1024)
            return output_path
    except subprocess.TimeoutExpired:
        logger.warning("Playwright timeout ({}с)", timeout_sec)
        return None
    except FileNotFoundError:
        logger.info("npx/playwright не найдены — пропускаю")
        return None
    except Exception as e:
        logger.warning("Playwright ошибка: {}", e)
        return None


def _via_cairo(
    svg_bytes: bytes,
    output_path: Path,
    width: int,
    height: int,
    output_format: str,
    jpeg_quality: int,
) -> Optional[Path]:
    """Через cairosvg (pip)."""
    try:
        import cairosvg
        cairosvg.svg2png(
            bytestring=svg_bytes,
            output_width=width,
            output_height=height,
            write_to=str(output_path.with_suffix(".png")),
            output_format="png",
        )
        if output_format == "jpg":
            _png_to_jpg(output_path.with_suffix(".png"), output_path)
            output_path.with_suffix(".png").unlink(missing_ok=True)
        logger.info("🎨 cairosvg → {} ({} KB)",
                   output_path.name,
                   output_path.stat().st_size // 1024)
        return output_path
    except Exception as e:
        logger.warning("cairosvg ошибка: {}", e)
        return None


# ── Утилита PNG → JPG (через Pillow, fallback — копия PNG) ────────
def _png_to_jpg(png_path: Path, jpg_path: Path, quality: int = 92) -> None:
    """Сконвертировать PNG → JPG. Если Pillow недоступен — копия PNG в jpg_path."""
    try:
        from PIL import Image
        img = Image.open(png_path).convert("RGB")
        img.save(jpg_path, "JPEG", quality=quality, optimize=True)
    except ImportError:
        # Pillow нет — оставляем PNG, но копируем в jpg_path (даже если расширение .jpg)
        # Это лучше, чем None — Publisher всё равно прочитает PNG.
        shutil.copy2(png_path, jpg_path)
        logger.warning("Pillow не установлен — JPG не сжат, оставлен PNG внутри {}".format(jpg_path.name))
    except Exception as e:
        logger.warning("PNG→JPG не удался: {}", e)
        shutil.copy2(png_path, jpg_path)
