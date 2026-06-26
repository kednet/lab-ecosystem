"""
Пост-обработка импортированных PDF-конспектов.

Для каждой подпапки ``output/library/<Книга>`` с уже заполненными
``summary.md``/``workbook.md``/``metadata.json`` догенерирует:

  - ``practical_tips.md``  — через LLM (YandexGPT, шаблон tips_v1)
  - ``buy_links.md``       — Литрес/Лабиринт/Ozon (без сети, чистые ссылки)
  - ``cover.jpg``          — обложка из Open Library (по title+author) или
                              первая страница исходного PDF (fallback)
  - ``reviews.md``         — парсер LiveLib + koob.ru (нужен сеть)
  - ``scientific.md``      — парсер КиберЛенинки (нужен сеть)

Файлы, которые уже есть, **пропускаются** (используйте ``--force``
для перезаписи).

Использование:
    source .venv/Scripts/activate
    python -X utf8 scripts/postprocess_imported.py
    python -X utf8 scripts/postprocess_imported.py --skip-network     # только tips+buy_links+cover
    python -X utf8 scripts/postprocess_imported.py --folder "Конкретная_папка"
    python -X utf8 scripts/postprocess_imported.py --force            # перезаписывать всё
    python -X utf8 scripts/postprocess_imported.py --dry-run
"""
from __future__ import annotations

import argparse
import json
import sys
from io import BytesIO
from pathlib import Path
from typing import Optional, Tuple
from urllib.parse import quote_plus

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import requests  # noqa: E402

from agent.config import get_settings  # noqa: E402
from agent.librarian import WishLibrarian  # noqa: E402
from agent.models import BookInfo  # noqa: E402
from agent.utils.logger import get_logger, setup_logging  # noqa: E402

logger = get_logger()

# Конфиг скачивания обложек
COVER_TIMEOUT = 15  # секунд на один источник
COVER_MIN_SIZE = 1024  # 1 КБ — отсекаем битые / placeholder
OPEN_LIBRARY_URL = "https://covers.openlibrary.org/b/title/{key}-L.jpg?default=false"


