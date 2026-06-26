"""
regen_covers_with_new_styles.py — перегенерировать обложки с правильным маппингом стиль↔книга.

Логика:
- Трансерфинги/эзотерика → MYSTICAL (оставляем, там уже хорошо)
- Франкл, Канеман, Кант → CLASSIC (философская классика, учебники)
- Психология/Саморазвитие/Бизнес → MODERN
- Книги без категории (cat=None) → ротация MODERN/VINTAGE (50/50)
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

WL_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(WL_ROOT))

from agent.cover import CoverGenerator, CoverStyle
from agent.cover.png_export import svg_to_png


# slug → style (явные исключения, чтобы каждая книга получила подходящий стиль)
EXPLICIT_STYLES = {
    "Фrankl_Сkazat_zhizni_Дa": CoverStyle.CLASSIC,           # Философская классика
    "Даниэль_Канеман_Думай_медленно_решай_быстро__Даниэль_Канеман": CoverStyle.MODERN,  # Психология
    "Тemplar_Пravila_dostizheniya_tseli": CoverStyle.MODERN,   # Саморазвитие
    "Трунин_РА_От_мечты_до_успеха": CoverStyle.VINTAGE,        # Ретро-ностальгия
}

# Slug → для ротации (50/50) при cat=None
NO_CAT_ROTATION = ["modern", "vintage"]


def get_style_for_book(slug: str, cat: str | None, title: str) -> CoverStyle:
    if slug in EXPLICIT_STYLES:
        return EXPLICIT_STYLES[slug]
    if cat == "Эзотерика":
        return CoverStyle.MYSTICAL
    if cat in ("Психология", "Саморазвитие", "Бизнес", "Практика", "Философия"):
        return CoverStyle.MODERN
    if cat == "Наука":
        return CoverStyle.GEOMETRIC
    # cat is None — ротация по slug-хешу
    h = sum(ord(c) for c in slug) % 2
    return CoverStyle.MODERN if h == 0 else CoverStyle.VINTAGE


def main() -> int:
    gen = CoverGenerator()
    lib_dir = WL_ROOT / "output" / "library"
    regenerated = 0
    for book_dir in sorted(lib_dir.iterdir()):
        meta_path = book_dir / "metadata.json"
        if not meta_path.exists():
            print(f"  SKIP {book_dir.name} (no metadata.json)")
            continue

        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        title = (meta.get("title") or "").strip()
        author = (meta.get("author") or "").strip()
        if not title or not author:
            print(f"  SKIP {book_dir.name} (empty title/author)")
            continue

        cat = gen.detect_category(None, title)
        style = get_style_for_book(book_dir.name, cat, title)

        # Генерация SVG
        result = gen.generate(
            title=title,
            author=author,
            genre=None,
            style=style,
            category=cat,
        )
        (book_dir / "cover_local.svg").write_bytes(result["svg"])

        # Рендер в JPG
        cover_path = book_dir / "cover.jpg"
        png_path = svg_to_png(
            result["svg"], book_dir / "cover",
            width=800, height=1200, output_format="jpg",
        )
        if png_path:
            print(f"  ✓ {book_dir.name:55s} style={style.value:9s} cat={cat}")
            regenerated += 1

    print(f"\n📊 Регенерировано: {regenerated}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
