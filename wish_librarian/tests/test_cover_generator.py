"""
Smoke-тесты для генератора обложек agent/cover/.

Запуск:
    cd wish_librarian && python -m pytest tests/test_cover_generator.py -v
"""
from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

from agent.cover import CoverGenerator, CoverStyle
from agent.cover.colors import (
    SCHEMES,
    ColorGenerator,
    contrast_ratio,
    get_color_generator,
)
from agent.cover.png_export import has_cairo
from agent.cover.templates import get_template, TEMPLATES
from agent.models import BookInfo


# ── 1. Базовый generate возвращает валидный SVG ────────────────────
def test_generate_returns_valid_svg():
    gen = CoverGenerator()
    r = gen.generate("Тестовая книга", "Автор")
    assert isinstance(r["svg"], bytes)
    assert r["svg"].startswith(b"<?xml") or r["svg"].startswith(b"<svg")
    # Парсится как XML
    root = ET.fromstring(r["svg"])
    assert root.tag.endswith("svg")
    # Содержит text с title
    ns = {"svg": "http://www.w3.org/2000/svg"}
    texts = root.findall(".//svg:text", ns)
    assert any("Тестовая книга" in (t.text or "") for t in texts)
    assert any("Автор" in (t.text or "") for t in texts)
    # Стиль по умолчанию — minimal
    assert r["style"] == CoverStyle.MINIMAL


# ── 2. detect_style по жанру ───────────────────────────────────────
@pytest.mark.parametrize("genre,expected", [
    ("эзотерика",         CoverStyle.MYSTICAL),
    ("эзотерическая",     CoverStyle.MYSTICAL),
    ("духовное развитие", CoverStyle.MYSTICAL),
    ("медитация",         CoverStyle.MYSTICAL),
    ("бизнес",            CoverStyle.BUSINESS),
    ("финансы",           CoverStyle.BUSINESS),
    ("психология",        CoverStyle.GRADIENT),
    ("саморазвитие",      CoverStyle.GRADIENT),
    ("мотивация",         CoverStyle.GRADIENT),
    ("история",           CoverStyle.GEOMETRIC),
    ("наука",             CoverStyle.GEOMETRIC),
    ("random",            None),  # нет совпадений — None (generate мапит в MINIMAL)
])
def test_detect_style(genre, expected):
    gen = CoverGenerator()
    style = gen._detect_style_from_text(genre)
    assert style == expected, f"genre={genre!r} → {style}, expected {expected}"


# ── 3. detect_style через BookInfo ─────────────────────────────────
def test_detect_style_via_book():
    gen = CoverGenerator()
    book = BookInfo(
        title="Трансерфинг реальности",
        author="Зеланд",
        source_url="https://example.com",
        genre="эзотерика",
    )
    assert gen.detect_style(book) == CoverStyle.MYSTICAL


# ── 4. SVG корректно экранирует спец-символы ───────────────────────
def test_escape_special_chars():
    gen = CoverGenerator()
    r = gen.generate(
        title='Тест "с кавычками" & <тегами>',
        author="O'Reilly & Sons",
    )
    # Должно парситься без ошибок
    root = ET.fromstring(r["svg"])
    texts = root.findall(".//{http://www.w3.org/2000/svg}text")
    joined = " | ".join(t.text or "" for t in texts)
    # Экранированные символы
    assert "&amp;" in r["svg"].decode("utf-8")
    assert "&quot;" in r["svg"].decode("utf-8")
    assert "&lt;" in r["svg"].decode("utf-8")
    assert "&gt;" in r["svg"].decode("utf-8")


# ── 5. save() создаёт файл ─────────────────────────────────────────
def test_save_creates_svg_file(tmp_path: Path):
    gen = CoverGenerator()
    r = gen.generate("Test", "Author")
    out = gen.save(r, tmp_path, png_format="none")
    assert out["svg"].exists()
    assert out["svg"].suffix == ".svg"
    assert out["svg"].stat().st_size > 200
    assert out["png"] is None  # мы просили none


