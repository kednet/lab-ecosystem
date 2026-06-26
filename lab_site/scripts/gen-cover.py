"""
Генератор обложек для книг в стиле сайта lab_site.

Использование:
    python scripts/gen-cover.py                  # только книги без обложки
    python scripts/gen-cover.py --force          # перегенерить все
    python scripts/gen-cover.py --slug ot-mechty # конкретная книга

Дизайн (3:4, 600×800):
  - Радиальный градиент (светлое сверху) → линейный градиент к rose-deep снизу
  - Сверху: «ЛАБОРАТОРИЯ ЖЕЛАНИЙ» (9px, letter-spacing)
  - Центр: эмодзи-иконка по теме (крупно, с тенью)
  - Низ: название книги (DM Serif Display, italic если длинное) + автор · год
  - Бумажная текстура: лёгкий тёмный overlay снизу

Зависимости:
    pip install playwright
    python -m playwright install chromium
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Optional

# Windows: включить UTF-8 в stdout/stderr (иначе эмодзи в путях/именах → charmap)
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8")
    except Exception:
        pass

# Пути — относительно корня lab_site/
ROOT = Path(__file__).resolve().parent.parent
BOOKS_JSON = ROOT / "src" / "data" / "books.json"
PUBLIC_BOOKS = ROOT / "public" / "books"
FONTS_DIR = ROOT / "public" / "fonts"  # woff2 для Manrope / DM Serif Display (если есть локально)


# ──────────────────────────────────────────────────────────────
# Палитра (фирменные цвета сайта)
# ──────────────────────────────────────────────────────────────
PALETTE = {
    # Градиент обложки — фирменные розовые (как в audio-треках)
    "rose_soft":   "#FECDD3",  # светлый
    "rose":        "#FB7185",  # средний
    "rose_deep":   "#E11D48",  # основной бренд
    "rose_dark":   "#9F1239",  # тёмный

    # Для более «глубоких» книг
    "blush":       "#FFE4E6",
    "mauve":       "#9F1239",

    # Текст
    "text_light":  "#FFFFFF",
    "text_muted":  "rgba(255, 255, 255, 0.85)",
    "text_faint":  "rgba(255, 255, 255, 0.55)",
}

# Градиент по умолчанию: розовый (как у audio «Ermil»)
DEFAULT_GRADIENT = (PALETTE["rose_soft"], PALETTE["rose_deep"])
# Альтернативный: малиновый (как у audio «Alena»)
ALT_GRADIENT = (PALETTE["blush"], PALETTE["mauve"])


# ──────────────────────────────────────────────────────────────
# Эмодзи-иконка по тегам/названию
# ──────────────────────────────────────────────────────────────
def pick_emoji(book: dict) -> str:
    """Подбирает иконку по slug/тегам/названию. Если ничего не нашёл — книга."""
    title = (book.get("title") or "").lower()
    tags = " ".join(book.get("tags") or []).lower()
    themes = " ".join(book.get("themes") or []).lower()
    blob = f"{title} {tags} {themes}"

    rules = [
        (["деньг", "финанс", "капит"],      "💰"),
        (["любов", "отношен", "брак"],      "💗"),
        (["медитац", "осознанн", "mindful"], "🧘"),
        (["привычк", "habit"],              "🌱"),
        (["цели", "goal", "успех"],         "🎯"),
        (["сон", "засып"],                  "🌙"),
        (["тревог", "страх", "паник"],      "🌊"),
        (["самооценк", "уверенност"],       "⭐"),
        (["критик", "внутренн"],            "🪞"),
        (["мотивац", "энерг"],              "🔥"),
        (["прокрастин"],                    "⏳"),
        (["женск"],                         "🌸"),
    ]
    for keys, emoji in rules:
        if any(k in blob for k in keys):
            return emoji
    return "📖"


# ──────────────────────────────────────────────────────────────
# SVG-шаблон (600×800)
# ──────────────────────────────────────────────────────────────
def render_svg(title: str, author: str, year: Optional[int], emoji: str,
               gradient: tuple[str, str], brand: str = "ЛАБОРАТОРИЯ ЖЕЛАНИЙ") -> str:
    c1, c2 = gradient

    # Перенос длинного названия: делим по пробелам, чтобы каждая строка ≤ 5 слов
    words = title.split()
    lines: list[str] = []
    cur: list[str] = []
    for w in words:
        cur.append(w)
        if len(cur) >= 3 and sum(len(x) for x in cur) > 18:
            lines.append(" ".join(cur))
            cur = []
    if cur:
        lines.append(" ".join(cur))
    if len(lines) > 4:
        lines = lines[:3] + ["…"]

    # Вертикальное центрирование названия
    base_y = 510
    line_h = 56
    n = len(lines)
    start_y = base_y - (line_h * (n - 1)) // 2

    title_svg = ""
    for i, ln in enumerate(lines):
        font_size = 44 if n <= 2 else 38
        title_svg += (
            f'  <text x="300" y="{start_y + i * line_h}" '
            f'font-family="\'DM Serif Display\', Georgia, serif" '
            f'font-size="{font_size}" font-weight="400" '
            f'fill="white" text-anchor="middle" '
            f'style="text-shadow: 0 2px 6px rgba(0,0,0,0.25)">{escape(ln)}</text>\n'
        )

    author_line = f"{author}{(' · ' + str(year)) if year else ''}"

    return f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 600 800" width="600" height="800">
  <defs>
    <radialGradient id="bgRad" cx="20%" cy="20%" r="80%">
      <stop offset="0%" stop-color="white" stop-opacity="0.18"/>
      <stop offset="60%" stop-color="white" stop-opacity="0"/>
    </radialGradient>
    <linearGradient id="bgLin" x1="0%" y1="0%" x2="0%" y2="100%">
      <stop offset="0%" stop-color="{c1}"/>
      <stop offset="100%" stop-color="{c2}"/>
    </linearGradient>
    <linearGradient id="overlay" x1="0%" y1="0%" x2="0%" y2="100%">
      <stop offset="0%" stop-color="black" stop-opacity="0"/>
      <stop offset="100%" stop-color="black" stop-opacity="0.25"/>
    </linearGradient>
  </defs>

  <!-- Фон: градиент + лёгкий радиальный highlight -->
  <rect width="600" height="800" fill="url(#bgLin)"/>
  <rect width="600" height="800" fill="url(#bgRad)"/>

  <!-- Тонкий тёмный overlay снизу (как в TrackCard) -->
  <rect width="600" height="800" fill="url(#overlay)"/>

  <!-- Бренд-надпись сверху -->
  <text x="300" y="60" font-family="Manrope, Arial, sans-serif" font-size="13"
        font-weight="700" letter-spacing="3.5" fill="white" fill-opacity="0.92"
        text-anchor="middle">ЛАБОРАТОРИЯ ЖЕЛАНИЙ</text>

  <!-- Эмодзи-иконка по центру -->
  <text x="300" y="380" font-size="180" text-anchor="middle"
        style="filter: drop-shadow(0 8px 18px rgba(0,0,0,0.22));">{emoji}</text>

  <!-- Декоративный разделитель -->
  <line x1="240" y1="450" x2="360" y2="450" stroke="white" stroke-opacity="0.35" stroke-width="1.2"/>

  <!-- Название книги -->
{title_svg}
  <!-- Автор · год -->
  <text x="300" y="710" font-family="Manrope, Arial, sans-serif" font-size="20"
        font-weight="500" fill="white" fill-opacity="0.9" text-anchor="middle">{escape(author_line)}</text>

  <!-- Дисклеймер: бренд-каталог -->
  <text x="300" y="770" font-family="Manrope, Arial, sans-serif" font-size="10"
        font-weight="600" letter-spacing="2" fill="white" fill-opacity="0.45"
        text-anchor="middle">КОНСПЕКТ · ВОРКБУК · ПРАКТИКА</text>
</svg>'''


def escape(s: str) -> str:
    """Мини-html-escape для SVG-текста."""
    return (s.replace("&", "&amp;")
             .replace("<", "&lt;")
             .replace(">", "&gt;"))


# ──────────────────────────────────────────────────────────────
# Конвертация SVG → PNG (через Playwright) → JPG (PIL)
# ──────────────────────────────────────────────────────────────
def svg_to_png(svg: str, png_path: Path) -> None:
    """Рендерит SVG в PNG 1200×1600 (Retina) через Playwright Chromium."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("❌ playwright не установлен: pip install playwright && python -m playwright install chromium",
              file=sys.stderr)
        sys.exit(1)

    html = f'''<!doctype html>
<html><head><meta charset="utf-8">
<style>
  html, body {{ margin: 0; padding: 0; background: transparent; }}
  body {{ display: flex; align-items: center; justify-content: center; }}
</style></head><body>{svg}</body></html>'''

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1200, "height": 1600},
                                device_scale_factor=2)
        page.set_content(html)
        # Скрин именно SVG-элемента
        svg_el = page.locator("svg")
        svg_el.screenshot(path=str(png_path), omit_background=True)
        browser.close()


