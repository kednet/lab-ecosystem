"""
backfill_cover.py — массовая генерация обложек для старых книг.

Для каждой книги в wish_librarian/output/library/<slug>/:
  • если есть `cover.jpg` / `cover.png` / `cover.svg` / `cover_local.svg` — пропускаем
  • иначе — генерируем обложку (SVG + JPG) + OG-картинку 1200×630
  • опционально — публикуем OG в lab_site/src/data/books/<slug>/og_image.jpg

Использование:
  python scripts/backfill_cover.py                       # все книги, кэш включён
  python scripts/backfill_cover.py --dry-run             # показать, что будет сделано
  python scripts/backfill_cover.py --force               # перегенерировать ВСЕ обложки
  python scripts/backfill_cover.py --no-og               # без OG-картинки
  python scripts/backfill_cover.py --publish             # публиковать в lab_site
  python scripts/backfill_cover.py --slugs "slug1,slug2" # только указанные
  python scripts/backfill_cover.py --workers 4           # параллелизм
"""
from __future__ import annotations

import argparse
import json
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Optional

# Корень wish_librarian → для импорта agent.cover
WL_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(WL_ROOT))

from agent.cover import CoverGenerator, CoverStyle  # noqa: E402
from agent.cover.png_export import svg_to_png       # noqa: E402
from agent.utils.logger import get_logger, setup_logging  # noqa: E402


try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass


logger = get_logger()

OUTPUT_ROOT = WL_ROOT / "output" / "library"
LAB_SITE_DATA = Path("C:/Users/kfigh/lab_site/src/data/books")
COVER_CANDIDATES = ("cover.jpg", "cover.png", "cover.svg", "cover_local.svg")
OG_CANDIDATES = ("og_image.jpg", "og_image.svg")


# ── Утилиты ────────────────────────────────────────────────────────
def has_cover(folder: Path) -> bool:
    """True если в папке уже есть обложка (любой поддерживаемый формат)."""
    return any((folder / n).exists() for n in COVER_CANDIDATES)


def has_og(folder: Path) -> bool:
    return any((folder / n).exists() for n in OG_CANDIDATES)


def has_og_lab_site(slug: str) -> bool:
    """Есть ли уже og_image.{jpg,svg} в lab_site/src/data/books/<slug>/."""
    dst = LAB_SITE_DATA / slug
    return any((dst / n).exists() for n in OG_CANDIDATES)


def load_metadata(folder: Path) -> Optional[dict]:
    """Прочитать metadata.json, если есть."""
    p = folder / "metadata.json"
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception as e:
        logger.warning("metadata.json невалиден в {}: {}", folder.name, e)
        return None


