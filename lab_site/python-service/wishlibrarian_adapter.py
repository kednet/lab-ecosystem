"""
Адаптер WishLibrarian для python-service.

Импортирует WL из ../wish_librarian/agent/ (добавлен в sys.path в main.py).
Передаёт URL на обработку, читает результаты из output_dir, возвращает метаданные.

ВАЖНО: на Render.com файлы WishLibrarian (output/library/) существуют
временно — Worker забирает их через callback и кладёт в R2.
"""
from __future__ import annotations

import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

# Гарантируем, что можем импортировать WL
WISHLIBRARIAN_PATH = Path(__file__).resolve().parent.parent.parent / "wish_librarian"
if str(WISHLIBRARIAN_PATH) not in sys.path:
    sys.path.insert(0, str(WISHLIBRARIAN_PATH))


@dataclass
class BookResult:
    slug: str
    title: str
    author: str
    year: Optional[int]
    description: str
    cover: Optional[str]
    files: dict  # { 'summary': path, 'workbook': path, 'tips': path, 'cover': path | None }


def _slugify(text: str) -> str:
    """Транслит + lower + дефисы. Безопасный для URL."""
    # Минимальная транслитерация для русского
    table = {
        'а': 'a', 'б': 'b', 'в': 'v', 'г': 'g', 'д': 'd', 'е': 'e', 'ё': 'e',
        'ж': 'zh', 'з': 'z', 'и': 'i', 'й': 'i', 'к': 'k', 'л': 'l', 'м': 'm',
        'н': 'n', 'о': 'o', 'п': 'p', 'р': 'r', 'с': 's', 'т': 't', 'у': 'u',
        'ф': 'f', 'х': 'h', 'ц': 'ts', 'ч': 'ch', 'ш': 'sh', 'щ': 'shch',
        'ъ': '', 'ы': 'y', 'ь': '', 'э': 'e', 'ю': 'yu', 'я': 'ya',
    }
    out = []
    for ch in text.lower():
        if ch in table:
            out.append(table[ch])
        elif ch.isascii() and ch.isalnum():
            out.append(ch)
        elif ch in ' -_':
            out.append('-')
    s = ''.join(out)
    s = re.sub(r'-+', '-', s).strip('-')
    return s[:80] or 'book'


def _read_meta(meta_path: Path) -> dict:
    import json
    if not meta_path.exists():
        return {}
    try:
        return json.loads(meta_path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def process_book(url: str, output_dir: Path, progress_cb=None) -> BookResult:
    """Обработать книгу по URL через WishLibrarian.

    Args:
        url: URL книги (koob.ru, litres.ru, livelib и т.д.)
        output_dir: куда WL должен положить результат
        progress_cb: callable(stage: str, progress: 0-100, message: str) — для отчёта в Worker

    Returns:
        BookResult с метаданными и путями к файлам.
    """
    from agent.config import get_settings
    from agent.librarian import WishLibrarian

    if progress_cb:
        progress_cb("parsing", 5, "Запускаем парсер…")

    # Перенастроить WL на нужный output_dir
    settings = get_settings()
    settings.output_dir = output_dir
    # cache_dir по умолчанию PROJECT_ROOT/cache — оставим, он маленький

    librarian = WishLibrarian(settings)
    assets = librarian.process_book(url, force=True)

    if progress_cb:
        progress_cb("summary", 35, "Конспект готов, генерируем воркбук…")

    # process_book уже создал все файлы
    book = assets.book
    folder = Path(assets.folder) if assets.folder else output_dir

    if progress_cb:
        progress_cb("workbook", 70, "Воркбук готов, ищем обложку…")

    # Собрать пути к файлам
    summary_path = folder / "summary.md"
    workbook_path = folder / "workbook.md"
    tips_path = folder / "tips.md"
    cover_path = folder / "cover.jpg"
    meta_path = folder / "metadata.json"

    files = {}
    for key, p in [("summary", summary_path), ("workbook", workbook_path),
                    ("tips", tips_path), ("cover", cover_path)]:
        if p.exists() and p.stat().st_size > 0:
            files[key] = str(p)

    if progress_cb:
        progress_cb("done", 100, f"Готово: {book.title}")

    # Мета
    meta = _read_meta(meta_path)
    title = book.title or meta.get("title") or "Без названия"
    author = book.author or meta.get("author") or "Неизвестен"
    year = book.year or meta.get("year")
    description = book.description or meta.get("short_description") or meta.get("description") or ""

    # Slug — обязательно с префиксом gen-, чтобы не пересекаться со статическими книгами
    # в /library/{slug}/ (Astro SSG)
    base_slug = _slugify(f"{title}-{author}")
    slug = f"gen-{base_slug}"

    return BookResult(
        slug=slug,
        title=title,
        author=author,
        year=year,
        description=description,
        cover=files.get("cover"),
        files=files,
    )