# ── 6. PNG конвертация (через Playwright или cairosvg) ─────────────
def test_png_export_graceful(tmp_path: Path):
    """С 2026-06: PNG-экспорт работает через Playwright (Node CLI) — точнее
    рендерит кириллицу. cairosvg оставлен как fallback. Тест проверяет, что
    при наличии хотя бы одного бэкенда (Playwright или cairosvg) PNG создаётся.
    """
    from agent.cover.png_export import has_any_backend, has_cairo, has_playwright
    if not has_any_backend():
        pytest.skip("Ни Playwright, ни cairosvg не доступны — пропускаем")
    gen = CoverGenerator()
    r = gen.generate("Test", "Author")
    out = gen.save(r, tmp_path, png_format="jpg")
    assert out["png"] is not None, (
        f"PNG не создан, хотя backend доступен: "
        f"playwright={has_playwright()}, cairo={has_cairo()}"
    )
    assert out["png"].exists()
    assert out["png"].stat().st_size > 1000


# ── 7. WCAG-AA контраст для всех палитр ───────────────────────────
def test_all_schemes_have_wcag_aa_contrast():
    gen = get_color_generator()
    for name, scheme in SCHEMES.items():
        fixed = gen._fix_contrast(scheme.copy())
        for bg_key in ("primary", "secondary"):
            ratio = contrast_ratio(fixed["text"], fixed[bg_key])
            assert ratio >= 4.5, (
                f"scheme={name}, bg={bg_key}, "
                f"text={fixed['text']} on {fixed[bg_key]} → {ratio:.2f}"
            )


# ── 8. Усечение длинных title/author ────────────────────────────────
def test_truncation():
    gen = CoverGenerator()
    long_title = "А" * 100
    long_author = "Б" * 100
    r = gen.generate(long_title, long_author)
    # title НЕ усекается жёстко — wrap разбивает на 2-3 строки (см. _wrap_title_to_tspans)
    # Это намеренное поведение: иначе теряется информация из длинных названий
    # (например, «Трансерфинг реальности I: Пространство вариантов»).
    assert len(r["title"]) == 100  # title сохраняется целиком
    # author усекается (MAX_AUTHOR_LEN=45)
    assert r["author"].endswith("…")
    assert len(r["author"]) <= gen.MAX_AUTHOR_LEN


# ── 9. forced_scheme + явный style ─────────────────────────────────
def test_forced_style_and_scheme():
    gen = CoverGenerator()
    r = gen.generate(
        "Любая", "Книга",
        style=CoverStyle.BUSINESS,
        forced_scheme="purple_pink",
    )
    assert r["style"] == CoverStyle.BUSINESS
    assert r["scheme"]["primary"] == "#6D28D9"


# ── 10. Шаблоны покрывают все стили ────────────────────────────────
def test_all_templates_have_placeholders():
    # Базовые плейсхолдеры должны быть во ВСЕХ шаблонах.
    # {{TEXT_COLOR}} требуется не всем — classic использует светлый фон
    # и рисует тёмный текст через {{COLOR1}} (см. комментарий в classic.py).
    needed = {"{{TITLE}}", "{{AUTHOR}}", "{{COLOR1}}"}
    # Дополнительно: некоторые шаблоны должны иметь {{TEXT_COLOR}} (тёмный фон).
    needs_text_color = {"modern", "gradient", "mystical", "business", "geometric",
                       "minimal", "vintage", "og"}
    for name, tpl in TEMPLATES.items():
        placeholders = set(re.findall(r"\{\{[A-Z_0-9]+\}\}", tpl))
        missing = needed - placeholders
        assert not missing, f"Template {name!r} missing: {missing}"
        if name in needs_text_color:
            assert "{{TEXT_COLOR}}" in placeholders, \
                f"Template {name!r} (dark-bg) must have {{TEXT_COLOR}}"


# ── 11. get_template fallback ──────────────────────────────────────
def test_get_template_unknown_returns_minimal():
    assert get_template("unknown") == get_template("minimal")
