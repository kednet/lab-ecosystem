"""
render_book.py — Stage 1: WL артефакты → Astro-страница.

Использование:
  python render_book.py <slug>                    # полный рендер
  python render_book.py <slug> --dry-run          # в tmp/<slug>/, без записи в lab_site
  python render_book.py <slug> --preview          # HTML + PNG превью

Источник:    wish_librarian/output/library/<slug>/
Назначение:  lab_site/src/pages/books/<slug>.astro
             lab_site/src/data/books/<slug>.json
             lab_site/src/data/books/<slug>/* (копия артефактов)
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path
from datetime import datetime, timezone

# Локальный импорт
sys.path.insert(0, str(Path(__file__).resolve().parent))
import state  # noqa: E402

# Корни
SKILL_ROOT = Path(__file__).resolve().parent.parent
WL_OUTPUT_ROOT = Path("C:/Users/kfigh/wish_librarian/output/library")
LAB_SITE_ROOT = Path("C:/Users/kfigh/lab_site")
TEMPLATES_DIR = SKILL_ROOT / "templates"

# UTF-8
try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass


REQUIRED_ARTIFACTS = [
    "metadata.json",
    "summary.md",
    "practical_tips.md",
    "reviews.md",
    "workbook.md",
    "buy_links.md",
]
# Обложка: динамически ищем первое существующее из списка.
# Приоритет: cover.jpg (исторически скачивалось) > cover.png >
#            cover.svg (прямой SVG) > cover_local.svg (WL-генератор)
COVER_CANDIDATES = ["cover.jpg", "cover.png", "cover.svg", "cover_local.svg"]
# OG-картинка 1200×630 для соцсетей (генерится seo_optimize.py)
OG_CANDIDATES = ["og_image.jpg", "og_image.svg"]
OPTIONAL_ARTIFACTS = ["scientific.md", *COVER_CANDIDATES, *OG_CANDIDATES]


def find_cover(src: Path) -> str | None:
    """Найти файл обложки в src/ по приоритету jpg > png > svg.

    Возвращает имя файла (например 'cover.jpg') или None.
    """
    for name in COVER_CANDIDATES:
        if (src / name).exists():
            return name
    return None


def check_artifacts(slug: str, skip_cover: str = "warn") -> tuple[bool, list[str]]:
    """Проверить, что артефакты WL на месте.

    skip_cover:
      - "strict" — обложка обязательна (старый жёсткий режим)
      - "warn"   — обложка опциональна, печатаем warning, продолжаем
      - "allow"  — обложка опциональна, вообще без warning (тихий режим)
    """
    src = WL_OUTPUT_ROOT / slug
    if not src.exists():
        return False, [f"Нет папки: {src}"]

    missing = []
    for f in REQUIRED_ARTIFACTS:
        p = src / f
        if not p.exists():
            # cover.jpg → cover.png fallback (уже было)
            if f == "cover.jpg" and (src / "cover.png").exists():
                continue
            missing.append(f)

    # Обложка: динамически
    if find_cover(src) is None:
        if skip_cover == "strict":
            missing.append("cover.{jpg|png|svg}")
        elif skip_cover == "warn":
            print(f"[render] WARN: cover не найден в {src} (продолжаем без обложки)")
        # "allow" — тихо продолжаем

    if missing:
        return False, [f"Не хватает в {src}: {', '.join(missing)}"]
    return True, []


def load_metadata(slug: str) -> dict:
    """Прочитать metadata.json."""
    p = WL_OUTPUT_ROOT / slug / "metadata.json"
    with open(p, "r", encoding="utf-8") as f:
        return json.load(f)


def copy_artifacts(slug: str, dry_run: bool, dst_override: Path | None = None) -> Path:
    """Скопировать артефакты WL → lab_site/src/data/books/<slug>/."""
    src = WL_OUTPUT_ROOT / slug
    if dry_run:
        dst = SKILL_ROOT / "tmp" / f"{slug}-preview" / "data"
    elif dst_override:
        dst = dst_override
    else:
        dst = LAB_SITE_ROOT / "src" / "data" / "books" / slug
    dst.mkdir(parents=True, exist_ok=True)

    for f in REQUIRED_ARTIFACTS + OPTIONAL_ARTIFACTS:
        s = src / f
        if s.exists():
            shutil.copy2(s, dst / f)
    return dst


def _read_md_html(path: Path) -> str:
    """Прочитать .md и сконвертировать в HTML. Пустая строка если файла нет.

    Нормализуем переносы: убираем \\n внутри абзацев и склеиваем короткие
    параграфы-«обрывки» (PDF-импорты часто дают "Здесь\\n\\nон\\n\\nидет\\n\\nглубже.").
    """
    if not path.exists():
        return ""
    try:
        import re as _re
        import markdown as _md
        raw = path.read_text(encoding="utf-8")
        raw = _re.sub(r"\n{3,}", "\n\n", raw)

        # Разбиваем на параграфы по пустой строке
        paragraphs = [p.strip() for p in raw.split("\n\n") if p.strip()]

        # Классификация: «блочный» (заголовок, список, цитата, таблица, hr, code)
        # vs «текстовый».
        block_prefixes = ("#", ">", "-", "*", "+", "1.", "```", "|", "---", "===")

        def is_block(p: str) -> bool:
            s = p.lstrip()
            if any(s.startswith(b) for b in block_prefixes):
                return True
            # многострочные списки: "- ...\n- ..."
            if "\n" in s and any(line.lstrip().startswith(("-", "*", "+"))
                                 for line in s.split("\n") if line.strip()):
                return True
            return False

        # Склеиваем ВСЕ подряд идущие «текстовые» параграфы между двумя
        # блочными в один большой абзац (PDF-импорты дают по 1 фразе на абзац).
        normalized: list[str] = []
        text_buffer: list[str] = []
        def flush_text() -> None:
            if not text_buffer:
                return
            joined = " ".join(text_buffer)
            joined = _re.sub(r"\s+", " ", joined).strip()
            if joined:
                normalized.append(joined)
            text_buffer.clear()

        for p in paragraphs:
            if is_block(p):
                flush_text()
                normalized.append(p)
            else:
                # многострочный текстовый — сначала схлопываем \n в пробелы
                p_clean = _re.sub(r"\s*\n\s*", " ", p).strip()
                if p_clean:
                    text_buffer.append(p_clean)
        flush_text()

        normalized_raw = "\n\n".join(normalized)
        return _md.markdown(
            normalized_raw,
            extensions=["extra", "sane_lists", "tables"],
        )
    except ImportError:
        from html import escape
        body = escape(path.read_text(encoding="utf-8"))
        return f"<pre>{body}</pre>"
    except Exception as e:
        print(f"[render] WARN: markdown parse failed for {path.name}: {e}", file=sys.stderr)
        return ""


def build_book_json(slug: str, meta: dict, artifacts_dir: Path) -> dict:
    """Сгенерировать meta.json для import в Astro.

    Помимо *_path, кладёт *_html — заранее отрендеренный markdown,
    чтобы Astro-шаблон мог показать контент через <Fragment set:html>
    (минуя <Content> из astro:content, который работает только для коллекций).
    """
    cover_file = find_cover(artifacts_dir)  # None если нет обложки
    cover_missing = cover_file is None
    # OG-картинка 1200×630 для соцсетей (генерится seo_optimize.py)
    og_image = f"/src/data/books/{slug}/og_image.jpg"
    if not (artifacts_dir / "og_image.jpg").exists():
        if (artifacts_dir / "og_image.svg").exists():
            og_image = f"/src/data/books/{slug}/og_image.svg"
        else:
            og_image = f"/src/data/books/{slug}/{cover_file}" if cover_file else None

    defs = [
        ("summary",     "summary.md"),
        ("tips",        "practical_tips.md"),
        ("reviews",     "reviews.md"),
        ("workbook",    "workbook.md"),
        ("buy_links",   "buy_links.md"),
    ]
    paths, htmls = {}, {}
    for key, fname in defs:
        p = artifacts_dir / fname
        paths[f"{key}_path"] = f"/src/data/books/{slug}/{fname}" if p.exists() else None
        htmls[f"{key}_html"] = _read_md_html(p)

    sci_p = artifacts_dir / "scientific.md"
    return {
        "slug": slug,
        "title": meta.get("title", ""),
        "author": meta.get("author", ""),
        "year": meta.get("year"),
        "isbn": meta.get("isbn"),
        "language": meta.get("language", "ru"),
        "summary_path":   paths["summary_path"],
        "tips_path":      paths["tips_path"],
        "reviews_path":   paths["reviews_path"],
        "workbook_path":  paths["workbook_path"],
        "buy_links_path": paths["buy_links_path"],
        "summary_html":   htmls["summary_html"],
        "tips_html":      htmls["tips_html"],
        "reviews_html":   htmls["reviews_html"],
        "workbook_html":  htmls["workbook_html"],
        "buy_links_html": htmls["buy_links_html"],
        # cover_path = None если обложки нет — Astro-шаблон покажет плейсхолдер
        "cover_path": f"/src/data/books/{slug}/{cover_file}" if cover_file else None,
        "cover_format": cover_file.rsplit(".", 1)[-1] if cover_file else None,
        "og_image_path": og_image,  # 1200×630 для VK/TG/Facebook
        "scientific_path": f"/src/data/books/{slug}/scientific.md" if sci_p.exists() else None,
        "scientific_html": _read_md_html(sci_p) if sci_p.exists() else "",
        "cover_missing": cover_missing,  # для шаблона — показать плейсхолдер
    }


def build_seo_bundle(
    slug: str,
    meta: dict,
    cover_file: str | None = None,
    *,
    generate_og: bool = True,
    og_dst_dir: "Path | None" = None,
) -> dict:
    """Генерация SEO-пакета через seo-advisor-skill интеграцию (v0.2+)."""
    cover_path = f"/src/data/books/{slug}/{cover_file}" if cover_file else f"/src/data/books/{slug}/cover.jpg"
    # Импортируем on-demand (избегаем циркулярных импортов)
    seo_script = Path(__file__).resolve().parent / "seo_optimize.py"
    if seo_script.exists():
        try:
            import importlib.util
            spec = importlib.util.spec_from_file_location("seo_optimize", seo_script)
            m = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(m)
            return m.build_seo_bundle(
                slug, meta,
                generate_og=generate_og,
                og_dst_dir=og_dst_dir,
            )
        except Exception as e:
            print(f"[render] WARN: seo_optimize.py не сработал ({e}). Fallback на stub.", file=sys.stderr)

    # Fallback (если seo_optimize.py не подгрузился)
    title = meta.get("title", "")
    author = meta.get("author", "")
    year = meta.get("year")
    isbn = meta.get("isbn")
    return {
        "title": f"{title} — конспект и практика | Лаборатория желаний",
        "description": f"Краткое содержание, практические советы и упражнения по книге «{title}» автора {author}.",
        "og_title": f"{title} — конспект и практика",
        "og_description": f"Краткое содержание, практические советы и упражнения по книге «{title}».",
        "og_image": cover_path,
        "og_type": "book",
        "twitter_card": "summary_large_image",
        "schema_book": {
            "@context": "https://schema.org",
            "@type": "Book",
            "name": title,
            "author": {"@type": "Person", "name": author},
            "datePublished": str(year) if year else None,
            "isbn": isbn,
            "image": cover_path,
            "inLanguage": meta.get("language", "ru"),
        },
        "schema_faqpage": None,
    }


def render_page(slug: str, meta: dict, dry_run: bool) -> Path:
    """Сгенерировать book-page.astro из шаблона."""
    template = TEMPLATES_DIR / "book-page-astro.astro"
    with open(template, "r", encoding="utf-8") as f:
        tpl = f.read()

    # Подстановка {slug} (минимальная — Astro-фронтматтер статичен)
    page = tpl.replace("{slug}", slug)

    if dry_run:
        dst = SKILL_ROOT / "tmp" / f"{slug}-preview" / f"{slug}.astro"
    else:
        dst = LAB_SITE_ROOT / "src" / "pages" / "books" / f"{slug}.astro"
    dst.parent.mkdir(parents=True, exist_ok=True)
    with open(dst, "w", encoding="utf-8") as f:
        f.write(page)
    return dst


def main():
    ap = argparse.ArgumentParser(description="Render WL artifacts → Astro page")
    ap.add_argument("slug")
    ap.add_argument("--dry-run", action="store_true", help="Не писать в lab_site, только в tmp/")
    ap.add_argument("--preview", action="store_true", help="Сгенерировать HTML-превью в tmp/")
    ap.add_argument("--skip-cover", default="warn",
                    choices=["strict", "warn", "allow"],
                    help="Политика обработки отсутствующей обложки: "
                         "strict=требовать (default в старом поведении), "
                         "warn=warning и продолжить, "
                         "allow=тихо продолжить")
    args = ap.parse_args()

    slug = args.slug
    print(f"[render] {slug}")

    # 1. Проверка артефактов
    ok, missing = check_artifacts(slug, skip_cover=args.skip_cover)
    if not ok:
        for m in missing:
            print(f"[render] ✗ {m}", file=sys.stderr)
        sys.exit(1)
    print(f"[render] ✓ все артефакты WL на месте")

    # 2. Metadata
    meta = load_metadata(slug)
    print(f"[render] ✓ metadata: {meta.get('title')} — {meta.get('author')}")

    # 3. Копия артефактов
    artifacts_dir = copy_artifacts(slug, dry_run=args.dry_run)
    print(f"[render] ✓ артефакты скопированы: {artifacts_dir}")

    # 3.5 OG-картинка 1200×630 для соцсетей (генерится ДО seo-bundle, чтобы
    # seo_optimize подхватил её и положил og_image_path в book.json)
    try:
        import importlib.util
        seo_script = Path(__file__).resolve().parent / "seo_optimize.py"
        spec = importlib.util.spec_from_file_location("seo_optimize", seo_script)
        seo_mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(seo_mod)
        og = seo_mod.generate_og_image(
            slug, meta.get("title", ""), meta.get("author", ""),
            genre=meta.get("genre", ""),
            dst_dir=artifacts_dir,  # ← пишем в artifacts_dir (включая dry-run)
        )
        if og:
            print(f"[render] ✓ OG-картинка: {og}")
        else:
            print(f"[render]   ℹ OG-картинка не сгенерирована (WL не отвечает или шаблон не найден)")
    except Exception as e:
        print(f"[render] WARN: OG-генерация не сработала: {e}", file=sys.stderr)

    # 4. meta.json
    book_json = build_book_json(slug, meta, artifacts_dir)
    meta_json_path = artifacts_dir.parent / f"{slug}.json"
    with open(meta_json_path, "w", encoding="utf-8") as f:
        json.dump(book_json, f, ensure_ascii=False, indent=2)
    print(f"[render] ✓ {meta_json_path.name}")
    if book_json.get("cover_missing"):
        print(f"[render]   ℹ обложка отсутствует (cover_path=null, в Astro-шаблоне будет плейсхолдер)")
    if book_json.get("og_image_path"):
        print(f"[render]   ℹ og_image_path = {book_json['og_image_path']}")

    # 5. SEO-bundle (OG уже сгенерирован на шаге 3.5 → отключаем повтор)
    cover_file = find_cover(artifacts_dir)
    seo = build_seo_bundle(
        slug, meta, cover_file=cover_file,
        generate_og=False,  # ← уже сделано на 3.5
        og_dst_dir=artifacts_dir,  # ← og_image_path в bundle указывает на artifacts_dir
    )
    seo_path = artifacts_dir / "seo-bundle.json"
    with open(seo_path, "w", encoding="utf-8") as f:
        json.dump(seo, f, ensure_ascii=False, indent=2)
    print(f"[render] ✓ seo-bundle.json")

    # 6. Astro-страница
    page_path = render_page(slug, meta, dry_run=args.dry_run)
    print(f"[render] ✓ {page_path}")

    # 7. State
    state.update(
        slug,
        status="rendered" if not args.dry_run else "preview",
        rendered_at=datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        page_path=str(page_path.relative_to(SKILL_ROOT.parent.parent)) if "lab_site" in str(page_path) else str(page_path),
        data_path=str(meta_json_path.relative_to(SKILL_ROOT.parent.parent)) if "lab_site" in str(meta_json_path) else str(meta_json_path),
        artifacts_dir=str(artifacts_dir.relative_to(SKILL_ROOT.parent.parent)) if "lab_site" in str(artifacts_dir) else str(artifacts_dir),
        seo_path=str(seo_path.relative_to(SKILL_ROOT.parent.parent)) if "lab_site" in str(seo_path) else str(seo_path),
    )
    print(f"[render] ✓ state обновлён")

    if args.dry_run:
        print(f"\n[render] DRY-RUN. Файлы в tmp/{slug}-preview/. Не записано в lab_site.")
    else:
        print(f"\n[render] Готово. Следующий шаг: deploy (scripts/deploy_pages.py {slug})")


if __name__ == "__main__":
    main()
