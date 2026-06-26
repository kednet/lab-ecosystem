"""
Юнит-тесты для парсера KoobParser (универсальный — www.koob.ru + oko.koob.ru).

Проверяет, что:
  1. www-фикстура (zeland_level1.html) правильно парсится
     (title, author, cover, short_description).
  2. oko-фикстура (transerfing.html) — обратная совместимость.
  3. Авто-детект кодировки работает для cp1251.
  4. Абсолютизация URL обложки работает (даже если base = file://).
  5. Выбор зеркала (www/oko) делается корректно.

Запуск:
    python tests/test_koob_parser.py
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

# Корень проекта в sys.path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

# Убираем socks4 от VPN
for _k in ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY",
           "http_proxy", "https_proxy", "all_proxy"):
    os.environ.pop(_k, None)

from agent.parsers.koob_parser import KoobParser  # noqa: E402


FIXTURES = ROOT / "tests" / "fixtures"


def file_url(name: str) -> str:
    """Сформировать file:// URL для Windows-фикстуры."""
    return f"file:///{FIXTURES.as_posix()}/{name}"


def test_www_fixture():
    """www.koob.ru: парсим страницу Трансерфинг I — поля не пустые."""
    p = KoobParser()
    info = p.parse(file_url("zeland_level1.html"), save_raw_to=None)

    assert info.title, "title не должен быть пустым"
    assert "Трансерфинг" in info.title
    assert info.author, "author не должен быть пустым"
    assert "Зеланд" in info.author
    assert info.cover_url, "cover_url не должен быть пустым"
    assert info.cover_url.startswith("https://"), f"cover_url должен быть абсолютным, got {info.cover_url}"
    assert "koob.ru" in info.cover_url
    assert info.short_description, "short_description не должен быть пустым"
    print(f"  ✅ www: title={info.title!r} author={info.author!r} cover={info.cover_url}")


def test_oko_fixture_regression():
    """oko.koob.ru: legacy-фикстура должна по-прежнему работать."""
    p = KoobParser()
    info = p.parse(file_url("transerfing.html"), save_raw_to=None)
    assert info.title == "Трансерфинг реальности"
    assert info.year == 2004
    assert len(info.key_ideas) >= 3
    assert len(info.quotes) >= 1
    assert len(info.chapters) >= 1
    print(f"  ✅ oko: title={info.title!r} ideas={len(info.key_ideas)} quotes={len(info.quotes)} chapters={len(info.chapters)}")


def test_encoding_detection():
    """_decode_bytes правильно определяет cp1251 (русский текст не битый)."""
    raw = "Привет, мир!".encode("cp1251")
    decoded = KoobParser._decode_bytes(raw)
    assert "Привет" in decoded, f"Декодирование cp1251 не сработало: {decoded!r}"
    print(f"  ✅ cp1251 детект: {decoded!r}")


def test_utf8_encoding():
    """UTF-8 фикстура тоже работает (на случай других сайтов)."""
    raw = "Hello, мир!".encode("utf-8")
    decoded = KoobParser._decode_bytes(raw)
    assert "мир" in decoded
    print(f"  ✅ utf-8 детект: {decoded!r}")


def test_mirror_detection():
    """_detect_mirror правильно выбирает www/oko по URL и разметке."""
    from bs4 import BeautifulSoup

    www_html = '<html><body><div class="razdel"><a href="/x/">x</a></div></body></html>'
    oko_html = '<html><body><h1 class="book-title">X</h1></body></html>'

    soup_www = BeautifulSoup(www_html, "lxml")
    soup_oko = BeautifulSoup(oko_html, "lxml")

    assert KoobParser._detect_mirror("https://www.koob.ru/zeland/level1", soup_www) == "www"
    assert KoobParser._detect_mirror("https://oko.koob.ru/transerfing/", soup_www) == "oko"
    assert KoobParser._detect_mirror("https://www.koob.ru/zeland/level1", soup_oko) == "www"  # host wins
    print("  ✅ mirror detection: www+oko выбираются корректно")


def test_url_absolutize():
    """_absolutize_url превращает /foto/book/122.jpg → https://www.koob.ru/foto/..."""
    base_http = "https://www.koob.ru/zeland/level1"
    base_file = "file:///C:/tmp/page.html"

    abs_http = KoobParser._absolutize_url("/foto/book/122.jpg", base_http)
    assert abs_http == "https://www.koob.ru/foto/book/122.jpg", abs_http

    abs_file = KoobParser._absolutize_url("/foto/book/122.jpg", base_file)
    # file:// не годится как база → должен подставиться koob_base_url
    assert abs_file.startswith("https://"), f"file:// base должен дать https, got {abs_file}"
    assert "koob.ru" in abs_file

    abs_full = KoobParser._absolutize_url("https://other.com/x.jpg", base_http)
    assert abs_full == "https://other.com/x.jpg"

    abs_proto = KoobParser._absolutize_url("//cdn.example.com/x.jpg", base_http)
    assert abs_proto == "https://cdn.example.com/x.jpg"

    print(f"  ✅ URL absolutize: http={abs_http}  file={abs_file}")


if __name__ == "__main__":
    print("=" * 60)
    print("🧪 TEST 1: www.koob.ru — парсинг zeland_level1.html")
    print("=" * 60)
    test_www_fixture()
    print()
    print("=" * 60)
    print("🧪 TEST 2: oko.koob.ru — regression transerfing.html")
    print("=" * 60)
    test_oko_fixture_regression()
    print()
    print("=" * 60)
    print("🧪 TEST 3: детект кодировки cp1251")
    print("=" * 60)
    test_encoding_detection()
    print()
    print("=" * 60)
    print("🧪 TEST 4: детект кодировки utf-8")
    print("=" * 60)
    test_utf8_encoding()
    print()
    print("=" * 60)
    print("🧪 TEST 5: _detect_mirror (www/oko)")
    print("=" * 60)
    test_mirror_detection()
    print()
    print("=" * 60)
    print("🧪 TEST 6: _absolutize_url")
    print("=" * 60)
    test_url_absolutize()
    print()
    print("🎉 Все 6 тестов KoobParser прошли успешно!")
