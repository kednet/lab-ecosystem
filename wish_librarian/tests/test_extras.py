"""
Тесты для новых модулей:
  - normalize (нормализация + fingerprint)
  - ai_cache (кеш)
  - search (поиск)
  - export (экспорт)
  - llm_parser (LLM-стратегия, моки)

Запуск: python tests/test_extras.py
"""
from __future__ import annotations

import os
import sys
import json
import tempfile
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

for _k in ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY",
           "http_proxy", "https_proxy", "all_proxy"):
    os.environ.pop(_k, None)

from agent.utils.normalize import (  # noqa: E402
    normalize_text, normalize_title, normalize_isbn,
    book_fingerprint, folder_name_for,
)


# ── normalize ───────────────────────────────────────────────────────
def test_normalize_basic():
    assert normalize_text("Привет, Мир!") == "privet mir"
    assert normalize_text("Hello, World!") == "hello world"
    # диакритика
    assert normalize_text("Café") == "cafe"
    print("  ✅ normalize_text: кириллица/латиница/диакритика")


def test_normalize_title():
    # "Книга: Трансерфинг" → "transerfing"
    t = normalize_title("Книга: Трансерфинг реальности")
    assert "transerfing" in t
    assert "kniga" not in t  # стоп-слово
    print("  ✅ normalize_title: стоп-слова выкинуты")


def test_normalize_isbn():
    assert normalize_isbn("978-5-00146-783-3") == "9785001467833"
    assert normalize_isbn("9785001467833") == "9785001467833"
    assert normalize_isbn("5-04-002873-7") == "5040028737"
    assert normalize_isbn("not-an-isbn") is None
    print("  ✅ normalize_isbn: 10/13 цифр, дефисы ок")


def test_fingerprint_stable():
    fp1 = book_fingerprint("Трансерфинг", "Зеланд", 2004)
    fp2 = book_fingerprint("Трансерфинг", "Зеланд", 2004)
    assert fp1 == fp2
    # другой год → другой fingerprint
    fp3 = book_fingerprint("Трансерфинг", "Зеланд", 2005)
    assert fp1 != fp3
    print("  ✅ fingerprint: стабильный + зависит от года")


def test_fingerprint_isbn_wins():
    fp_isbn = book_fingerprint("X", "Y", None, "978-5-00146-783-3")
    fp_no_isbn = book_fingerprint("X", "Y", None, None)
    assert fp_isbn.startswith("isbn:")
    assert fp_no_isbn.startswith("fp:")
    print("  ✅ fingerprint: ISBN > (title+author)")


def test_folder_name_for():
    n = folder_name_for("Трансерфинг", "Зеланд", 2004, "978-5-00146-783-3")
    assert "Зеланд" in n
    assert "Трансерфинг" in n
    assert "2004" in n
    assert "ISBN" in n
    print(f"  ✅ folder_name_for: «{n}»")


# ── ai_cache ────────────────────────────────────────────────────────
def test_ai_cache_roundtrip():
    from agent.models import BookInfo
    from agent.storage import ai_cache
    from agent.config import get_settings

    book = BookInfo(title="Test Book", author="Tester", year=2024, source_url="x")
    model = "test:model"
    settings = get_settings()

    # Чистый кеш для теста
    ai_cache.clear_cache_for(book)

    # Первый запрос — None
    assert ai_cache.get_cached(book, "summary", model) is None
    # Сохраняем
    ai_cache.save_cached(book, "summary", model, "Hello, this is a cached summary.")
    # Второй запрос — есть
    cached = ai_cache.get_cached(book, "summary", model)
    assert cached == "Hello, this is a cached summary."
    # Очистка
    n = ai_cache.clear_cache_for(book)
    assert n >= 1
    assert ai_cache.get_cached(book, "summary", model) is None
    print("  ✅ ai_cache: save → get → clear работает")


# ── search ──────────────────────────────────────────────────────────
def test_search_basic():
    from agent.search import search_library, _tokenize
    # _tokenize
    assert "привет" in _tokenize("Привет, как дела?")
    assert "дела" in _tokenize("Привет, как дела?")
    # search — нужен хотя бы 1 книга в библиотеке
    from agent.config import get_settings
    s = get_settings()
    if not s.output_dir.exists() or not list(s.output_dir.glob("*/summary.md")):
        print("  ⚠️  search.skip: библиотека пуста, тест невозможен")
        return
    results = search_library("трансерфинг", s.output_dir)
    assert results, "search не нашёл ни одной книги (хоть одна должна быть в библиотеке)"
    folder, score, _ = results[0]
    assert score > 0
    print(f"  ✅ search_library: «трансерфинг» → {len(results)} результатов, top score={score}")


# ── export ──────────────────────────────────────────────────────────
def test_export_txt():
    from agent.export import export_book, collect_book_text
    with tempfile.TemporaryDirectory() as tmp:
        folder = Path(tmp) / "Test_Book"
        folder.mkdir()
        (folder / "summary.md").write_text("# Test\n\nSome content here.", encoding="utf-8")
        (folder / "workbook.md").write_text("# Workbook\n\n- Step 1\n- Step 2", encoding="utf-8")

        text = collect_book_text(folder)
        assert "Some content" in text
        assert "Step 1" in text
        # Без metadata.json заголовка не будет — но сам контент собран
        assert "# 📝 Конспект" in text or "Some content" in text

        files = export_book(folder, ["txt"])
        assert len(files) == 1
        assert files[0].suffix == ".txt"
        assert "Some content" in files[0].read_text(encoding="utf-8")
        print("  ✅ export_book: txt создан, контент собран")


