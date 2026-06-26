"""
Сбор отзывов с LiveLib (через поиск) + www.koob.ru (из уже сохранённого HTML).

Парсит публичную поисковую выдачу по названию книги, извлекает рейтинг и цитаты из отзывов.
"""
from __future__ import annotations

from typing import List, Optional
from urllib.parse import quote_plus

from bs4 import BeautifulSoup, Tag
from pathlib import Path

from agent.models import BookInfo, Review, ReviewBundle
from agent.parsers.base_parser import BaseParser
from agent.utils.logger import get_logger


logger = get_logger()


class ReviewsParser(BaseParser):
    name = "reviews"

    SEARCH_URL = "https://www.livelib.ru/find"

    def search(self, book: BookInfo, max_reviews: int = 8) -> ReviewBundle:
        """Собрать отзывы и оценки по книге."""
        query = f"{book.title} {book.author}"
        logger.info("💬 Поиск отзывов: {}", query)

        url = f"{self.SEARCH_URL}?q={quote_plus(query)}"
        try:
            html = self.fetch(url, cache_subdir="livelib")
        except Exception as e:
            logger.warning("Не удалось получить отзывы: {}", e)
            return ReviewBundle(book_title=book.title)

        soup = self.parse_soup(html)

        # Берём первую карточку книги
        book_card = soup.select_one(".book-item, .search-book, .ll-icon-card")
        book_url = ""
        if book_card:
            a = book_card.select_one("a[href*='/book/']")
            if a and a.get("href"):
                href = a["href"]
                book_url = (
                    href if href.startswith("http")
                    else "https://www.livelib.ru" + href
                )

        rating = None
        if book_card:
            import re
            r = book_card.select_one(".rating-value, .book-rating, .ll-rating")
            if r:
                m = re.search(r"[\d.,]+", r.get_text())
                if m:
                    try:
                        rating = float(m.group(0).replace(",", "."))
                    except ValueError:
                        pass

        reviews: List[Review] = []
        pros: List[str] = []
        cons: List[str] = []

        for card in book_card.select(".review, .ll-review") if book_card else []:
            text_el = card.select_one(".review-text, .ll-review-text, .review__text")
            if not text_el:
                continue
            text = text_el.get_text("\n", strip=True)
            if len(text) < 30:
                continue

            author_el = card.select_one(".review-author, .ll-review-author")
            reviews.append(
                Review(
                    author=author_el.get_text(strip=True) if author_el else "Аноним",
                    text=text[:1000],
                    rating=rating,
                    source="LiveLib",
                    url=book_url or None,
                )
            )
            if len(reviews) >= max_reviews:
                break

        # Альтернатива: «список плюсов и минусов» с обложки
        for li in book_card.select(".book-list-pros li, .pros li") if book_card else []:
            t = li.get_text(strip=True)
            if t and len(t) < 200:
                pros.append(t)
        for li in book_card.select(".book-list-cons li, .cons li") if book_card else []:
            t = li.get_text(strip=True)
            if t and len(t) < 200:
                cons.append(t)

        bundle = ReviewBundle(
            book_title=book.title,
            average_rating=rating,
            total_reviews=len(reviews),
            reviews=reviews,
            pros=pros[:10],
            cons=cons[:10],
        )
        logger.info("💬 Собрано отзывов: {}, плюсов: {}, минусов: {}",
                    len(reviews), len(pros), len(cons))
        return bundle

    # ── Доп. источник: www.koob.ru ───────────────────────────────
    def collect_www_koob_reviews(
        self,
        book: BookInfo,
        raw_html_path: Optional[str],
    ) -> List[Review]:
        """
        Достать отзывы из уже сохранённого HTML www.koob.ru.
        Используется, если страница была скачана парсером KoobParser.
        """
        if not raw_html_path:
            return []
        p = Path(raw_html_path)
        if not p.exists():
            return []
        try:
            html = p.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            return []
        soup = BeautifulSoup(html, "lxml")
        results: List[Review] = []
        for name, text in self._www_koob_comments(soup):
            results.append(
                Review(
                    author=name,
                    text=text,
                    source="www.koob.ru",
                    url=book.source_url,
                )
            )
            if len(results) >= 8:
                break
        if results:
            logger.info("💬 www.koob.ru: добавлено {} отзывов", len(results))
        return results

    @staticmethod
    def _www_koob_comments(soup: BeautifulSoup):
        block = soup.select_one("div.comments_list")
        if not block:
            return []
        out = []
        for div in block.find_all("div", recursive=False):
            name_el = div.select_one("small b")
            # Собираем только текстовые части, исключая <small>
            parts = []
            for child in div.children:
                if isinstance(child, Tag) and child.name == "small":
                    continue
                t = child.get_text(" ", strip=True) if hasattr(child, "get_text") else str(child).strip()
                if t:
                    parts.append(t)
            text = " ".join(parts).strip()
            if not text:
                continue
            name = name_el.get_text(strip=True) if name_el else "Аноним"
            if 5 <= len(text) <= 2000:
                out.append((name, text))
        return out

    def merge_bundles(
        self, book: BookInfo, primary: ReviewBundle, additional: List[Review]
    ) -> ReviewBundle:
        """Слить LiveLib-пакет с www.koob.ru отзывами (без дублей)."""
        if not additional:
            return primary
        seen = {r.text[:80].lower() for r in primary.reviews}
        for r in additional:
            if r.text[:80].lower() not in seen:
                primary.reviews.append(r)
                seen.add(r.text[:80].lower())
        primary.total_reviews = len(primary.reviews)
        return primary
