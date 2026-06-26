"""
Нормализация имён авторов/названий и дедупликация книг.

Алгоритм:
  1. Транслитерация (Лев Толстой → Lev Tolstoy) — опционально.
  2. Lowercase, strip, убрать пунктуацию, схлопнуть пробелы.
  3. Хеш = sha1(normalized_author + normalized_title)[:12].
  4. Если есть ISBN — отдельный канонический ключ (приоритетнее).

Используется:
  - в BookInfo.folder_name() — единое имя папки для всех изданий.
  - в FileManager.find_existing_book() — поиск уже обработанной книги.
"""
from __future__ import annotations

import hashlib
import re
import unicodedata
from typing import Optional


# Минимальный транслит (кириллица → латиница). Достаточно для дедупа.
_TRANSLIT = {
    "а": "a", "б": "b", "в": "v", "г": "g", "д": "d", "е": "e", "ё": "yo",
    "ж": "zh", "з": "z", "и": "i", "й": "i", "к": "k", "л": "l", "м": "m",
    "н": "n", "о": "o", "п": "p", "р": "r", "с": "s", "т": "t", "у": "u",
    "ф": "f", "х": "h", "ц": "ts", "ч": "ch", "ш": "sh", "щ": "sch",
    "ъ": "", "ы": "y", "ь": "", "э": "e", "ю": "yu", "я": "ya",
}


def _translit(text: str) -> str:
    out = []
    for ch in text.lower():
        out.append(_TRANSLIT.get(ch, ch))
    return "".join(out)


def _strip_accents(text: str) -> str:
    return "".join(
        c for c in unicodedata.normalize("NFKD", text)
        if not unicodedata.combining(c)
    )


def normalize_text(s: Optional[str]) -> str:
    """
    Универсальная нормализация строки для сравнения:
      - lower
      - убрать диакритику
      - кириллица → латиница (транслит)
      - оставить только [a-z0-9] + пробелы
      - схлопнуть пробелы
    """
    if not s:
        return ""
    s = _strip_accents(s)
    s = _translit(s)
    s = re.sub(r"[^a-z0-9\s]+", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


# Стоп-слова, которые часто встречаются в названиях, но не помогают дедупу
_BOOK_TITLE_STOPWORDS = {
    "kniga", "the", "a", "an",         # english
    "книга",                              # russian
}


def normalize_title(s: Optional[str]) -> str:
    """Нормализация названия книги с выкидыванием стоп-слов."""
    n = normalize_text(s)
    tokens = [t for t in n.split() if t not in _BOOK_TITLE_STOPWORDS and len(t) > 1]
    return " ".join(tokens)


def normalize_isbn(isbn: Optional[str]) -> Optional[str]:
    """ISBN нормализуется в верхний регистр без дефисов и пробелов.
    None если строка не похожа на ISBN-10 или ISBN-13."""
    if not isbn:
        return None
    cleaned = re.sub(r"[\s\-]", "", isbn).upper()
    if re.fullmatch(r"\d{9}[\dX]", cleaned):
        return cleaned
    if re.fullmatch(r"\d{13}", cleaned):
        return cleaned
    return None


# ── Вычисление канонического ключа ────────────────────────────────
def book_fingerprint(
    title: Optional[str],
    author: Optional[str],
    year: Optional[int] = None,
    isbn: Optional[str] = None,
) -> str:
    """
    Канонический отпечаток книги.
    Приоритет: ISBN → (title + author + year).
    Возвращает hex-хеш (12 символов) — стабильный между запусками.
    """
    norm_isbn = normalize_isbn(isbn)
    if norm_isbn:
        return f"isbn:{norm_isbn}"

    nt = normalize_title(title)
    na = normalize_text(author)
    ny = str(year) if year else ""
    base = f"{na}|{nt}|{ny}"
    return "fp:" + hashlib.sha1(base.encode("utf-8")).hexdigest()[:12]


def folder_name_for(
    title: Optional[str],
    author: Optional[str],
    year: Optional[int] = None,
    isbn: Optional[str] = None,
) -> str:
    """
    Имя папки: Author_Title_Year.
    Если ISBN есть — добавляется суффикс.
    """
    def _safe(s: str) -> str:
        return "".join(c for c in s if c.isalnum() or c in " _-").strip()

    a = _safe(author or "Unknown").replace(" ", "_")
    t = _safe(title or "Untitled").replace(" ", "_")
    parts = [a, t]
    if year:
        parts.append(str(year))
    if isbn:
        norm_isbn = normalize_isbn(isbn)
        if norm_isbn:
            parts.append(f"ISBN-{norm_isbn}")
    return "_".join(p for p in parts if p)
