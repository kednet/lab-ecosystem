"""
Универсальный парсер книг.

Принимает URL любого сайта, автоматически подбирает подходящую
карту (YAML/JSON из agent/parsers/sites/) и достаёт BookInfo.

Декларативный движок: чтобы добавить новый сайт — просто
положите .yaml в agent/parsers/sites/. Код не трогаем.

Поддерживаемые стратегии (см. docstring в prompts.py):
  - og_meta     — Open Graph + Schema.org / JSON-LD
  - hybrid      — специализированные CSS-селекторы + OG-фолбэк
  - metadata    — только meta[name=...] / meta[property=...]

Карты определяют, какие селекторы и правила использовать для:
  - title, author, year
  - cover_url, short_description
  - key_ideas, quotes, chapters
  - isbn, page_count, genre
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, List, Optional
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup, Tag

from agent.config import get_settings
from agent.models import BookInfo, ChapterInfo
from agent.parsers.base_parser import BaseParser, FetchError, ParseError
from agent.parsers.prompts import (
    SITES_DIR,
    find_site_for_url,
    load_all_sites,
)
from agent.utils.logger import get_logger


logger = get_logger()


# ── Точка входа ─────────────────────────────────────────────────────
class UniversalBookParser(BaseParser):
    """
    Парсер, который сам выбирает стратегию по URL.
    """

    name = "universal"

    def __init__(self, session=None):
        super().__init__(session=session)
        self.settings = get_settings()
        self._sites_cache: Optional[List[dict]] = None

    # ── Публичное API ───────────────────────────────────────────
    def parse(self, url: str, *, save_raw_to: Optional[Path] = None) -> BookInfo:
        logger.info("🌐 Universal parse: {}", url)

        html = self.fetch(url, cache_subdir="universal")
        soup = self.parse_soup(html)

        site = self._resolve_site(url, soup)
        logger.info("📋 Карта: {} ({})", site.get("name"), site.get("display", ""))

        engine = _Engine(site, soup, base_url=url, raw_html=html)
        book = engine.extract()

        # Если обычный парсер дал мало — пробуем LLM-фолбэк
        if _Engine._is_poor(book) and self._llm_enabled:
            logger.info("📉 Мало полей — пробую LLM-стратегию")
            llm = self._get_llm_parser()
            if llm is not None:
                llm_result = llm.parse_unknown(url, html, site.get("name", ""))
                if llm_result and len(llm_result.title) > 2:
                    book = _Engine._merge_better(book, llm_result)

        if save_raw_to:
            save_raw_to.parent.mkdir(parents=True, exist_ok=True)
            save_raw_to.write_text(html, encoding="utf-8")
            book.raw_html_path = str(save_raw_to)

        if not book.title:
            raise ParseError(f"Не удалось извлечь title с {url} (карта: {site.get('name')})")

        logger.success(
            "✅ Извлечено [{}]: «{}» — {} ({} идей, {} цитат, {} глав)",
            site.get("name"),
            book.title,
            book.author,
            len(book.key_ideas),
            len(book.quotes),
            len(book.chapters),
        )
        return book

    # ── LLM-фолбэк (ленивая загрузка) ─────────────────────────
    @property
    def _llm_enabled(self) -> bool:
        # Включаем по умолчанию; отключить можно через env или конструктор
        import os
        return os.environ.get("WL_DISABLE_LLM_PARSE", "0") != "1"

    def _get_llm_parser(self):
        try:
            from agent.ai.factory import get_ai_client
            from agent.parsers.llm_parser import LLMParser
            return LLMParser(get_ai_client())
        except Exception as e:
            logger.debug("LLM parser недоступен: {}", e)
            return None

    # ── Список поддерживаемых сайтов ───────────────────────────
    @property
    def supported_sites(self) -> List[dict]:
        if self._sites_cache is None:
            self._sites_cache = load_all_sites()
        return self._sites_cache

    def detect_site(self, url: str) -> Optional[str]:
        """Вернуть имя карты, подходящей под URL (или None)."""
        site = find_site_for_url(url, self.supported_sites)
        return site.get("name") if site else None

    # ── Внутреннее ───────────────────────────────────────────
    def _resolve_site(self, url: str, soup: BeautifulSoup) -> dict:
        """Подобрать карту: сначала по host, потом generic.
        Для file:// URL — перебираем все карты по приоритету.
        """
        # file:// URL — универсальный парсер не знает сайт заранее,
        # пробуем каждую карту по очереди; берём ту, которая даст
        # максимум непустых полей.
        if url.startswith("file://"):
            return self._best_site_for_unknown(soup)

        site = find_site_for_url(url, self.supported_sites)
        if site:
            return site
        # fallback — generic
        for s in self.supported_sites:
            if s.get("name") == "generic":
                return s
        return {"name": "inline_empty", "selectors": {}}

    def _best_site_for_unknown(self, soup: BeautifulSoup) -> dict:
        """Для неизвестного URL пробуем все карты; берём ту, что даёт
        максимум непустых полей. Полезно для file:// и незнакомых сайтов.
        """
        best, best_score = None, -1
        for s in self.supported_sites:
            try:
                eng = _Engine(s, soup, base_url="", raw_html="")
                trial = eng.extract()
            except Exception:
                continue
            score = sum(1 for f in ("title", "author", "cover_url",
                                    "short_description", "year", "isbn")
                        if getattr(trial, f, None))
            if score > best_score:
                best, best_score = s, score
        return best or self.supported_sites[-1]  # generic fallback


# ── Движок интерпретации карт ───────────────────────────────────────
class _Engine:
    """Выполняет правила из SiteMap против soup-дерева."""

    def __init__(self, site: dict, soup: BeautifulSoup, *, base_url: str, raw_html: str):
        self.site = site
        self.soup = soup
        self.base_url = base_url
        self.raw_html = raw_html
        self.settings = get_settings()
        self.full_text = soup.get_text("\n", strip=True)
        # Поля BookInfo
        self.data: dict = {
            "title": "",
            "author": "Неизвестен",
            "year": None,
            "source_url": base_url,
            "cover_url": None,
            "short_description": None,
            "key_ideas": [],
            "quotes": [],
            "chapters": [],
            "isbn": None,
            "page_count": None,
            "genre": None,
        }

    # ── Главный метод ─────────────────────────────────────────
    def extract(self) -> BookInfo:
        selectors = self.site.get("selectors", {})
        for field, rules in selectors.items():
            if not rules:
                continue
            value = self._apply_rules(rules)
            if value is None or value == "":
                continue
            self._assign(field, value)

        # Пост-обработка
        self._normalize_cover()
        self._limit_lists()

        return BookInfo(**self.data)

    # ── Применение правил ─────────────────────────────────────
    def _apply_rules(self, rules) -> Any:
        """Перебираем правила по порядку; первое успешное побеждает."""
        if isinstance(rules, str):
            rules = [rules]
        for rule in rules:
            try:
                v = self._apply_one(rule)
            except Exception as e:  # pragma: no cover
                logger.debug("Rule {} failed: {}", rule, e)
                continue
            if v is None or v == "" or v == []:
                continue
            return v
        return None

    def _apply_one(self, rule: str) -> Any:
        """Обработать одно правило."""
        if not isinstance(rule, str):
            return None

        # ── Спец-правила ──────────────────────────────────
        if rule.startswith("css:"):
            sel = rule[4:].strip()
            if ":has-text(" in sel:
                # CSS-селектор с text-фильтром: разбираем вручную
                sel, text = self._split_has_text(sel)
                nodes = [n for n in self.soup.select(sel) if text.lower() in n.get_text().lower()]
                if not nodes:
                    return None
                # Ищем «следующий» элемент (sibling)
                target = nodes[0].find_next(["ol", "ul", "div", "section"])
                if not target:
                    return None
                if target.name in ("ol", "ul"):
                    return [li.get_text(" ", strip=True) for li in target.find_all("li", recursive=True)]
                return target.get_text("\n", strip=True)
            nodes = self.soup.select(sel)
            if not nodes:
                return None
            # Если это <li>-список или <p>-список — вернуть массив
            if all(n.name in ("li", "p") for n in nodes):
                return [n.get_text(" ", strip=True) for n in nodes]
            return nodes[0].get_text(" ", strip=True)

        if rule.startswith("@attr:"):
            # @attr:src:selector
            parts = rule.split(":", 2)
            if len(parts) == 3:
                _, attr, sel = parts
                el = self.soup.select_one(sel)
                if el and el.get(attr):
                    return el[attr]
                return None

        if rule.startswith("@content:"):
            # @content:meta[name='description']
            sel = rule[len("@content:"):].strip()
            # Если правило уже начинается с `meta`, не дублируем
            if not sel.startswith("meta"):
                sel = f"meta{sel}"
            el = self.soup.select_one(sel)
            if el and el.get("content"):
                return el["content"].strip()
            return None

        if rule.startswith("@og:"):
            # @og:title  → <meta property="og:title">
            # @og:book:author → <meta property="og:book:author">
            # @og:image → <meta property="og:image">
            prop = "og:" + rule[4:].strip()
            el = self.soup.find("meta", attrs={"property": prop})
            if el and el.get("content"):
                return el["content"].strip()
            # Альтернатива — name=og:* (некоторые сайты)
            el = self.soup.find("meta", attrs={"name": prop})
            if el and el.get("content"):
                return el["content"].strip()
            return None

        if rule.startswith("@split_title:"):
            # @split_title:last  / first
            mode = rule.split(":", 1)[1].strip()
            t = self.soup.title.get_text(" -/—–|") if self.soup.title else ""
            parts = [p.strip() for p in re.split(r"[\s\-–—|]+", t) if p.strip()]
            if mode == "last" and parts:
                return parts[-1]
            if mode == "first" and parts:
                return parts[0]

        if rule.startswith("@url_slug:"):
            # @url_slug:1 — взять N-й сегмент пути, humanize
            n = int(rule.split(":", 1)[1].strip()) - 1
            path = urlparse(self.base_url).path.strip("/")
            segs = [s for s in path.split("/") if s]
            if 0 <= n < len(segs):
                slug = segs[n].replace("_", " ").replace("-", " ").strip()
                return slug.title()

        if rule.startswith("@jsonld:"):
            field = rule.split(":", 1)[1].strip()
            return self._jsonld_get(field)

        if rule.startswith("regex_in:"):
            # regex_in:title:\\b(19|20)\\d{2}\\b   или   regex_in:full:...
            parts = rule.split(":", 2)
            if len(parts) == 3:
                _, where, pattern = parts
                rx = re.compile(pattern)
                if where == "title" and self.soup.title:
                    m = rx.search(self.soup.title.get_text())
                    if m:
                        return m.group(0)
                elif where == "full":
                    m = rx.search(self.raw_html)
                    if m:
                        return m.group(0)
                    m = rx.search(self.full_text)
                    if m:
                        return m.group(0)

        return None

    @staticmethod
    def _split_has_text(sel: str):
        # css:h2:has-text(оглавление)~ol li
        m = re.match(r"^(.*?):has-text\(([^)]+)\)(.*)$", sel)
        if not m:
            return sel, ""
        return (m.group(1) + m.group(3)).strip(), m.group(2).strip()

    def _jsonld_get(self, field: str) -> Optional[str]:
        for s in self.soup.find_all("script", attrs={"type": "application/ld+json"}):
            try:
                data = json.loads(s.string or "{}")
            except (ValueError, TypeError):
                continue
            for node in self._iter_jsonld(data):
                if field in node and node[field]:
                    v = node[field]
                    if isinstance(v, list):
                        v = v[0] if v else ""
                    if isinstance(v, dict):
                        v = v.get("name") or v.get("@value") or ""
                    return str(v)
        return None

    @staticmethod
    def _iter_jsonld(data):
        if isinstance(data, dict):
            yield data
            for v in data.values():
                yield from _Engine._iter_jsonld(v)
        elif isinstance(data, list):
            for v in data:
                yield from _Engine._iter_jsonld(v)

    # ── Назначение полей ─────────────────────────────────────
    def _assign(self, field: str, value: Any) -> None:
        if field == "year":
            m = re.search(r"\b(19|20)\d{2}\b", str(value))
            self.data["year"] = int(m.group(0)) if m else None
        elif field == "cover":
            self.data["cover_url"] = self._absolutize(str(value))
        elif field in ("title", "author", "short_description", "isbn", "page_count", "genre"):
            text = str(value).strip()
            if not text:
                return
            if field == "page_count":
                m = re.search(r"\d+", text)
                self.data["page_count"] = int(m.group(0)) if m else None
            elif field == "isbn":
                self.data["isbn"] = text
            elif field == "genre":
                self.data["genre"] = text
            else:
                self.data[field] = text
        elif field in ("key_ideas", "quotes"):
            arr = value if isinstance(value, list) else [value]
            cleaned = []
            for x in arr:
                x = str(x).strip()
                if x and 5 <= len(x) <= 800:
                    cleaned.append(x)
                if len(cleaned) >= 10:
                    break
            self.data[field].extend(cleaned)
        elif field == "chapters":
            arr = value if isinstance(value, list) else [value]
            for i, ch in enumerate(arr, start=len(self.data["chapters"]) + 1):
                title = re.sub(r"^(Глава|Chapter|Параграф)\s*\d+[.:)]?\s*", "", str(ch), flags=re.I).strip()
                if 2 <= len(title) <= 200:
                    self.data["chapters"].append(ChapterInfo(number=i, title=title))
                if len(self.data["chapters"]) >= 50:
                    break

    def _absolutize(self, src: str) -> str:
        if not src:
            return ""
        if src.startswith("//"):
            return "https:" + src
        if src.startswith(("http://", "https://")):
            return src
        if src.startswith("/"):
            # Если base_url это file://, подставляем базу koob
            if self.base_url.startswith("file://"):
                return urljoin(self.settings.koob_base_url, src)
            return urljoin(self.base_url, src)
        return src

    def _normalize_cover(self) -> None:
        if not self.data["cover_url"]:
            return
        self.data["cover_url"] = self._absolutize(self.data["cover_url"])

    def _limit_lists(self) -> None:
        self.data["key_ideas"] = self._dedupe(self.data["key_ideas"])[:7]
        self.data["quotes"] = self._dedupe(self.data["quotes"])[:5]
        if len(self.data["chapters"]) > 50:
            self.data["chapters"] = self.data["chapters"][:50]

    @staticmethod
    def _dedupe(items):
        seen, out = set(), []
        for it in items:
            k = it.strip().lower()[:80]
            if k and k not in seen:
                seen.add(k)
                out.append(it.strip())
        return out

    # ── Качество результата ───────────────────────────────────
    @staticmethod
    def _is_poor(book) -> bool:
        """True, если обычный парсер мало что достал — есть смысл звать LLM."""
        score = 0
        if book.title and book.title not in ("", "Без названия"):
            score += 2
        if book.author and book.author not in ("", "Неизвестен"):
            score += 2
        if book.cover_url:
            score += 1
        if book.short_description and len(book.short_description) > 50:
            score += 1
        if book.year:
            score += 1
        return score < 4

    @staticmethod
    def _merge_better(primary, secondary):
        """Мердж: secondary дополняет пустые поля primary, не затирая заполненные."""
        if not secondary:
            return primary
        # Простые поля
        if not primary.title or primary.title == "Без названия":
            primary.title = secondary.title
        if not primary.author or primary.author == "Неизвестен":
            primary.author = secondary.author
        if not primary.year:
            primary.year = secondary.year
        if not primary.cover_url:
            primary.cover_url = secondary.cover_url
        if not primary.short_description or len(primary.short_description) < 30:
            primary.short_description = secondary.short_description
        if not primary.isbn:
            primary.isbn = secondary.isbn
        if not primary.page_count:
            primary.page_count = secondary.page_count
        if not primary.genre:
            primary.genre = secondary.genre
        # Списки — мерджим уникальные
        seen = {x.lower()[:80] for x in primary.key_ideas}
        for x in secondary.key_ideas:
            if x.lower()[:80] not in seen:
                primary.key_ideas.append(x)
                seen.add(x.lower()[:80])
        primary.key_ideas = primary.key_ideas[:7]
        seen = {x.lower()[:80] for x in primary.quotes}
        for x in secondary.quotes:
            if x.lower()[:80] not in seen:
                primary.quotes.append(x)
                seen.add(x.lower()[:80])
        primary.quotes = primary.quotes[:5]
        # Главы
        seen = {c.title.lower() for c in primary.chapters}
        for c in secondary.chapters:
            if c.title.lower() not in seen:
                c.number = len(primary.chapters) + 1
                primary.chapters.append(c)
                seen.add(c.title.lower())
        return primary