def test_export_html_minimal():
    from agent.export import export_book
    with tempfile.TemporaryDirectory() as tmp:
        folder = Path(tmp) / "Book"
        folder.mkdir()
        (folder / "summary.md").write_text("# Title\n\nParagraph.", encoding="utf-8")
        files = export_book(folder, ["html"])
        # html без pandoc всё равно создаётся
        assert any(f.suffix == ".html" for f in files)
        print("  ✅ export_book: html создан (без pandoc — fallback)")


def test_export_pdf_reportlab():
    """PDF должен создаваться без pandoc — через reportlab (pure Python)."""
    from agent.export import export_book, md_to_pdf
    with tempfile.TemporaryDirectory() as tmp:
        folder = Path(tmp) / "Book_PDF"
        folder.mkdir()
        (folder / "summary.md").write_text(
            "# Конспект\n\n"
            "## Раздел 1\n"
            "Это **жирный** и *курсивный* текст.\n\n"
            "- Пункт 1\n- Пункт 2\n- [ ] Чекбокс\n\n"
            "> Цитата\n\n"
            "| A | B |\n|---|---|\n| 1 | 2 |\n",
            encoding="utf-8",
        )
        files = export_book(folder, ["pdf"])
        assert any(f.suffix == ".pdf" for f in files), "PDF не создан"
        pdf_path = [f for f in files if f.suffix == ".pdf"][0]
        # Проверка: файл — валидный PDF
        with open(pdf_path, "rb") as f:
            head = f.read(5)
        assert head == b"%PDF-", f"Не PDF-заголовок: {head!r}"
        # Размер > 1 КБ (там есть контент)
        assert pdf_path.stat().st_size > 1000
        # md_to_pdf — одиночный файл
        md = folder / "summary.md"
        pdf2 = md.with_suffix(".pdf")
        if pdf2.exists():
            pdf2.unlink()
        result = md_to_pdf(md, pdf2)
        assert result.exists() and result.suffix == ".pdf"
        print(
            f"  ✅ export PDF: {pdf_path.stat().st_size} байт, "
            f"валидный заголовок %PDF-"
        )


# ── llm_parser (моки) ───────────────────────────────────────────────
def test_llm_parser_json_extraction():
    """Парсим типичный ответ LLM с ```json```."""
    from agent.parsers.llm_parser import _try_parse_json
    raw = "```json\n{\"title\": \"X\", \"year\": 2004}\n```"
    data = _try_parse_json(raw)
    assert data == {"title": "X", "year": 2004}

    # С пояснением вокруг
    raw2 = "Here is the JSON:\n{\"a\": 1, \"b\": [2,3]}\nDone!"
    data2 = _try_parse_json(raw2)
    assert data2 == {"a": 1, "b": [2, 3]}
    print("  ✅ _try_parse_json: обрабатывает markdown-fence и prose")


def test_llm_parser_truncate():
    from agent.parsers.llm_parser import _truncate_html
    html = "<html><head>" + ("<meta name='x' content='y'>" * 1000) + "</head><body>" + ("<p>Lorem ipsum dolor sit amet</p>" * 1000) + "</body></html>"
    truncated = _truncate_html(html, max_chars=2000)
    assert len(truncated) <= 2500
    assert "[meta" in truncated or "[p]" in truncated
    print(f"  ✅ _truncate_html: {len(html)} → {len(truncated)} символов")


if __name__ == "__main__":
    print("=" * 60); print("🧪 TEST 1: normalize_text"); print("=" * 60)
    test_normalize_basic()
    print()
    print("=" * 60); print("🧪 TEST 2: normalize_title"); print("=" * 60)
    test_normalize_title()
    print()
    print("=" * 60); print("🧪 TEST 3: normalize_isbn"); print("=" * 60)
    test_normalize_isbn()
    print()
    print("=" * 60); print("🧪 TEST 4: fingerprint (стабильность)"); print("=" * 60)
    test_fingerprint_stable()
    print()
    print("=" * 60); print("🧪 TEST 5: fingerprint (ISBN приоритет)"); print("=" * 60)
    test_fingerprint_isbn_wins()
    print()
    print("=" * 60); print("🧪 TEST 6: folder_name_for"); print("=" * 60)
    test_folder_name_for()
    print()
    print("=" * 60); print("🧪 TEST 7: ai_cache roundtrip"); print("=" * 60)
    test_ai_cache_roundtrip()
    print()
    print("=" * 60); print("🧪 TEST 8: search_library"); print("=" * 60)
    test_search_basic()
    print()
    print("=" * 60); print("🧪 TEST 9: export_book (txt)"); print("=" * 60)
    test_export_txt()
    print()
    print("=" * 60); print("🧪 TEST 10: export_book (html)"); print("=" * 60)
    test_export_html_minimal()
    print()
    print("=" * 60); print("🧪 TEST 10b: export_book (PDF / reportlab)"); print("=" * 60)
    test_export_pdf_reportlab()
    print()
    print("=" * 60); print("🧪 TEST 11: LLM JSON extraction"); print("=" * 60)
    test_llm_parser_json_extraction()
    print()
    print("=" * 60); print("🧪 TEST 12: LLM HTML truncate"); print("=" * 60)
    test_llm_parser_truncate()
    print()
    print("🎉 Все 13 тестов test_extras прошли успешно!")
