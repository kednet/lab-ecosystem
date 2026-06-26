"""
Парсер Koob.ru (универсальный — поддерживает оба зеркала).

Извлекает:
  - title, author, year
  - cover_url
  - short_description
  - key_ideas (из entry-content или .book-about, либо эвристикой)
  - quotes
  - chapters (если есть)
  - comments / reviews (с www.koob.ru)

Сохранение сырого HTML — в raw/source.html внутри папки книги.

Поддерживаемые зеркала:
  - https://www.koob.ru/{author_slug}/{book_slug}        — основной сайт
      Структура: <h1>Title</h1>, <div class=razdel><a>Author</a>,
                 <img src=/foto/book/{id}.jpg>, <div class=text><p>...</p></div>,
                 <div class=comments_list><div>...</div>...</div>
  - https://oko.koob.ru/{book_slug}/                     — legacy-зеркало
      Старая структура: h1.book-title, a[href*=/author/], .book-cover img, и т.д.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import List, Optional, Tuple
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup, Tag

from agent.config import get_settings
from agent.models import BookInfo, ChapterInfo
from agent.parsers.base_parser import BaseParser, FetchError, ParseError
from agent.utils.logger import get_logger


logger = get_logger()


class KoobParser(BaseParser):
    name = "koob"

    # ── Селекторы (устойчивые к редизайнам) ───────────────────────
    SELECTORS = {
        "title": [
            "h1.book-title",
            "h1.entry-title",
            "h1[itemprop='name']",
            "h1",  # универсальный fallback (www.koob.ru использует голый h1)
        ],
        "author": [
            ".book-author a",
            ".author-name",
            "span[itemprop='author']",
            "div.razdel > a:first-child",   # www.koob.ru: "Автор | Категория"
        ],
        "year": [
            "span.book-year",
            ".year",
            "span[itemprop='datePublished']",
        ],
        "cover": [
            ".book-cover img",
            "img.cover",
            "img[itemprop='image']",
            ".entry-content img:first-of-type",
            "div.book_id div.text a img",  # www.koob.ru
            "div.text img",                 # более широкий fallback
        ],
        "short_description": [
            ".book-annotation",
            ".book-about",
            ".annotation",
            "div.text p",                   # www.koob.ru
        ],
    }

    # Эти ссылки — элементы главного меню, НЕ авторы (даже если класс похож)
    _AUTHOR_HREF_BLOCKLIST = {"/author/", "/category/", "/comments/", "/search/"}

    # ── Главный метод ─────────────────────────────────────────────
    def parse(
        self,
        url: str,
        *,
        save_raw_to: Optional[Path] = None,
    ) -> BookInfo:
        logger.info("📖 Парсим Koob: {}", url)
        html = self.fetch(url, cache_subdir="koob")
        soup = self.parse_soup(html)

        # Определяем, какое зеркало — www.koob.ru или oko.koob.ru
        mirror = self._detect_mirror(url, soup)

        if save_raw_to:
            save_raw_to.parent.mkdir(parents=True, exist_ok=True)
            save_raw_to.write_text(html, encoding="utf-8")
            logger.debug("💾 Сырой HTML сохранён: {}", save_raw_to)

        title = self._extract_title(soup)
        author = self._extract_author(soup, mirror=mirror, base_url=url)
        year = self._extract_year(soup)
        cover_url = self._extract_cover(soup, base_url=url)
        short_description = self._extract_text(soup, self.SELECTORS["short_description"])
        key_ideas = self._extract_key_ideas(soup, full_text=self._entry_text(soup))
        quotes = self._extract_quotes(soup, full_text=self._entry_text(soup))
        chapters = self._extract_chapters(soup)

        if not title:
            raise ParseError(f"Не найдено название книги на {url}")

        info = BookInfo(
            title=title,
            author=author or "Неизвестен",
            year=year,
            source_url=url,
            cover_url=cover_url,
            short_description=short_description,
            key_ideas=key_ideas,
            quotes=quotes,
            chapters=chapters,
            raw_html_path=str(save_raw_to) if save_raw_to else None,
        )
        logger.success(
            "✅ Распарсено [{}]: «{}» — {} ({} идей, {} цитат, {} глав)",
            mirror,
            info.title,
            info.author,
            len(info.key_ideas),
            len(info.quotes),
            len(info.chapters),
        )
        return info

    # ── Определение зеркала ───────────────────────────────────────
    @staticmethod
    def _detect_mirror(url: str, soup: BeautifulSoup) -> str:
        """Возвращает 'www' или 'oko' в зависимости от URL/содержимого."""
        host = (urlparse(url).hostname or "").lower()
        if "oko.koob" in host:
            return "oko"
        # Сайт www.koob.ru использует <h1>Title</h1> + <div class=razdel>…
        if soup.select_one("div.razdel"):
            return "www"
        if host.endswith("koob.ru"):
            return "www"
        return "oko"  # безопасный fallback для совместимости

    # ── Извлечение полей ──────────────────────────────────────────
    def _entry_text(self, soup: BeautifulSoup) -> str:
        """Текст основного содержимого статьи."""
        node = (
            soup.select_one(".entry-content")
            or soup.select_one("article .entry")
            or soup.select_one("article")
            or soup.select_one("#content")
            or soup.select_one("div.text")  # www.koob.ru
        )
        return node.get_text("\n", strip=True) if node else soup.get_text("\n", strip=True)

    def _extract_title(self, soup: BeautifulSoup) -> str:
        for sel in self.SELECTORS["title"]:
            el = soup.select_one(sel)
            if el and el.get_text(strip=True):
                return el.get_text(strip=True)
        return ""

    def _extract_author(self, soup: BeautifulSoup, *, mirror: str, base_url: str) -> str:
        # 1. Специализированные селекторы
        for sel in self.SELECTORS["author"]:
            for el in soup.select(sel):
                href = (el.get("href") or "").strip()
                # Пропускаем ссылки из главного меню сайта
                if any(href.endswith(b) for b in self._AUTHOR_HREF_BLOCKLIST):
                    continue
                txt = el.get_text(strip=True)
                txt = re.sub(r"^(Автор:|А\.|By)\s*", "", txt, flags=re.IGNORECASE)
                if txt and len(txt) <= 100:
                    return txt

        # 2. meta og:author (www.koob.ru ставит такой)
        og_author = soup.find("meta", attrs={"property": "og:author"})
        if og_author and og_author.get("content"):
            return og_author["content"].strip()

        # 3. <title>Книга - Автор</title> (www.koob.ru)
        if mirror == "www" and soup.title:
            t = soup.title.get_text(" - ", strip=True)
            parts = [p.strip() for p in t.split(" - ") if p.strip()]
            if len(parts) >= 2:
                # Последний сегмент — автор. Но исключаем заведомо не-авторов:
                tail = parts[-1]
                if tail not in {"Куб", "Кооб"}:
                    return tail

        # 4. og:url → /zeland/... → "Зеланд"
        og_url = soup.find("meta", attrs={"property": "og:url"})
        if og_url and og_url.get("content"):
            path = urlparse(og_url["content"]).path.strip("/")
            if path:
                slug = path.split("/")[0].replace("_", " ").replace("-", " ").strip()
                if slug and slug not in {"www", "koob"}:
                    return slug.title()

        return ""

    def _extract_year(self, soup: BeautifulSoup) -> Optional[int]:
        for sel in self.SELECTORS["year"]:
            el = soup.select_one(sel)
            if el:
                m = re.search(r"\b(19|20)\d{2}\b", el.get_text())
                if m:
                    return int(m.group(0))
        # поищем в <title> и в og
        if soup.title:
            m = re.search(r"\b(19|20)\d{2}\b", soup.title.get_text())
            if m:
                return int(m.group(0))
        return None

    def _extract_cover(self, soup: BeautifulSoup, base_url: str) -> Optional[str]:
        for sel in self.SELECTORS["cover"]:
            el = soup.select_one(sel)
            if el and el.get("src"):
                return self._absolutize_url(el["src"], base_url)
        # og:image — резерв
        og = soup.find("meta", attrs={"property": "og:image"})
        if og and og.get("content"):
            return self._absolutize_url(og["content"], base_url)
        return None

    @staticmethod
    def _absolutize_url(src: str, base_url: str) -> str:
        if not src:
            return ""
        if src.startswith("//"):
            return "https:" + src
        if src.startswith(("http://", "https://")):
            return src
        if src.startswith("/"):
            # file:///C:/... не годится как база для https-картинки.
            # Используем koob_base_url как базу для относительных /-путей.
            if base_url.startswith("file://"):
                try:
                    base = get_settings().koob_base_url
                except Exception:
                    base = "https://www.koob.ru"
                return urljoin(base, src)
            return urljoin(base_url, src)
        return src

    def _extract_text(self, soup: BeautifulSoup, selectors: List[str]) -> Optional[str]:
        for sel in selectors:
            el = soup.select_one(sel)
            if el:
                txt = el.get_text("\n", strip=True)
                if txt and len(txt) > 30:
                    return txt
        # meta description
        md = soup.find("meta", attrs={"name": "description"})
        if md and md.get("content") and len(md["content"].strip()) > 30:
            return md["content"].strip()
        return None

    def _extract_key_ideas(self, soup: BeautifulSoup, full_text: str) -> List[str]:
        ideas: List[str] = []

        # 1. Маркированные списки внутри entry-content / book-about
        for ul in soup.select(".entry-content ul, .book-about ul, article ul"):
            for li in ul.find_all("li", recursive=True):
                txt = li.get_text(" ", strip=True)
                if 20 <= len(txt) <= 400:
                    ideas.append(txt)
                if len(ideas) >= 10:
                    return self._dedupe(ideas)

        # 2. Эвристика: строки, начинающиеся с "Идея", "Главная мысль" и т.п.
        for line in full_text.splitlines():
            if re.match(r"^(идея|мысль|главн\w*|тезис|концепц)\w*:", line.strip(), re.I):
                ideas.append(line.strip()[:400])
            if len(ideas) >= 10:
                break

        # 3. Fallback для www.koob.ru: первые 5 предложений описания,
        #    если они достаточно длинные (считаем их «идеями»)
        if not ideas:
            desc = (soup.select_one("div.text p") or soup.select_one("div.text"))
            if desc:
                sentences = re.split(r"(?<=[.!?])\s+", desc.get_text(" ", strip=True))
                for s in sentences:
                    s = s.strip()
                    if 40 <= len(s) <= 400:
                        ideas.append(s)
                    if len(ideas) >= 5:
                        break

        return self._dedupe(ideas)[:7]

    def _extract_quotes(self, soup: BeautifulSoup, full_text: str) -> List[str]:
        quotes: List[str] = []

        def _add(raw: str) -> None:
            raw = raw.strip()
            if not raw:
                return
            # Если текст уже обёрнут в «…» или "…" — оставляем как есть,
            # иначе оборачиваем в «…».
            if not (raw.startswith("«") and raw.endswith("»")) \
               and not (raw.startswith('"') and raw.endswith('"')):
                raw = f"«{raw}»"
            quotes.append(raw)

        # 1. <blockquote>
        for bq in soup.select("blockquote"):
            txt = bq.get_text(" ", strip=True)
            if 30 <= len(txt) <= 500:
                _add(txt)
            if len(quotes) >= 7:
                return self._dedupe(quotes)

        # 2. Строки в кавычках «»
        for m in re.finditer(r"«([^»]{30,500})»", full_text):
            _add(m.group(0))  # берём вместе с «…»
            if len(quotes) >= 7:
                break

        return self._dedupe(quotes)[:5]

    def _extract_chapters(self, soup: BeautifulSoup) -> List[ChapterInfo]:
        chapters: List[ChapterInfo] = []
        # Поиск блока "Содержание" / "Оглавление"
        contents = None
        for el in soup.find_all(["h2", "h3", "h4", "strong", "b"]):
            if "оглавление" in el.get_text().lower() or "содержание" in el.get_text().lower():
                contents = el.find_next(["ol", "ul"])
                if contents:
                    break

        if not contents:
            return chapters

        for i, li in enumerate(contents.find_all("li"), start=1):
            title = li.get_text(" ", strip=True)
            # убираем "Глава N. " префикс
            title = re.sub(r"^(Глава|Chapter|Параграф)\s*\d+[.:)]?\s*", "", title, flags=re.I)
            if 2 <= len(title) <= 200:
                chapters.append(ChapterInfo(number=i, title=title))

        return chapters[:50]

    # ── Дополнительно: отзывы с www.koob.ru ──────────────────────
    def extract_www_reviews(self, soup: BeautifulSoup) -> List[Tuple[str, str]]:
        """
        Возвращает список кортежей (автор_отзыва, текст) с www.koob.ru.
        Используется при необходимости обогатить reviews.md.
        """
        reviews: List[Tuple[str, str]] = []
        comments_list = soup.select_one("div.comments_list")
        if not comments_list:
            return reviews
        for block in comments_list.find_all("div", recursive=False):
            name_el = block.select_one("small b")
            text_parts: List[str] = []
            for child in block.children:
                if isinstance(child, Tag):
                    if child.name == "small":
                        continue
                    txt = child.get_text(" ", strip=True)
                    if txt:
                        text_parts.append(txt)
            text = " ".join(text_parts).strip()
            if not text:
                continue
            name = name_el.get_text(strip=True) if name_el else "Аноним"
            if 5 <= len(text) <= 2000:
                reviews.append((name, text))
        return reviews[:30]

    @staticmethod
    def _dedupe(items: List[str]) -> List[str]:
        seen = set()
        out = []
        for it in items:
            key = it.strip().lower()[:80]
            if key not in seen and it.strip():
                seen.add(key)
                out.append(it.strip())
        return out
