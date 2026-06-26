"""
Юнит-тесты UniversalBookParser.

Проверяет:
  1. Карты загружаются из YAML/JSON.
  2. detect_site правильно матчит URL.
  3. Универсальный парсер работает с фикстурой www.koob.ru.
  4. Универсальный парсер работает с фикстурой oko.koob.ru (регрессия).
  5. Generic (Open Graph) парсер работает с произвольной HTML-страницей.
  6. JSON-LD extraction работает.

Запуск:
    python tests/test_universal_parser.py
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

for _k in ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY",
           "http_proxy", "https_proxy", "all_proxy"):
    os.environ.pop(_k, None)

from agent.parsers.prompts import load_all_sites, find_site_for_url  # noqa: E402
from agent.parsers.universal_parser import UniversalBookParser  # noqa: E402


FIXTURES = ROOT / "tests" / "fixtures"


def file_url(name: str) -> str:
    return f"file:///{FIXTURES.as_posix()}/{name}"


def test_sites_loaded():
    sites = load_all_sites()
    assert len(sites) >= 5, f"Должно быть ≥5 карт, got {len(sites)}: {[s.get('name') for s in sites]}"
    names = {s.get("name") for s in sites}
    assert "koob_www" in names
    assert "koob_oko" in names
    assert "livelib" in names
    assert "labirint" in names
    assert "litres" in names
    assert "generic" in names
    print(f"  ✅ Загружено {len(sites)} карт: {sorted(names)}")


def test_detect_site():
    p = UniversalBookParser()
    assert p.detect_site("https://www.koob.ru/zeland/level1") == "koob_www"
    assert p.detect_site("https://koob.ru/zeland/level1") == "koob_www"
    assert p.detect_site("https://oko.koob.ru/foo/") == "koob_oko"
    assert p.detect_site("https://www.livelib.ru/book/123") == "livelib"
    assert p.detect_site("https://www.labirint.ru/books/123") == "labirint"
    assert p.detect_site("https://www.litres.ru/book/abc") == "litres"
    # Произвольный URL — попадёт в generic
    assert p.detect_site("https://example.com/some-page") == "generic"
    print("  ✅ detect_site матчит все 6+ типов URL правильно")


def test_parse_www_fixture():
    p = UniversalBookParser()
    info = p.parse(file_url("zeland_level1.html"), save_raw_to=None)
    assert "Трансерфинг" in info.title
    assert "Зеланд" in info.author
    assert info.cover_url and "koob.ru" in info.cover_url
    assert info.short_description
    print(f"  ✅ www: «{info.title}» — {info.author}, "
          f"{len(info.key_ideas)} идей, {len(info.quotes)} цитат")


def test_parse_oko_fixture_regression():
    p = UniversalBookParser()
    info = p.parse(file_url("transerfing.html"), save_raw_to=None)
    assert info.title == "Трансерфинг реальности"
    assert info.year == 2004
    assert len(info.key_ideas) >= 3
    assert len(info.chapters) >= 1
    print(f"  ✅ oko regression: «{info.title}» — {info.author}, "
          f"{len(info.key_ideas)} идей, {len(info.chapters)} глав")


def test_parse_generic_og_html():
    """Парсер должен сработать на голой HTML-странице с Open Graph."""
    html = """<!doctype html>
    <html><head>
      <meta property="og:title" content="Думай медленно, решай быстро">
      <meta property="og:book:author" content="Даниэль Канеман">
      <meta property="og:image" content="https://example.com/cover.jpg">
      <meta name="description" content="Книга о двух системах мышления.">
      <title>Думай медленно, решай быстро — Даниэль Канеман</title>
    </head><body><h1>Думай медленно, решай быстро</h1></body></html>"""
    p = UniversalBookParser()
    # Подсунем напрямую через cache
    cache_dir = p.settings.cache_dir / "universal"
    cache_dir.mkdir(parents=True, exist_ok=True)
    import hashlib
    url = "https://example.com/kniga"
    cache_file = cache_dir / f"{hashlib.md5(url.encode()).hexdigest()}.html"
    cache_file.write_bytes(html.encode("utf-8"))

    info = p.parse(url, save_raw_to=None)
    assert "Думай медленно" in info.title
    assert "Канеман" in info.author
    assert info.cover_url == "https://example.com/cover.jpg"
    assert info.short_description
    print(f"  ✅ Generic OG: «{info.title}» — {info.author}")


def test_parse_jsonld_html():
    """Парсер должен уметь вытаскивать поля из JSON-LD @graph."""
    html = """<!doctype html>
    <html><head>
      <title>Атомные привычки — Джеймс Клир</title>
      <script type="application/ld+json">
      {
        "@context": "https://schema.org",
        "@graph": [
          {"@type": "Book", "name": "Атомные привычки",
           "author": {"@type": "Person", "name": "Джеймс Клир"},
           "image": "https://cdn.example.com/cover.png",
           "datePublished": "2018",
           "isbn": "9785001467833"}
        ]
      }
      </script>
    </head><body></body></html>"""
    p = UniversalBookParser()
    cache_dir = p.settings.cache_dir / "universal"
    cache_dir.mkdir(parents=True, exist_ok=True)
    import hashlib
    url = "https://example.com/atomic-habits"
    cache_file = cache_dir / f"{hashlib.md5(url.encode()).hexdigest()}.html"
    cache_file.write_bytes(html.encode("utf-8"))

    info = p.parse(url, save_raw_to=None)
    # title должен быть из JSON-LD (@graph.name) или из <title>
    assert "Атомные" in info.title
    # author из JSON-LD
    assert "Клир" in info.author
    # isbn из JSON-LD
    assert info.isbn and "5001467833" in info.isbn
    print(f"  ✅ JSON-LD: «{info.title}» — {info.author}, ISBN={info.isbn}")


def test_no_yaml_lib_graceful():
    """Даже если YAML не установлен, парсер не падает."""
    sites = load_all_sites()
    # Если pyyaml не установлен, все карты просто .json, но .yaml/.yml будут None.
    # Должна быть как минимум карта generic, если она в .json.
    # (в нашем случае все в .yaml, поэтому pyyaml обязателен — проверим, что
    # хотя бы не падает)
    assert isinstance(sites, list)
    print(f"  ✅ load_all_sites не падает (найдено {len(sites)} карт)")


if __name__ == "__main__":
    print("=" * 60)
    print("🧪 TEST 1: загрузка карт из YAML/JSON")
    print("=" * 60)
    test_sites_loaded()
    print()
    print("=" * 60)
    print("🧪 TEST 2: detect_site по URL")
    print("=" * 60)
    test_detect_site()
    print()
    print("=" * 60)
    print("🧪 TEST 3: парсинг www.koob.ru фикстуры")
    print("=" * 60)
    test_parse_www_fixture()
    print()
    print("=" * 60)
    print("🧪 TEST 4: регрессия oko.koob.ru фикстуры")
    print("=" * 60)
    test_parse_oko_fixture_regression()
    print()
    print("=" * 60)
    print("🧪 TEST 5: generic Open Graph парсер")
    print("=" * 60)
    test_parse_generic_og_html()
    print()
    print("=" * 60)
    print("🧪 TEST 6: JSON-LD @graph extraction")
    print("=" * 60)
    test_parse_jsonld_html()
    print()
    print("=" * 60)
    print("🧪 TEST 7: load_all_sites не падает")
    print("=" * 60)
    test_no_yaml_lib_graceful()
    print()
    print("🎉 Все 7 тестов UniversalBookParser прошли успешно!")
