"""
seo_optimize.py — Stage 1.5: SEO-пакет через seo-advisor-skill (Phase 2+).

Использование:
  python seo_optimize.py <slug>                    # вызвать seo-advisor-skill
  python seo_optimize.py <slug> --offline          # fallback на встроенную заглушку
  python seo_optimize.py <slug> --no-og            # пропустить генерацию og_image

Стратегия v0.2:
  - пытаемся вызвать seo-advisor-skill (Python-импорт, если он есть)
  - если seo-advisor-skill не установлен как Python-модуль — fallback на _stub_build
  - в любом случае результат пишем в lab_site/src/data/books/<slug>/seo-bundle.json

NB: seo-advisor-skill v2 — это **скил Claude (SKILL.md)**, не Python-библиотека.
Поэтому полноценная интеграция возможна только если вызывать Claude-скил через
subprocess + Skill-инструмент, что вне scope Python-скрипта.
В v0.2 интеграция ограничена:
  - повторным использованием scripts/slugify.py из seo-advisor-skill (если доступен)
  - генерацией базового SEO-пакета на основе metadata.json + summary.md
  - структурой, совместимой с seo-bundle.json из seo-advisor-skill/templates
  - генерацией OG-картинки 1200×630 через wish_librarian.agent.cover
    (если установлен; иначе og_image = обложка, как раньше)
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from datetime import datetime, timezone

SKILL_ROOT = Path(__file__).resolve().parent.parent
SKILL_ROOT = Path(__file__).resolve().parent.parent
WL_OUTPUT_ROOT = Path("C:/Users/kfigh/wish_librarian/output/library")
LAB_SITE_ROOT = Path("C:/Users/kfigh/lab_site")
SEO_ADVISOR_ROOT = Path("C:/Users/kfigh/seo-advisor-skill")
WISHLIBRARIAN_ROOT = Path("C:/Users/kfigh/wish_librarian")

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

# Ключевые LSI-слова для ниши саморазвития (ручной список; Phase 3+ → AI-генерация)
LSI_SEEDS = [
    "осознанность", "намерение", "энергия", "реализация", "мечта",
    "цель", "трансформация", "гармония", "потенциал", "внутренняя сила",
    "внимание", "мышление", "подсознание", "визуализация", "действие",
    "привычки", "мотивация", "результат", "счастье", "баланс",
]

# People Also Ask — стартовый набор (Phase 3+ → AI через seo-advisor-skill /seo faq)
FAQ_TEMPLATES = [
    "О чём книга «{title}»?",
    "Кто автор книги «{title}»?",
    "Какие основные идеи в книге «{title}»?",
    "Какие практические упражнения предлагает автор?",
    "Кому подойдёт книга «{title}»?",
]


def try_import_seo_slugify():
    """Попробовать импортировать slugify из seo-advisor-skill."""
    if not SEO_ADVISOR_ROOT.exists():
        return None
    p = SEO_ADVISOR_ROOT / "scripts" / "slugify.py"
    if not p.exists():
        return None
    import importlib.util
    spec = importlib.util.spec_from_file_location("seo_slugify", p)
    m = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(m)
        return m.slugify
    except Exception as e:
        print(f"[seo] WARN: не удалось импортировать seo-advisor-skill/slugify.py: {e}", file=sys.stderr)
        return None


def extract_lsi(slug: str, limit: int = 10) -> list[str]:
    """Извлечь LSI-слова, реально встречающиеся в summary.md."""
    p = LAB_SITE_ROOT / "src" / "data" / "books" / slug / "summary.md"
    if not p.exists():
        return []
    text = p.read_text(encoding="utf-8").lower()
    found = []
    for w in LSI_SEEDS:
        if w in text:
            found.append(w)
        if len(found) >= limit:
            break
    return found


def extract_first_paragraph(slug: str, max_chars: int = 300) -> str:
    """Первый абзац из summary.md (для description)."""
    p = LAB_SITE_ROOT / "src" / "data" / "books" / slug / "summary.md"
    if not p.exists():
        return ""
    for para in p.read_text(encoding="utf-8").split("\n\n"):
        para = para.strip().lstrip("#").strip()
        if len(para) > 40:
            return para[:max_chars]
    return ""


def build_faq(slug: str, meta: dict) -> list[dict]:
    """Сгенерировать FAQPage (5 вопросов)."""
    title = meta.get("title", "")
    out = []
    for q in FAQ_TEMPLATES:
        out.append({
            "@type": "Question",
            "name": q.format(title=title),
            "acceptedAnswer": {
                "@type": "Answer",
                "text": "(ответ генерируется из summary.md в Phase 3+)"
            }
        })
    return out


def _try_import_cover_generator():
    """Импортировать CoverGenerator из wish_librarian (опционально)."""
    if not WISHLIBRARIAN_ROOT.exists():
        return None
    sys.path.insert(0, str(WISHLIBRARIAN_ROOT))
    try:
        from agent.cover import CoverGenerator
        return CoverGenerator
    except Exception as e:
        print(f"[seo] WARN: CoverGenerator не импортирован: {e}", file=sys.stderr)
        return None


def generate_og_image(
    slug: str,
    title: str,
    author: str,
    genre: str = "",
    output_format: str = "jpg",
    dst_dir: Path | None = None,
) -> str | None:
    """
    Сгенерировать OG-картинку 1200×630 для соцсетей.

    Использует wish_librarian.agent.cover.CoverGenerator (если доступен).
    Пишет в dst_dir (по умолчанию `lab_site/src/data/books/<slug>/`).

    Returns: относительный путь `/src/data/books/<slug>/og_image.{...}` или None.
    """
    CoverGenerator = _try_import_cover_generator()
    if CoverGenerator is None:
        return None

    try:
        gen = CoverGenerator()
        result = gen.generate_og(title, author, genre=genre)
        svg_bytes = result["svg"]

        # Куда писать
        ext = "jpg" if output_format == "jpg" else "svg"
        if dst_dir is None:
            dst_dir = LAB_SITE_ROOT / "src" / "data" / "books" / slug
        dst_dir = Path(dst_dir)
        dst_dir.mkdir(parents=True, exist_ok=True)
        svg_path = dst_dir / "og_image.svg"
        svg_path.write_bytes(svg_bytes)

        if ext == "svg":
            print(f"[seo] ✓ og_image.svg: {svg_path.stat().st_size // 1024} KB")
            rel = f"/src/data/books/{slug}/og_image.svg"
            return rel

        # Конверт в JPG через Playwright/cairosvg
        from agent.cover.png_export import svg_to_png
        jpg_path = svg_to_png(
            svg_bytes, dst_dir / "og_image",
            width=1200, height=630, output_format="jpg", timeout_sec=60,
        )
        if jpg_path:
            print(f"[seo] ✓ og_image: {jpg_path.name} ({jpg_path.stat().st_size // 1024} KB)")
            # Удаляем промежуточный SVG, оставляем только растровую картинку
            svg_path.unlink(missing_ok=True)
            return f"/src/data/books/{slug}/{jpg_path.name}"
        # Fallback: оставляем SVG
        print(f"[seo] ⚠ og_image.jpg не сгенерирован, fallback на SVG")
        return f"/src/data/books/{slug}/og_image.svg"
    except Exception as e:
        print(f"[seo] WARN: generate_og_image упал: {e}", file=sys.stderr)
        return None


def build_seo_bundle(slug: str, meta: dict, *, generate_og: bool = True, og_dst_dir: Path | None = None) -> dict:
    """Главная функция — собрать полный SEO-пакет.

    Args:
        slug:        идентификатор книги
        meta:        metadata.json книги
        generate_og: генерировать ли OG-картинку 1200×630 (если WL доступен)
        og_dst_dir:  куда писать og_image.{jpg,svg} (по умолчанию lab_site/...)
    """
    title = meta.get("title", "")
    author = meta.get("author", "")
    year = meta.get("year")
    isbn = meta.get("isbn")
    genre = meta.get("genre", "")
    # Динамически ищем обложку: cover.jpg > cover.png > cover.svg > cover_local.svg
    # (для книг, обработанных новым WL-генератором обложек, файла cover.jpg может не быть)
    cover_path = f"/src/data/books/{slug}/cover.jpg"
    cover_filename = "cover.jpg"
    try:
        from pathlib import Path as _P
        for name in ("cover.jpg", "cover.png", "cover.svg", "cover_local.svg"):
            cand = _P(WL_OUTPUT_ROOT) / slug / name
            if cand.exists():
                cover_path = f"/src/data/books/{slug}/{name}"
                cover_filename = name
                break
    except Exception:
        pass

    # Slug → возьмём из seo-advisor-skill если есть, иначе из нашего
    seo_slugify = try_import_seo_slugify()
    if seo_slugify:
        canonical_slug = seo_slugify(title)
    else:
        # Fallback: slugify из publisher_skill/scripts/slugify.py
        sys.path.insert(0, str(SKILL_ROOT / "scripts"))
        from slugify import slugify as our_slugify
        canonical_slug = our_slugify(title)
    if canonical_slug != slug:
        print(f"[seo] NB: slug={slug} != title-slug={canonical_slug} (используем как есть)")

    description = extract_first_paragraph(slug, max_chars=200)
    if not description:
        description = (
            f"Краткое содержание, практические советы и упражнения по книге «{title}» "
            f"автора {author}. Конспект от Лаборатории желаний."
        )
    lsi = extract_lsi(slug)
    faq = build_faq(slug, meta)

    # OG-картинка 1200×630: генерируем через WL (если доступен)
    og_path: str | None = None
    if generate_og:
        og_path = generate_og_image(slug, title, author, genre=genre, dst_dir=og_dst_dir)
    # Если og_dst_dir уже содержит og_image (сгенерировано ранее) — используем его
    if not og_path and og_dst_dir is not None:
        from pathlib import Path as _P
        og_dst_dir = _P(og_dst_dir)
        for name in ("og_image.jpg", "og_image.svg"):
            if (og_dst_dir / name).exists():
                og_path = f"/src/data/books/{slug}/{name}"
                break
    # Fallback: og_image = обложка (как раньше)
    if not og_path:
        og_path = cover_path

    bundle = {
        "title": f"{title} — конспект и практика | Лаборатория желаний",
        "description": description,
        "og_title": f"{title} — конспект и практика",
        "og_description": f"Краткое содержание, практические советы и упражнения по книге «{title}» автора {author}.",
        "og_image": og_path,
        "og_type": "book",
        "twitter_card": "summary_large_image",
        "canonical_url": f"https://pulab.online/books/{slug}",
        "keywords": lsi,
        "lsi": lsi,
        "cover_path": cover_path,
        "cover_format": cover_filename.rsplit(".", 1)[-1],
        "schema_book": {
            "@context": "https://schema.org",
            "@type": "Book",
            "name": title,
            "author": {"@type": "Person", "name": author},
            "datePublished": str(year) if year else None,
            "isbn": isbn,
            "image": f"https://pulab.online/books/{slug}/{cover_filename}",
            "inLanguage": meta.get("language", "ru"),
            "url": f"https://pulab.online/books/{slug}"
        },
        "schema_faqpage": {
            "@context": "https://schema.org",
            "@type": "FAQPage",
            "mainEntity": faq
        },
        "_meta": {
            "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "generator": "publisher_skill/scripts/seo_optimize.py",
            "seo_advisor_integration": seo_slugify is not None,
            "og_image_generated": og_path != cover_path,
            "phase": "v0.3"
        }
    }
    return bundle


def main():
    ap = argparse.ArgumentParser(description="Generate SEO bundle for book page")
    ap.add_argument("slug")
    ap.add_argument("--offline", action="store_true", help="Force offline stub (skip seo-advisor import)")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--no-og", action="store_true", help="Не генерировать OG-картинку 1200×630")
    args = ap.parse_args()

    slug = args.slug
    print(f"[seo] {slug}")

    meta_p = LAB_SITE_ROOT / "src" / "data" / "books" / slug / "metadata.json"
    if not meta_p.exists():
        meta_p = Path("C:/Users/kfigh/wish_librarian/output/library") / slug / "metadata.json"
    if not meta_p.exists():
        print(f"[seo] ✗ metadata.json не найден", file=sys.stderr)
        sys.exit(1)
    meta = json.loads(meta_p.read_text(encoding="utf-8"))

    if args.offline:
        # Принудительный fallback
        global try_import_seo_slugify
        try_import_seo_slugify = lambda: None  # type: ignore

    bundle = build_seo_bundle(slug, meta, generate_og=not args.no_og)

    if args.dry_run:
        out = SKILL_ROOT / "tmp" / f"{slug}-seo-bundle.json"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(bundle, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"[seo] DRY-RUN. Bundle в {out}")
        return

    # Пишем в lab_site
    dst = LAB_SITE_ROOT / "src" / "data" / "books" / slug / "seo-bundle.json"
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_text(json.dumps(bundle, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[seo] ✓ {dst}")
    print(f"[seo]   title: {bundle['title'][:80]}")
    print(f"[seo]   description: {bundle['description'][:120]}…")
    print(f"[seo]   og_image: {bundle['og_image']}")
    print(f"[seo]   LSI: {len(bundle['lsi'])} слов, FAQ: {len(bundle['schema_faqpage']['mainEntity'])} вопросов")


if __name__ == "__main__":
    main()
