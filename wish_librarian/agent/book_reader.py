"""
Читалка книг в локальных форматах: .txt, .fb2, .epub, .pdf (опционально).

Используется, когда пользователь сам скачивает книгу и кладёт в
``books_input/`` (а не парсит koob.ru).

Возвращает dict:
    {
        "title": str,
        "author": str,
        "text": str,         # полный текст (без XML-разметки)
        "chapters": [str],   # список заголовков глав (если есть)
        "format": str,       # "txt" | "fb2" | "epub" | "pdf"
    }
"""
from __future__ import annotations

import re
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Optional

from agent.utils.logger import get_logger

logger = get_logger()


# ── Публичный API ───────────────────────────────────────────────────
def read_book(path: str | Path) -> dict:
    """Прочитать книгу из локального файла. Поддерживает txt/fb2/epub/pdf.

    Args:
        path: абсолютный или относительный путь к файлу.

    Returns:
        dict с полями title/author/text/chapters/format.

    Raises:
        FileNotFoundError: файл не существует.
        ValueError: формат не поддерживается.
    """
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"Файл не найден: {p}")
    ext = p.suffix.lower().lstrip(".")
    if ext not in ("txt", "fb2", "epub", "pdf"):
        raise ValueError(f"Формат «.{ext}» не поддерживается. Используйте .txt, .fb2, .epub или .pdf")
    raw = p.read_bytes()
    if ext == "txt":
        return _read_txt(raw, p)
    if ext == "fb2":
        return _read_fb2(raw, p)
    if ext == "epub":
        return _read_epub(raw, p)
    if ext == "pdf":
        return _read_pdf(raw, p)
    raise ValueError(f"Формат «.{ext}» не реализован")  # pragma: no cover


def list_books(books_dir: str | Path = "books_input") -> list[Path]:
    """Список всех книг в папке (для команды ``/books``)."""
    d = Path(books_dir)
    if not d.exists():
        return []
    out: list[Path] = []
    for ext in ("*.txt", "*.fb2", "*.epub", "*.pdf", "*.TXT", "*.FB2", "*.EPUB", "*.PDF"):
        out.extend(d.glob(ext))
    return sorted(set(out), key=lambda p: p.stat().st_mtime, reverse=True)


# ── TXT ─────────────────────────────────────────────────────────────
def _read_txt(raw: bytes, p: Path) -> dict:
    # Пробуем несколько кодировок
    text = None
    for enc in ("utf-8", "cp1251", "koi8-r", "latin-1"):
        try:
            text = raw.decode(enc)
            break
        except UnicodeDecodeError:
            continue
    if text is None:
        text = raw.decode("utf-8", errors="ignore")
    # Извлекаем название и автора из первых строк
    title, author = _extract_title_author_from_text(text)
    chapters = _split_into_chapters(text)
    return {
        "title": title or p.stem,
        "author": author or "—",
        "text": text.strip(),
        "chapters": chapters,
        "format": "txt",
    }


def _extract_title_author_from_text(text: str) -> tuple[str, str]:
    """Попробовать найти «Title: X» / «Автор: Y» в первых 20 строках."""
    head = "\n".join(text.splitlines()[:20])
    title = ""
    author = ""
    m = re.search(r"(?:Title|Название|Заголовок|Книга)\s*[:\-—]\s*(.+)", head, re.IGNORECASE)
    if m:
        title = m.group(1).strip()
    m = re.search(r"(?:Author|Автор)\s*[:\-—]\s*(.+)", head, re.IGNORECASE)
    if m:
        author = m.group(1).strip()
    return title, author