def png_to_jpg(png_path: Path, jpg_path: Path, quality: int = 88) -> None:
    """Конвертит PNG → JPG с белым фоном. Без Pillow — fallback: переименование в .jpg."""
    try:
        from PIL import Image
        img = Image.open(png_path).convert("RGB")
        img.save(jpg_path, "JPEG", quality=quality, optimize=True)
        png_path.unlink(missing_ok=True)
    except ImportError:
        # Без Pillow — оставляем PNG-байтстрим в .jpg-файле (как в WL-обложках)
        png_path.replace(jpg_path)


# ──────────────────────────────────────────────────────────────
# Main
# ──────────────────────────────────────────────────────────────
def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--force", action="store_true",
                    help="Перегенерировать обложки, даже если файл уже есть")
    ap.add_argument("--slug", type=str,
                    help="Только указанный slug (по умолчанию — все без обложки)")
    ap.add_argument("--alt", action="store_true",
                    help="Использовать альтернативный градиент (blush → mauve)")
    args = ap.parse_args()

    with BOOKS_JSON.open(encoding="utf-8") as f:
        data = json.load(f)
    books = data["books"]

    PUBLIC_BOOKS.mkdir(parents=True, exist_ok=True)

    # Отбор книз
    to_process = []
    for b in books:
        slug = b.get("slug")
        if not slug:
            continue
        if args.slug and args.slug not in slug:
            continue
        target = PUBLIC_BOOKS / f"{slug}.jpg"
        if target.exists() and not args.force:
            print(f"[skip] {slug}: already exists ({target.stat().st_size} B)")
            continue
        to_process.append(b)

    if not to_process:
        print("Nothing to do: all covers exist (use --force to regenerate).")
        return 0

    gradient = ALT_GRADIENT if args.alt else DEFAULT_GRADIENT

    for b in to_process:
        slug = b["slug"]
        target = PUBLIC_BOOKS / f"{slug}.jpg"
        tmp_png = PUBLIC_BOOKS / f"{slug}.__tmp.png"

        emoji = pick_emoji(b)
        svg = render_svg(
            title=b["title"],
            author=b.get("author", ""),
            year=b.get("year"),
            emoji=emoji,
            gradient=gradient,
        )

        try:
            svg_to_png(svg, tmp_png)
            png_to_jpg(tmp_png, target)
            size = target.stat().st_size
            print(f"[OK] {slug}: {b['title'][:40]}... -> {target.name} ({size:,} B)")
        except Exception as e:
            print(f"[ERR] {slug}: {e}", file=sys.stderr)
            tmp_png.unlink(missing_ok=True)
            return 1

    print(f"\nDone: {len(to_process)} covers updated.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