def _load_book_info(folder: Path) -> Optional[BookInfo]:
    meta_path = folder / "metadata.json"
    if not meta_path.exists():
        return None
    try:
        data = json.loads(meta_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    title = (data.get("title") or "").strip()
    author = (data.get("author") or "—").strip()
    if not title:
        return None
    return BookInfo(
        title=title,
        author=author or "—",
        source_url=data.get("source_file", "external://imported"),
    )


def _has(folder: Path, name: str) -> bool:
    p = folder / name
    if not p.exists():
        return False
    try:
        return p.stat().st_size > 50  # 50 байт — отсекаем совсем пустые
    except OSError:
        return False


# ── Обложки ────────────────────────────────────────────────────────
def _download_cover_openlibrary(title: str, author: str) -> Optional[bytes]:
    """Попробовать скачать обложку с Open Library по title."""
    # Open Library принимает title в URL, без автора
    key = quote_plus(title)
    url = OPEN_LIBRARY_URL.format(key=key)
    try:
        r = requests.get(url, timeout=COVER_TIMEOUT, allow_redirects=True)
        if r.status_code == 200 and len(r.content) > COVER_MIN_SIZE:
            # Проверяем, что это JPEG (магические байты \xff\xd8)
            if r.content[:2] == b"\xff\xd8":
                return r.content
    except requests.RequestException as e:
        logger.debug("OpenLibrary: {}", e)
    return None


def _extract_first_pdf_page(pdf_path: Path) -> Optional[bytes]:
    """Рендер первой страницы PDF в JPEG (fallback, без внешних утилит)."""
    try:
        import pypdfium2 as pdfium
    except ImportError:
        return None
    try:
        pdf = pdfium.PdfDocument(str(pdf_path))
        if not pdf:
            return None
        page = pdf[0]
        img = page.render(scale=1.5).to_pil()
        buf = BytesIO()
        img.convert("RGB").save(buf, format="JPEG", quality=85)
        data = buf.getvalue()
        if len(data) > COVER_MIN_SIZE and data[:2] == b"\xff\xd8":
            return data
    except Exception as e:
        logger.debug("PDF first page: {}", e)
    return None


def _cover_already_ok(folder: Path) -> bool:
    p = folder / "cover.jpg"
    if not p.exists():
        return False
    try:
        return p.stat().st_size > COVER_MIN_SIZE
    except OSError:
        return False


def _download_cover(book: BookInfo, folder: Path) -> str:
    """Скачать обложку. Возвращает статус."""
    cover_path = folder / "cover.jpg"

    # 1) Open Library (по title)
    if book.title and book.title != "—":
        data = _download_cover_openlibrary(book.title, book.author or "")
        if data:
            cover_path.write_bytes(data)
            logger.success("🖼  OpenLibrary: {} ({} KB)", cover_path.name, len(data) // 1024)
            return "openlibrary"

    # 2) Fallback: первая страница исходного PDF
    pdf_path = folder / "source.pdf"
    if pdf_path.exists():
        data = _extract_first_pdf_page(pdf_path)
        if data:
            cover_path.write_bytes(data)
            logger.success("🖼  PDF cover: {} ({} KB)", cover_path.name, len(data) // 1024)
            return "pdf-page"

    # 3) Ничего не нашли — ставим заглушку
    note = folder / "cover.jpg.note.md"
    if not note.exists():
        note.write_text(
            f"# 🖼 Обложка не найдена\n\n"
            f"**Книга:** {book.title}\n"
            f"**Автор:** {book.author}\n\n"
            f"_Open Library не нашёл обложки для этого издания. "
            f"Положите JPG вручную: `{cover_path}`_\n",
            encoding="utf-8",
        )
    return "missing"


def process_one(
    folder: Path,
    wl: WishLibrarian,
    *,
    skip_network: bool,
    force: bool,
) -> dict:
    stats = {
        "tips": "skip",
        "buy_links": "skip",
        "cover": "skip",
        "reviews": "skip",
        "scientific": "skip",
        "errors": 0,
    }
    book = _load_book_info(folder)
    if book is None:
        logger.warning("⏭  {}: нет metadata.json с title/author", folder.name)
        return stats

    # ── 1. tips (через LLM) ────────────────────────────────────
    summary_path = folder / "summary.md"
    if force or not _has(folder, "practical_tips.md"):
        try:
            res = wl._generate_tips(
                book,
                folder,
                str(summary_path) if summary_path.exists() else None,
            )
            stats["tips"] = "ok" if res else "fallback"
        except Exception as e:
            logger.error("💥 tips: {}", e)
            stats["tips"] = "error"
            stats["errors"] += 1
    else:
        stats["tips"] = "exists"

    # ── 2. buy_links (без сети) ────────────────────────────────
    if force or not _has(folder, "buy_links.md"):
        try:
            res = wl._generate_buy_links(book, folder)
            stats["buy_links"] = "ok" if res else "ok-empty"
        except Exception as e:
            logger.error("💥 buy_links: {}", e)
            stats["buy_links"] = "error"
            stats["errors"] += 1
    else:
        stats["buy_links"] = "exists"

    # ── 3. cover (Open Library; не требует LLM, но нужна сеть) ──
    if force or not _cover_already_ok(folder):
        try:
            stats["cover"] = _download_cover(book, folder)
        except Exception as e:
            logger.error("💥 cover: {}", e)
            stats["cover"] = "error"
            stats["errors"] += 1
    else:
        stats["cover"] = "exists"

    # ── 4. reviews (нужна сеть) ───────────────────────────────
    if not skip_network:
        if force or not _has(folder, "reviews.md"):
            try:
                res = wl._collect_reviews(book, folder)
                stats["reviews"] = "ok" if res else "ok-empty"
            except Exception as e:
                logger.error("💥 reviews: {}", e)
                stats["reviews"] = "error"
                stats["errors"] += 1
        else:
            stats["reviews"] = "exists"

        # ── 5. scientific (нужна сеть) ──────────────────────────
        if force or not _has(folder, "scientific.md"):
            try:
                res = wl._search_scientific_articles(book, folder)
                stats["scientific"] = "ok" if res else "ok-empty"
            except Exception as e:
                logger.error("💥 scientific: {}", e)
                stats["scientific"] = "error"
                stats["errors"] += 1
        else:
            stats["scientific"] = "exists"

    return stats


def main() -> int:
    p = argparse.ArgumentParser(description="Пост-обработка импортированных PDF")
    p.add_argument("--folder", type=Path, default=None,
                   help="Одна папка (по умолчанию: весь output/library)")
    p.add_argument("--skip-network", action="store_true",
                   help="Не обращаться к LiveLib/КиберЛенинке (только tips + buy_links)")
    p.add_argument("--force", action="store_true",
                   help="Перезаписывать уже существующие файлы")
    p.add_argument("--dry-run", action="store_true",
                   help="Только показать план")
    p.add_argument("--source-only", action="store_true",
                   help="Обрабатывать только книги, импортированные из PDF (template_summary=external)")
    args = p.parse_args()

    setup_logging()
    settings = get_settings()
    output_dir = settings.output_dir
    logger.info("🚀 Пост-обработка: {}", output_dir)
    logger.info("   skip_network={}  force={}  source_only={}  dry_run={}",
                args.skip_network, args.force, args.source_only, args.dry_run)

    if not output_dir.exists():
        logger.error("❌ Папка не найдена: {}", output_dir)
        return 2

    # Список папок
    if args.folder:
        folders = [args.folder]
    else:
        folders = sorted([d for d in output_dir.iterdir() if d.is_dir()])

    # Фильтр «только импортированные»
    if args.source_only:
        filtered = []
        for f in folders:
            meta = f / "metadata.json"
            if meta.exists():
                try:
                    data = json.loads(meta.read_text(encoding="utf-8"))
                    if data.get("source") == "external_pdf" or data.get("template_summary") == "external":
                        filtered.append(f)
                except (OSError, ValueError):
                    continue
        folders = filtered

    logger.info("📂 Папок к обработке: {}", len(folders))

    if args.dry_run:
        for f in folders:
            tips = "✓" if _has(f, "practical_tips.md") else "—"
            buy = "✓" if _has(f, "buy_links.md") else "—"
            cov = "✓" if _cover_already_ok(f) else "—"
            rev = "✓" if _has(f, "reviews.md") else "—"
            sci = "✓" if _has(f, "scientific.md") else "—"
            logger.info("  {}  tips={} buy={} cover={} reviews={} sci={}",
                        f.name, tips, buy, cov, rev, sci)
        return 0

    # Инициализация WishLibrarian (ленивая, без HTTP)
    logger.info("🛠  Инициализация WishLibrarian (без парсинга URL)…")
    wl = WishLibrarian(
        template_summary=settings.template_summary,
        template_workbook=settings.template_workbook,
    )

    # Статистика
    totals = {"tips": 0, "buy_links": 0, "cover": 0, "reviews": 0, "scientific": 0, "errors": 0}
    skipped = 0
    for i, folder in enumerate(folders, 1):
        logger.info("")
        logger.info("━━━ [{}/{}] ━━━ {}", i, len(folders), folder.name)
        # Быстрый skip: если всё есть и не --force
        if not args.force:
            needed = ["practical_tips.md", "buy_links.md", "cover.jpg"]
            if not args.skip_network:
                needed += ["reviews.md", "scientific.md"]
            if all((_has(folder, n) if n != "cover.jpg" else _cover_already_ok(folder)) for n in needed):
                logger.info("⏭  Всё уже сгенерировано, пропуск")
                skipped += 1
                continue

        s = process_one(
            folder, wl,
            skip_network=args.skip_network,
            force=args.force,
        )
        for k in ("tips", "buy_links", "reviews", "scientific"):
            if s.get(k) in ("ok", "ok-empty", "fallback"):
                totals[k] += 1
        if s.get("cover") in ("openlibrary", "pdf-page"):
            totals["cover"] += 1
        totals["errors"] += s.get("errors", 0)
        logger.info("   → {}", s)

    logger.info("")
    logger.info("═══════════════════════════════════════")
    logger.info("✅ tips:        {}", totals["tips"])
    logger.info("✅ buy_links:   {}", totals["buy_links"])
    logger.info("✅ cover:       {}", totals["cover"])
    logger.info("✅ reviews:     {}", totals["reviews"])
    logger.info("✅ scientific:  {}", totals["scientific"])
    logger.info("⏭  Пропущено:   {} (всё уже есть)", skipped)
    logger.info("❌ Ошибок:      {}", totals["errors"])
    logger.info("═══════════════════════════════════════")
    return 0 if totals["errors"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