# ── FB2 (FictionBook 2.0) ──────────────────────────────────────────
def _read_fb2(raw: bytes, p: Path) -> dict:
    # FB2 — это XML. namespace обязателен.
    text: Optional[str] = None
    for enc in ("utf-8", "cp1251"):
        try:
            text = raw.decode(enc)
            break
        except UnicodeDecodeError:
            continue
    if text is None:
        text = raw.decode("utf-8", errors="ignore")
    # Удаляем default-namespace, чтобы не возиться с {http://...}book
    text = re.sub(r'\sxmlns="[^"]+"', "", text, count=1)
    text = re.sub(r"\sxmlns:[a-zA-Z]+=\"[^\"]+\"", "", text)
    try:
        root = ET.fromstring(text)
    except ET.ParseError as e:
        logger.warning("FB2: не удалось распарсить XML, берём как plain text: {}", e)
        plain = re.sub(r"<[^>]+>", "", text)
        return {
            "title": p.stem,
            "author": "—",
            "text": plain.strip(),
            "chapters": [],
            "format": "fb2",
        }
    ns = ""  # namespace удалён
    # Title
    title_el = root.find(f".//{ns}book-title")
    title = title_el.text.strip() if title_el is not None and title_el.text else p.stem
    # Author
    author_el = root.find(f".//{ns}author")
    author = "—"
    if author_el is not None:
        first = author_el.find(f"{ns}first-name")
        last = author_el.find(f"{ns}last-name")
        middle = author_el.find(f"{ns}middle-name")
        parts = []
        if first is not None and first.text:
            parts.append(first.text.strip())
        if middle is not None and middle.text:
            parts.append(middle.text.strip())
        if last is not None and last.text:
            parts.append(last.text.strip())
        if parts:
            author = " ".join(parts)
        else:
            nick = author_el.find(f"{ns}nickname")
            if nick is not None and nick.text:
                author = nick.text.strip()
    # Sections: каждый <section> верхнего уровня — глава
    body = root.find(f".//{ns}body")
    chapters: list[str] = []
    paragraphs: list[str] = []
    if body is not None:
        for section in body.findall(f"./{ns}section"):
            ch_title_el = section.find(f"{ns}title/{ns}p")
            ch_title = ch_title_el.text.strip() if ch_title_el is not None and ch_title_el.text else ""
            if not ch_title:
                # Попробуем plain text первого <p>
                first_p = section.find(f".//{ns}p")
                if first_p is not None and first_p.text:
                    ch_title = first_p.text.strip()[:60]
            if ch_title:
                chapters.append(ch_title)
            # Соберём все <p> внутри
            for p_el in section.findall(f".//{ns}p"):
                txt = "".join(p_el.itertext()).strip()
                if txt:
                    paragraphs.append(txt)
    full_text = "\n\n".join(paragraphs)
    return {
        "title": title,
        "author": author,
        "text": full_text,
        "chapters": chapters,
        "format": "fb2",
    }


