"""
Локальный e2e-тест: загружает HTML-фикстуру и прогоняет через KoobParser.
Не требует доступа в интернет.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from agent.config import get_settings
from agent.parsers.koob_parser import KoobParser
from agent.storage.file_manager import FileManager
from agent.storage.templates import render_metadata_json


def main() -> int:
    fixture = Path("tests/fixtures/transerfing.html")
    assert fixture.exists(), f"Фикстура не найдена: {fixture}"

    print("📖 Тест KoobParser (локальный)...")
    parser = KoobParser()
    html = fixture.read_text(encoding="utf-8")

    # Прогон через приватные методы парсера
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(html, "lxml")

    title = parser._extract_title(soup)
    author = parser._extract_author(soup)
    year = parser._extract_year(soup)
    cover = parser._extract_cover(soup, base_url="https://oko.koob.ru/test/")
    desc = parser._extract_text(soup, parser.SELECTORS["short_description"])
    ideas = parser._extract_key_ideas(soup, parser._entry_text(soup))
    quotes = parser._extract_quotes(soup, parser._entry_text(soup))
    chapters = parser._extract_chapters(soup)

    assert title == "Трансерфинг реальности", f"title={title!r}"
    assert "Зеланд" in author, f"author={author!r}"
    assert year == 2004, f"year={year!r}"
    assert cover and "cover" in cover, f"cover={cover!r}"
    assert desc and "Трансерфинг" in desc, f"desc={desc!r}"
    assert len(ideas) >= 3, f"ideas={ideas!r}"
    assert len(quotes) >= 2, f"quotes={quotes!r}"
    assert len(chapters) == 4, f"chapters={chapters!r}"

    print(f"  ✅ title:   {title}")
    print(f"  ✅ author:  {author}")
    print(f"  ✅ year:    {year}")
    print(f"  ✅ cover:   {cover}")
    print(f"  ✅ ideas:   {len(ideas)} шт.")
    print(f"  ✅ quotes:  {len(quotes)} шт.")
    print(f"  ✅ chapters:{len(chapters)} шт.")

    # Сохраним реальный результат парсинга
    from agent.models import BookInfo, ChapterInfo
    book = BookInfo(
        title=title,
        author=author,
        year=year,
        source_url="https://oko.koob.ru/transerfing_realnosti/",
        cover_url=cover,
        short_description=desc,
        key_ideas=ideas,
        quotes=quotes,
        chapters=chapters,
    )
    fm = FileManager()
    folder = fm.book_folder(book)
    fm.write_text(folder / "metadata.json", render_metadata_json(book))
    print(f"\n💾 Книга сохранена в: {folder}")

    # Проверим, что папка содержит ожидаемое
    assert (folder / "metadata.json").exists()
    print(f"  ✅ metadata.json создан")

    # Проверим, что metadata.json валидный JSON
    import json
    data = json.loads((folder / "metadata.json").read_text(encoding="utf-8"))
    assert data["title"] == title
    assert len(data["key_ideas"]) == len(ideas)
    assert len(data["quotes"]) == len(quotes)
    print(f"  ✅ metadata.json валидный, {len(data['key_ideas'])} идей, {len(data['quotes'])} цитат")

    print("\n🎉 Локальный e2e-тест прошёл успешно!")
    return 0


if __name__ == "__main__":
    sys.exit(main())
