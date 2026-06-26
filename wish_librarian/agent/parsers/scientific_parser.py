"""
Поиск научных статей на КиберЛенинке (cyberleninka.ru).

Использует полнотекстовый поиск по запросу, сформированному из темы книги.
"""
from __future__ import annotations

from typing import List
from urllib.parse import quote_plus

from agent.models import BookInfo, ScientificArticle
from agent.parsers.base_parser import BaseParser
from agent.utils.logger import get_logger


logger = get_logger()


class ScientificParser(BaseParser):
    name = "scientific"

    SEARCH_URL = "https://cyberleninka.ru/search"

    def search(self, book: BookInfo, max_results: int = 5) -> List[ScientificArticle]:
        """Найти релевантные научные статьи по теме книги."""
        query = self._build_query(book)
        logger.info("🔬 Поиск статей по: {}", query)

        url = f"{self.SEARCH_URL}?q={quote_plus(query)}"
        try:
            html = self.fetch(url, cache_subdir="cyberleninka")
        except Exception as e:
            logger.warning("Не удалось искать на КиберЛенинке: {}", e)
            return []

        soup = self.parse_soup(html)
        articles: List[ScientificArticle] = []

        for card in soup.select("ul.search-results li, .search-result, article"):
            a = card.select_one("a[href*='/article/']")
            if not a:
                continue

            title = a.get_text(" ", strip=True)
            href = a.get("href", "")
            if href.startswith("/"):
                href = "https://cyberleninka.ru" + href

            authors_block = card.select_one(".authors, .author")
            authors_text = authors_block.get_text(" ", strip=True) if authors_block else ""
            authors = [a.strip() for a in authors_text.replace(",", ";").split(";") if a.strip()]

            year = None
            import re
            m = re.search(r"\b(19|20)\d{2}\b", card.get_text())
            if m:
                year = int(m.group(0))

            articles.append(
                ScientificArticle(
                    title=title,
                    authors=authors,
                    url=href,
                    year=year,
                )
            )
            if len(articles) >= max_results:
                break

        logger.info("📚 Найдено статей: {}", len(articles))
        return articles

    def _build_query(self, book: BookInfo) -> str:
        """Сформировать поисковый запрос из метаданных книги."""
        parts: list[str] = []
        if book.key_ideas:
            # берём 2-3 самых "концептных" слова из первой идеи
            first = book.key_ideas[0]
            parts.append(first[:120])
        if book.short_description:
            parts.append(book.short_description[:120])
        if not parts:
            parts = [f"{book.title} {book.author}"]
        return " ".join(parts)