# ── EPUB (распаковка ZIP → XHTML) ─────────────────────────────────
def _read_epub(raw: bytes, p: Path) -> dict:
    title = p.stem
    author = "—"
    chapters: list[str] = []
    paragraphs: list[str] = []
    try:
        with zipfile.ZipFile(p) as z:
            # container.xml → path to OPF
            try:
                container = z.read("META-INF/container.xml").decode("utf-8", errors="ignore")
                opf_path_m = re.search(r'full-path="([^"]+\.opf)"', container)
                if not opf_path_m:
                    raise ValueError("OPF not found in container.xml")
                opf_path = opf_path_m.group(1)
                opf = z.read(opf_path).decode("utf-8", errors="ignore")
                # Title & author
                m = re.search(r"<dc:title[^>]*>([^<]+)</dc:title>", opf)
                if m:
                    title = m.group(1).strip()
                m = re.search(r"<dc:creator[^>]*>([^<]+)</dc:creator>", opf)
                if m:
                    author = m.group(1).strip()
                # Все xhtml/html в порядке spine
                spine_ids = re.findall(r'<itemref[^>]+idref="([^"]+)"', opf)
                items = dict(re.findall(r'<item[^>]+id="([^"]+)"[^>]+href="([^"]+)"', opf))
                for sid in spine_ids:
                    href = items.get(sid)
                    if not href:
                        continue
                    full = str(Path(opf_path).parent / href)
                    try:
                        xhtml = z.read(full).decode("utf-8", errors="ignore")
                    except KeyError:
                        continue
                    # Title
                    t = re.search(r"<title[^>]*>([^<]+)</title>", xhtml)
                    if t:
                        chapters.append(t.group(1).strip())
                    # Paragraphs
                    for p_el in re.finditer(r"<p[^>]*>(.+?)</p>", xhtml, re.DOTALL):
                        para = re.sub(r"<[^>]+>", "", p_el.group(1))
                        para = re.sub(r"\s+", " ", para).strip()
                        if para and len(para) > 1:
                            paragraphs.append(para)
            except (KeyError, ValueError) as e:
                logger.warning("EPUB: структура нестандартная, fallback: {}", e)
                # Fallback: читаем все .xhtml/.html
                for name in z.namelist():
                    if name.endswith((".xhtml", ".html", ".htm")):
                        try:
                            xhtml = z.read(name).decode("utf-8", errors="ignore")
                        except Exception:
                            continue
                        for p_el in re.finditer(r"<p[^>]*>(.+?)</p>", xhtml, re.DOTALL):
                            para = re.sub(r"<[^>]+>", "", p_el.group(1))
                            para = re.sub(r"\s+", " ", para).strip()
                            if para and len(para) > 1:
                                paragraphs.append(para)
    except zipfile.BadZipFile as e:
        raise ValueError(f"EPUB повреждён: {e}")
    full_text = "\n\n".join(paragraphs)
    return {
        "title": title,
        "author": author,
        "text": full_text,
        "chapters": chapters,
        "format": "epub",
    }


# ── PDF (опционально, через pypdf) ─────────────────────────────────
def _read_pdf(raw: bytes, p: Path) -> dict:
    try:
        import pypdf  # type: ignore
    except ImportError:
        raise ValueError("PDF требует пакет pypdf: pip install pypdf")
    try:
        import io
        reader = pypdf.PdfReader(io.BytesIO(raw))
        paragraphs: list[str] = []
        for page in reader.pages:
            try:
                txt = page.extract_text() or ""
            except Exception:
                continue
            # Простая очистка
            txt = re.sub(r"[\x00-\x08\x0b-\x0c\x0e-\x1f]", "", txt)
            for para in re.split(r"\n\s*\n", txt):
                para = para.strip()
                if para and len(para) > 1:
                    paragraphs.append(para)
        # Title / author — берём из метаданных
        meta = reader.metadata or {}
        title = (meta.get("/Title") or p.stem).strip()
        author = (meta.get("/Author") or "—").strip()
        return {
            "title": title,
            "author": author,
            "text": "\n\n".join(paragraphs),
            "chapters": [],
            "format": "pdf",
        }
    except Exception as e:
        raise ValueError(f"Не удалось прочитать PDF: {e}")


# ── Утилиты ─────────────────────────────────────────────────────────
def _split_into_chapters(text: str) -> list[str]:
    """Грубая эвристика: главы выделены строками 'Глава N', 'Часть N' или '## '."""
    chapters: list[str] = []
    for line in text.splitlines():
        s = line.strip()
        if not s or len(s) > 120:
            continue
        if re.match(r"^(Глава|Часть|ГЛАВА|ЧАСТЬ|CHAPTER)\s+[IVX0-9]+", s, re.IGNORECASE):
            chapters.append(s)
        elif s.startswith("## "):
            chapters.append(s.lstrip("# ").strip())
    return chapters


def truncate_for_llm(text: str, max_chars: int = 60_000) -> str:
    """Обрезать текст до max_chars, стараясь резать по абзацам.

    60 000 символов ≈ 15 000 токенов (по 4 символа на токен) — влезает
    в yandexgpt-32k (32 768 токенов) с запасом на выход.
    """
    if len(text) <= max_chars:
        return text
    head = text[: int(max_chars * 0.7)]
    tail = text[-int(max_chars * 0.3):]
    return head + "\n\n[... middle part omitted for brevity ...]\n\n" + tail