# ── Генерация обложки ─────────────────────────────────────────────
def generate_cover_for_slug(
    slug: str,
    *,
    cover_gen: CoverGenerator,
    force: bool = False,
    with_og: bool = True,
    publish_to_lab_site: bool = False,
    cover_format: str = "jpg",
) -> dict:
    """
    Сгенерировать обложку (+ опц. OG) для одной книги.

    Returns: {"slug", "status", "cover", "og", "error"}
    """
    folder = OUTPUT_ROOT / slug
    if not folder.exists():
        return {"slug": slug, "status": "skip", "error": "folder missing"}
    meta = load_metadata(folder)
    if not meta:
        return {"slug": slug, "status": "skip", "error": "metadata.json missing"}

    title  = meta.get("title") or slug
    author = meta.get("author") or "—"
    genre  = meta.get("genre") or ""

    result = {"slug": slug, "title": title, "cover": None, "og": None, "error": None}

    # ── Обложка ────────────────────────────────────────────────
    if force or not has_cover(folder):
        try:
            style = cover_gen.detect_style_from_text(genre + " " + title)
            cover_res = cover_gen.generate(
                title=title, author=author, genre=genre, style=style,
            )
            svg_path = folder / "cover_local.svg"
            svg_path.write_bytes(cover_res["svg"])
            result["cover"] = str(svg_path.relative_to(folder))
            logger.info("  ✓ cover_local.svg ({} KB)", svg_path.stat().st_size // 1024)

            # JPG-конвертация
            if cover_format in ("jpg", "both"):
                jpg_out = svg_to_png(
                    cover_res["svg"], folder / "cover",
                    width=800, height=1200, output_format="jpg", timeout_sec=45,
                )
                if jpg_out:
                    result["cover_jpg"] = str(jpg_out.relative_to(folder))
                    logger.info("  ✓ cover.jpg ({} KB)", jpg_out.stat().st_size // 1024)
        except Exception as e:
            result["error"] = f"cover: {e}"
            logger.error("  ✗ обложка: {}", e)
    else:
        result["cover"] = "exists"
        logger.info("  · обложка уже есть — пропускаю")

    # ── OG 1200×630 ────────────────────────────────────────────
    if with_og and (force or not has_og(folder)):
        try:
            og_res = cover_gen.generate_og(title=title, author=author, genre=genre)
            og_svg = folder / "og_image.svg"
            og_svg.write_bytes(og_res["svg"])
            og_jpg = svg_to_png(
                og_res["svg"], folder / "og_image",
                width=1200, height=630, output_format="jpg", timeout_sec=45,
            )
            if og_jpg:
                og_svg.unlink(missing_ok=True)
                result["og"] = str(og_jpg.relative_to(folder))
                logger.info("  ✓ og_image.jpg ({} KB)", og_jpg.stat().st_size // 1024)

                # Публикация в lab_site
                if publish_to_lab_site:
                    dst = LAB_SITE_DATA / slug
                    dst.mkdir(parents=True, exist_ok=True)
                    target = dst / og_jpg.name
                    target.write_bytes(og_jpg.read_bytes())
                    logger.info("  ↗ опубликовано в lab_site: {}", target.name)
        except Exception as e:
            result["error"] = (result.get("error") or "") + f" og: {e}"
            logger.error("  ✗ OG: {}", e)
    elif with_og:
        result["og"] = "exists"
        logger.info("  · OG уже есть — пропускаю")

    # ── Publish-only: скопировать существующую обложку/OG в lab_site ─
    if publish_to_lab_site and not has_og_lab_site(slug):
        og_src = None
        for name in OG_CANDIDATES:
            cand = folder / name
            if cand.exists():
                og_src = cand
                break
        if og_src:
            dst = LAB_SITE_DATA / slug
            dst.mkdir(parents=True, exist_ok=True)
            target = dst / og_src.name
            target.write_bytes(og_src.read_bytes())
            logger.info("  ↗ OG опубликован (existing): {}", target.name)

    return result


# ── Main ──────────────────────────────────────────────────────────
def main():
    ap = argparse.ArgumentParser(description="Backfill book covers for old books")
    ap.add_argument("--dry-run", action="store_true",
                    help="Показать, какие книги требуют обложки, без записи")
    ap.add_argument("--force", action="store_true",
                    help="Перегенерировать ВСЕ обложки (даже если есть)")
    ap.add_argument("--no-og", action="store_true",
                    help="Не генерировать OG-картинки")
    ap.add_argument("--publish", action="store_true",
                    help="Публиковать og_image.jpg в lab_site/src/data/books/<slug>/")
    ap.add_argument("--slugs", type=str, default=None,
                    help="Фильтр: только указанные slug-и (через запятую)")
    ap.add_argument("--workers", type=int, default=2,
                    help="Количество параллельных воркеров (default: 2)")
    ap.add_argument("--cover-format", default="jpg", choices=["jpg", "svg", "both"],
                    help="Формат обложки: jpg (через Playwright) | svg | both")
    args = ap.parse_args()

    setup_logging()
    logger.info("🚀 backfill_cover: dry_run={} force={} og={} publish={} format={}",
                args.dry_run, args.force, not args.no_og, args.publish, args.cover_format)

    if not OUTPUT_ROOT.exists():
        logger.error("✗ Папка не найдена: {}", OUTPUT_ROOT)
        sys.exit(1)

    # Список книг
    all_folders = sorted(p for p in OUTPUT_ROOT.iterdir() if p.is_dir())
    if args.slugs:
        wanted = {s.strip() for s in args.slugs.split(",") if s.strip()}
        all_folders = [p for p in all_folders if p.name in wanted]
        if not all_folders:
            logger.error("✗ Ни одна папка не совпала с --slugs")
            sys.exit(1)

    # Разделяем на нуждающиеся / не нуждающиеся
    need_cover, has_already = [], []
    for p in all_folders:
        need_backfill = args.force or not has_cover(p) or (not args.no_og and not has_og(p))
        # --publish добавляет книги, у которых OG есть локально, но не опубликован
        need_publish = args.publish and not has_og_lab_site(p.name)
        if need_backfill or need_publish:
            need_cover.append(p)
        else:
            has_already.append(p)

    logger.info("📚 Всего: {} | уже с обложкой: {} | требуют backfill: {}",
                len(all_folders), len(has_already), len(need_cover))

    if args.dry_run:
        logger.info("\n📋 DRY-RUN: будут обработаны:")
        for p in need_cover:
            meta = load_metadata(p)
            title = meta.get("title", "?") if meta else "?"
            has_c = "✓" if has_cover(p) else "✗"
            has_o = "✓" if has_og(p) else "✗"
            logger.info("  {} cover={} og={}  «{}»", p.name, has_c, has_o, title)
        return

    if not need_cover:
        logger.info("🎉 Все книги уже с обложкой и OG — нечего делать")
        return

    # Генерация
    cover_gen = CoverGenerator()
    logger.info("▶ Старт генерации ({} воркеров)…", args.workers)
    success, failed = 0, 0

    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = {
            pool.submit(
                generate_cover_for_slug,
                p.name,
                cover_gen=cover_gen,
                force=args.force,
                with_og=not args.no_og,
                publish_to_lab_site=args.publish,
                cover_format=args.cover_format,
            ): p for p in need_cover
        }
        for fut in as_completed(futures):
            r = fut.result()
            slug = r.get("slug", "?")
            if r.get("error"):
                failed += 1
                logger.error("✗ {}: {}", slug, r["error"])
            else:
                success += 1
                logger.info("✓ {}: cover={} og={}",
                            slug, r.get("cover"), r.get("og"))

    logger.info("\n📊 Итого: ✓ {} | ✗ {}", success, failed)
    if failed:
        sys.exit(1)


if __name__ == "__main__":
    main()
