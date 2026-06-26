"""
FileManager — создание папок, сохранение файлов, проверка дубликатов.
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Optional, Union

from agent.config import get_settings
from agent.models import BookInfo
from agent.utils.logger import get_logger


logger = get_logger()


class FileManager:
    """Менеджер файловой системы для библиотеки."""

    def __init__(self):
        self.settings = get_settings()

    # ── Пути ────────────────────────────────────────────────────
    def book_folder(self, book: BookInfo) -> Path:
        """Возвращает путь к папке книги (создаёт, если нужно)."""
        folder = self.settings.output_dir / book.folder_name()
        folder.mkdir(parents=True, exist_ok=True)
        (folder / "raw").mkdir(parents=True, exist_ok=True)
        return folder

    def raw_html_path(self, book: BookInfo) -> Path:
        return self.book_folder(book) / "raw" / "source.html"

    # ── Сохранение ──────────────────────────────────────────────
    def write_text(
        self,
        path: Union[str, Path],
        content: str,
        *,
        encoding: str = "utf-8",
    ) -> Path:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding=encoding)
        logger.debug("💾 Записан: {} ({} байт)", path, len(content))
        return path

    def write_json(
        self,
        path: Union[str, Path],
        data: Any,
        *,
        encoding: str = "utf-8",
        ensure_ascii: bool = False,
    ) -> Path:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(data, ensure_ascii=ensure_ascii, indent=2, default=str),
            encoding=encoding,
        )
        logger.debug("💾 JSON записан: {}", path)
        return path

    def write_binary(self, path: Union[str, Path], data: bytes) -> Path:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        logger.debug("💾 Бинарь записан: {} ({} байт)", path, len(data))
        return path

    # ── Проверка дубликатов ─────────────────────────────────────
    def is_processed(self, book: BookInfo) -> bool:
        """Книга считается обработанной, если уже есть summary.md."""
        folder = self.settings.output_dir / book.folder_name()
        marker = folder / "summary.md"
        if marker.exists() and marker.stat().st_size > 200:
            logger.info("⏭  Книга уже обработана: {}", folder)
            return True
        return False

    def find_existing_by_fingerprint(self, book: BookInfo):
        """
        Ищет уже обработанную книгу по каноническому отпечатку
        (ISBN → (title+author+year)). Сканирует все metadata.json.

        Возвращает Path к папке или None.
        """
        from agent.utils.normalize import book_fingerprint
        target_fp = book_fingerprint(book.title, book.author, book.year, book.isbn)
        if not self.settings.output_dir.exists():
            return None
        for md in self.settings.output_dir.glob("*/metadata.json"):
            try:
                import json
                data = json.loads(md.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                continue
            existing_fp = book_fingerprint(
                data.get("title"),
                data.get("author"),
                data.get("year"),
                data.get("isbn"),
            )
            if existing_fp == target_fp:
                logger.info(
                    "♻️  Дубль по отпечатку: {} → {}",
                    target_fp, md.parent.name,
                )
                return md.parent
        return None

    def force_reprocess(self, book: BookInfo) -> None:
        """Удалить папку, чтобы перепарсить."""
        folder = self.settings.output_dir / book.folder_name()
        if folder.exists():
            import shutil
            shutil.rmtree(folder, ignore_errors=True)
            logger.warning("♻️  Папка удалена для переобработки: {}", folder)
