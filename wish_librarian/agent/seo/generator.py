"""
SEOPackageGenerator — собирает полный SEO-пакет из BookInfo.

Не вызывает AI (детерминированный, без токенов) — генерирует SEO на основе:
- Метаданных книги (title, author, year, genre)
- LSI-базы по жанру
- Шаблонов из seo-advisor-skill

Включает опциональный AI-вызов для FAQ-ответов (--seo-ai-faq).
"""
from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Tuple

from agent.models import BookInfo
from agent.seo.lsi import get_lsi_for_book
from agent.seo.models import (
    SEOMeta,
    SEOFAQ,
    SEOFAQItem,
    SEOOGImage,
    SEOOGMeta,
    SEOSchema,
    SEOKeywords,
    SEOKeywordGroup,
    SEOPackage,
)
from agent.seo.slug import slugify, make_canonical_url


# ── Конфиг ────────────────────────────────────────────────────
SITE_BASE = "https://lab.com"
LIBRARY_PREFIX = "/library/"
SITE_NAME = "Лаборатория желаний"
OG_IMAGE_BASE = f"{SITE_BASE}/img/og"
DEFAULT_COVER_OG = f"{OG_IMAGE_BASE}/book-default.jpg"
SKILL_VERSION = "2.0"

# Описания-шаблоны (Description generator)
DESC_FORMULAS = [
    "Краткий конспект «{title}» {author}. Ключевые идеи, цитаты, выводы и практический воркбук для {topic}.",
    "Читайте краткий конспект книги «{title}» {author}. {quote_count} ключевых идей, {workbook_count} практических заданий, воркбук для {topic}.",
    "«{title}» {author} — {genre_phrase}. Краткий конспект, идеи, цитаты, воркбук. Подходит тем, кто изучает {topic}.",
]

# Title-формулы (выбираем лучшую под длину)
TITLE_FORMULAS = [
    "{title} — {author}: конспект, воркбук и отзывы",  # 60-70
    "{title}: краткий конспект с воркбуком",  # короткая
    "«{title}» {author} — конспект идей и воркбук",  # средняя
]


# ── Главный генератор ─────────────────────────────────────────
class SEOPackageGenerator:
    """Собирает SEOPackage из BookInfo."""

    def __init__(
        self,
        site_base: str = SITE_BASE,
        site_name: str = SITE_NAME,
        library_prefix: str = LIBRARY_PREFIX,
        og_image_base: str = OG_IMAGE_BASE,
    ):
        self.site_base = site_base
        self.site_name = site_name
        self.library_prefix = library_prefix
        self.og_image_base = og_image_base

    # ── Slug + Canonical ──────────────────────────────────────
    def make_slug(self, book: BookInfo) -> str:
        return slugify(f"{book.title} {book.author}", max_length=60)

    def make_canonical(self, slug: str) -> str:
        return make_canonical_url(slug, self.site_base, self.library_prefix)

    # ── Title ────────────────────────────────────────────────
    def make_title(self, book: BookInfo) -> str:
        # Пробуем формулы по порядку, выбираем первую подходящую по длине
        candidates = [
            f"{book.title} — {book.author}: конспект, воркбук и отзывы",
            f"{book.title} — {book.author}: конспект и воркбук",
            f"{book.title}: краткий конспект с воркбуком",
        ]
        for c in candidates:
            if 50 <= len(c) <= 70:
                return c
        # Если все не подошли — берём самую короткую
        return min(candidates, key=len)

    # ── Description ──────────────────────────────────────────
    def make_description(self, book: BookInfo) -> str:
        topic = self._guess_topic(book)
        genre_phrase = self._genre_phrase(book)
        # Берём первую формулу, проверяем длину
        desc = DESC_FORMULAS[0].format(
            title=book.title,
            author=book.author,
            topic=topic,
            genre_phrase=genre_phrase,
            quote_count="5-7",
            workbook_count="10+",
        )
        # Подрезаем до 160
        if len(desc) > 160:
            desc = desc[:157].rsplit(' ', 1)[0] + "…"
        if len(desc) < 100:
            desc = f"{desc} Читайте онлайн бесплатно на {self.site_name}."
        # Гарантируем 100-160
        if len(desc) < 100:
            return desc.ljust(120, " — подробный разбор с примерами")
        return desc[:160].rsplit(' ', 1)[0] if len(desc) >= 160 else desc

    # ── Keywords ─────────────────────────────────────────────
    def make_keywords(self, book: BookInfo) -> List[str]:
        """Главный ключ + бренд + жанр + формат."""
        base = [
            f"конспект {book.title.lower()}",
            f"{book.author} книга",
            f"{book.title.lower()} краткое содержание",
            f"воркбук {book.title.lower()}",
            "саморазвитие",
            self.site_name.lower(),
        ]
        if book.genre:
            base.insert(0, book.genre.lower())
        # Уникальные, непустые
        seen, out = set(), []
        for k in base:
            k = k.strip()
            if k and k not in seen:
                seen.add(k)
                out.append(k)
        return out[:10]

    # ── Schema.org ───────────────────────────────────────────
    def make_schema(self, book: BookInfo, slug: str, faq: SEOFAQ) -> SEOSchema:
        canonical = self.make_canonical(slug)
        graph = []

        # 1. Book
        book_block = {
            "@type": "Book",
            "name": book.title,
            "bookFormat": "https://schema.org/EBook",
            "inLanguage": "ru",
            "author": {"@type": "Person", "name": book.author},
        }
        if book.isbn:
            book_block["isbn"] = book.isbn
        if book.year:
            book_block["datePublished"] = str(book.year)
        if book.page_count:
            book_block["numberOfPages"] = book.page_count
        if book.cover_url:
            book_block["image"] = book.cover_url
        if book.short_description:
            book_block["description"] = book.short_description[:300]
        if book.genre:
            book_block["genre"] = book.genre
        graph.append(book_block)

        # 2. BreadcrumbList
        graph.append({
            "@type": "BreadcrumbList",
            "itemListElement": [
                {"@type": "ListItem", "position": 1, "name": "Главная", "item": f"{self.site_base}/"},
                {"@type": "ListItem", "position": 2, "name": "Библиотека", "item": f"{self.site_base}{self.library_prefix}"},
                {"@type": "ListItem", "position": 3, "name": book.title},
            ],
        })

        # 3. FAQPage (если есть FAQ)
        if faq.items:
            graph.append(faq.to_jsonld())

        return SEOSchema(graph=graph)

    # ── OG / VK / Twitter ────────────────────────────────────
    def make_og(self, book: BookInfo, slug: str, meta: SEOMeta) -> SEOOGMeta:
        canonical = self.make_canonical(slug)
        image_url = book.cover_url or f"{self.og_image_base}/{slug}.jpg"
        image_alt = f"Обложка книги «{book.title}» {book.author}"

        return SEOOGMeta(
            og_type="book",
            og_title=meta.title[:90],
            og_description=meta.description[:200],
            og_image=SEOOGImage(url=image_url, width=1200, height=630, alt=image_alt),
            og_url=canonical,
            og_locale="ru_RU",
            og_site_name=self.site_name,
            book_author=book.author,
            book_isbn=book.isbn,
            book_release_date=str(book.year) if book.year else None,
            twitter_card="summary_large_image",
            twitter_title=meta.title[:70],
            twitter_description=meta.description[:200],
            twitter_image=image_url,
            vk_image=image_url,
        )

    # ── FAQ ──────────────────────────────────────────────────
    def make_faq(self, book: BookInfo, use_ai: bool = False, ai_client=None) -> SEOFAQ:
        """
        Генерирует 4-5 вопросов по книге.
        - use_ai=False (default): детерминированные вопросы-шаблоны + краткие ответы из метаданных
        - use_ai=True: через AI-клиент (Claude/Yandex) → более качественные ответы, но тратит токены
        """
        questions = self._faq_templates(book)
        if use_ai and ai_client is not None:
            try:
                return self._faq_via_ai(book, questions, ai_client)
            except Exception:
                pass  # fallback на детерминированные
        # Детерминированные ответы
        items = [self._faq_deterministic(book, q) for q in questions]
        return SEOFAQ(items=items)

    def _faq_templates(self, book: BookInfo) -> List[str]:
        """5 типовых вопросов для любой книги саморазвития."""
        return [
            f"О чём книга «{book.title}» {book.author}?",
            f"Какие основные идеи книги «{book.title}»?",
            f"Стоит ли читать «{book.title}»?",
            f"Кто автор книги «{book.title}»?",
            f"Где купить книгу «{book.title}»?",
        ]

    def _faq_deterministic(self, book: BookInfo, question: str) -> SEOFAQItem:
        """Сгенерировать детерминированный ответ (без AI)."""
        topic = self._guess_topic(book)
        if "О чём" in question:
            ans = (
                f"«{book.title}» {book.author} — книга о {topic}. "
                f"Автор раскрывает ключевые принципы, которые можно применить на практике. "
                f"Издание относится к жанру {book.genre or 'саморазвития'}. "
                f"Книга содержит практические методы и воркбук для самостоятельной работы."
            )
        elif "основные идеи" in question or "ключевые" in question:
            ans = (
                f"Среди ключевых идей «{book.title}» — изменение мышления, "
                f"работа с вниманием и применение практических техник. "
                f"Автор показывает, как перенести принципы книги в повседневную жизнь. "
                f"Подробный разбор идей — в нашем конспекте."
            )
        elif "Стоит ли" in question:
            ans = (
                f"Да, если вам интересна тема {topic}. "
                f"Книга даёт практические инструменты, "
                f"которые можно применить сразу после прочтения. "
                f"Подходит тем, кто готов работать над собой."
            )
        elif "Кто автор" in question:
            ans = (
                f"{book.author} — автор книги «{book.title}» "
                f"{f'({book.year} г.)' if book.year else ''}. "
                f"Известен работами в жанре {book.genre or 'саморазвития'}. "
                f"Подробнее об авторе и его методе — в нашем конспекте."
            )
        else:  # "Где купить"
            ans = (
                f"Купить «{book.title}» {book.author} можно в крупных книжных магазинах, "
                f"а также в электронных библиотеках (Литрес, Bookmate). "
                f"Партнёрские ссылки на магазины — на странице книги."
            )
        return SEOFAQItem(question=question, answer=ans)

    def _faq_via_ai(self, book: BookInfo, questions: List[str], ai_client) -> SEOFAQ:
        """Сгенерировать FAQ через AI-клиент (использует токены)."""
        from agent.ai.prompts import build_system_prompt, render_user_prompt
        prompt = (
            f"Сгенерируй 4 коротких ответа (40-60 слов каждый) на вопросы о книге "
            f"«{book.title}» автора {book.author}. Жанр: {book.genre or 'саморазвитие'}. "
            f"Описание: {book.short_description or '—'}. "
            f"Вопросы:\n" + "\n".join(f"{i+1}. {q}" for i, q in enumerate(questions)) +
            f"\n\nФормат: каждый ответ на отдельной строке, начни с номера вопроса. "
            f"Без воды, конкретика, без дисклеймеров в ответах."
        )
        try:
            content = ai_client.generate(
                system="Ты — SEO-копирайтер. Генерируешь FAQ для книжного сайта.",
                user=prompt,
                max_tokens=800,
            )
        except Exception:
            return self._faq_deterministic_book(book, questions)

        # Парсим ответы
        items: List[SEOFAQItem] = []
        current_q = None
        current_a: List[str] = []
        for line in content.splitlines():
            m = re.match(r"^\s*(\d+)\.\s+(.+)$", line)
            if m and m.group(2).endswith("?"):
                if current_q and current_a:
                    items.append(SEOFAQItem(question=current_q, answer=" ".join(current_a).strip()))
                current_q = m.group(2)
                current_a = []
            elif current_q and line.strip():
                current_a.append(line.strip())
        if current_q and current_a:
            items.append(SEOFAQItem(question=current_q, answer=" ".join(current_a).strip()))
        # Если парсер сломался — fallback
        if not items:
            return self._faq_deterministic_book(book, questions)
        return SEOFAQ(items=items[:5])

    def _faq_deterministic_book(self, book: BookInfo, questions: List[str]) -> SEOFAQ:
        return SEOFAQ(items=[self._faq_deterministic(book, q) for q in questions])

    # ── Keywords / LSI ───────────────────────────────────────
    def make_keywords_full(self, book: BookInfo) -> SEOKeywords:
        topic = self._guess_topic(book)
        title_l = book.title.lower()
        author_l = book.author.lower()

        high = [
            title_l,
            f"{author_l} книга",
            f"книга {title_l}",
        ]
        mid = [
            f"конспект {title_l}",
            f"воркбук {title_l}",
            f"{title_l} краткое содержание",
            f"{title_l} отзывы",
        ]
        low = [
            f"о чём книга {title_l}",
            f"{title_l} идеи",
            f"{title_l} цитаты",
            f"как применить {title_l}",
        ]
        long_tail = [
            f"конспект {title_l} {author_l}",
            f"воркбук {title_l} скачать pdf",
            f"стоит ли читать {title_l}",
        ]
        # LSI по жанру
        genres = [book.genre] if book.genre else None
        lsi = get_lsi_for_book(genres, max_n=15)

        return SEOKeywords(
            main_keyword=title_l,
            groups=SEOKeywordGroup(
                high_freq=high,
                mid_freq=mid,
                low_freq=low,
                long_tail=long_tail,
                lsi=lsi,
            ),
            intent="informational",
        )

    # ── Хелперы ──────────────────────────────────────────────
    def _guess_topic(self, book: BookInfo) -> str:
        """Определить тему по жанру/названию (простая эвристика)."""
        if book.genre:
            g = book.genre.lower()
            if "психолог" in g:
                return "психологии и самопознания"
            if "трансерф" in g or "эзотер" in g:
                return "исполнения желаний и управления реальностью"
            if "духовн" in g:
                return "духовного развития"
            if "бизнес" in g:
                return "бизнеса и карьеры"
            if "финанс" in g:
                return "финансов и инвестиций"
            if "здоров" in g:
                return "здоровья и образа жизни"
            if "отношен" in g:
                return "отношений и коммуникации"
        # Fallback по ключевым словам в title
        t = book.title.lower()
        if any(w in t for w in ("желан", "трансерф", "реальност")):
            return "исполнения желаний"
        if any(w in t for w in ("псих", "мышлен", "привыч")):
            return "психологии и самопознания"
        if any(w in t for w in ("деньг", "финанс", "инвест", "капитал")):
            return "финансов"
        return "саморазвития"

    def _genre_phrase(self, book: BookInfo) -> str:
        """Сгенерировать фразу жанра для description."""
        if not book.genre:
            return "книга по саморазвитию"
        return f"книга по теме «{book.genre}»"

    # ── Главная сборка ────────────────────────────────────────
    def generate(
        self,
        book: BookInfo,
        *,
        use_ai_faq: bool = False,
        ai_client=None,
    ) -> SEOPackage:
        """Собрать полный SEO-пакет для книги."""
        slug = self.make_slug(book)
        title = self.make_title(book)
        desc = self.make_description(book)
        keywords = self.make_keywords(book)
        canonical = self.make_canonical(slug)
        meta = SEOMeta(
            title=title,
            description=desc,
            keywords=keywords,
            canonical=canonical,
            author=book.author,
        )
        faq = self.make_faq(book, use_ai=use_ai_faq, ai_client=ai_client)
        schema = self.make_schema(book, slug, faq)
        og = self.make_og(book, slug, meta)
        kw_full = self.make_keywords_full(book)

        return SEOPackage(
            book_title=book.title,
            book_author=book.author,
            book_year=book.year,
            book_isbn=book.isbn,
            book_genre=book.genre,
            book_description=book.short_description,
            slug=slug,
            meta=meta,
            schema_block=schema,
            og=og,
            faq=faq,
            keywords=kw_full,
            intent="informational",
            has_ymyl_warning=True,
            generated_at=datetime.now().isoformat(timespec="seconds"),
            skill_version=SKILL_VERSION,
        )


# ── Рендереры файлов (выход) ──────────────────────────────────
def render_seo_files(pkg: SEOPackage, out_dir: Path) -> dict[str, str]:
    """
    Записать SEO-пакет в файлы в out_dir (обычно <book_folder>/seo/).
    Возвращает словарь {file_role: path}.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    paths: dict[str, str] = {}

    # 1. meta.md — Title/Description/Keywords (в формате HTML для копипаста)
    meta_md = (
        f"# SEO-мета-теги: {pkg.book_title}\n\n"
        f"<!-- Сгенерировано SEO Advisor skill v{pkg.skill_version} -->\n\n"
        f"```html\n"
        f"<title>{_esc(pkg.meta.title)}</title>\n"
        f'<meta name="description" content="{_esc(pkg.meta.description)}">\n'
        f'<meta name="keywords" content="{", ".join(pkg.meta.keywords)}">\n'
        f'<meta name="author" content="{_esc(pkg.meta.author or "")}">\n'
        f'<meta name="robots" content="{pkg.meta.robots}">\n'
        f'<link rel="canonical" href="{pkg.meta.canonical}">\n'
        f"```\n"
    )
    p = out_dir / "meta.md"
    p.write_text(meta_md, encoding="utf-8")
    paths["meta_md"] = str(p)

    # 2. meta.json — для парсинга из Publisher
    p = out_dir / "meta.json"
    p.write_text(
        pkg.meta.model_dump_json(indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    paths["meta_json"] = str(p)

    # 3. schema.json — JSON-LD (готов для вставки в <head>)
    p = out_dir / "schema.json"
    p.write_text(
        json.dumps(pkg.schema_block.to_jsonld(), indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    paths["schema"] = str(p)

    # 4. og.md — OG/VK/Twitter мета в HTML-формате
    og_md = _render_og_md(pkg)
    p = out_dir / "og.md"
    p.write_text(og_md, encoding="utf-8")
    paths["og"] = str(p)

    # 5. faq.md — FAQ-блок + JSON-LD + видимый HTML
    faq_md = _render_faq_md(pkg)
    p = out_dir / "faq.md"
    p.write_text(faq_md, encoding="utf-8")
    paths["faq"] = str(p)

    # 6. keywords.md — семантическое ядро + LSI
    kw_md = _render_keywords_md(pkg)
    p = out_dir / "keywords.md"
    p.write_text(kw_md, encoding="utf-8")
    paths["keywords"] = str(p)

    # 7. slug.txt — короткий, для использования в URL
    p = out_dir / "slug.txt"
    p.write_text(pkg.slug, encoding="utf-8")
    paths["slug"] = str(p)

    # 8. seo-report.md — полный SEO-отчёт (человекочитаемый)
    report_md = _render_report_md(pkg)
    p = out_dir / "seo-report.md"
    p.write_text(report_md, encoding="utf-8")
    paths["report"] = str(p)

    return paths


def _esc(s: str) -> str:
    """Escape для HTML-атрибутов."""
    return s.replace('"', '&quot;').replace('<', '&lt;').replace('>', '&gt;')


def _render_og_md(pkg: SEOPackage) -> str:
    """Рендер OG/VK/Twitter мета-тегов в HTML-блок."""
    og = pkg.og
    lines = [
        f"# OG / VK / Twitter превью: {pkg.book_title}",
        "",
        f"<!-- Сгенерировано SEO Advisor skill v{pkg.skill_version} -->",
        "",
        "```html",
        f'<meta property="og:type" content="{og.og_type}">',
        f'<meta property="og:title" content="{_esc(og.og_title)}">',
        f'<meta property="og:description" content="{_esc(og.og_description)}">',
        f'<meta property="og:image" content="{og.og_image.url}">',
        f'<meta property="og:image:width" content="{og.og_image.width}">',
        f'<meta property="og:image:height" content="{og.og_image.height}">',
        f'<meta property="og:image:alt" content="{_esc(og.og_image.alt)}">',
        f'<meta property="og:url" content="{og.og_url}">',
        f'<meta property="og:locale" content="{og.og_locale}">',
        f'<meta property="og:site_name" content="{_esc(og.og_site_name)}">',
    ]
    if og.book_author:
        lines.append(f'<meta property="book:author" content="{_esc(og.book_author)}">')
    if og.book_isbn:
        lines.append(f'<meta property="book:isbn" content="{_esc(og.book_isbn)}">')
    if og.book_release_date:
        lines.append(f'<meta property="book:release_date" content="{og.book_release_date}">')
    lines += [
        "",
        f'<meta name="twitter:card" content="{og.twitter_card}">',
        f'<meta name="twitter:title" content="{_esc(og.twitter_title)}">',
        f'<meta name="twitter:description" content="{_esc(og.twitter_description)}">',
        f'<meta name="twitter:image" content="{og.twitter_image}">',
    ]
    if og.vk_image:
        lines.append(f'<meta property="vk:image" content="{og.vk_image}">')
    lines.append("```")
    return "\n".join(lines) + "\n"


def _render_faq_md(pkg: SEOPackage) -> str:
    """Рендер FAQ-блока: видимый HTML + JSON-LD."""
    lines = [
        f"# FAQ-блок: {pkg.book_title}",
        "",
        f"<!-- Сгенерировано SEO Advisor skill v{pkg.skill_version} -->",
        "",
        "## Видимый HTML (вставить в конец страницы)",
        "",
        "```html",
        '<section class="faq" itemscope itemtype="https://schema.org/FAQPage">',
        '  <h2>Часто задаваемые вопросы</h2>',
    ]
    for item in pkg.faq.items:
        lines += [
            '  <div itemscope itemprop="mainEntity" itemtype="https://schema.org/Question">',
            f'    <h3 itemprop="name">{_esc(item.question)}</h3>',
            '    <div itemscope itemprop="acceptedAnswer" itemtype="https://schema.org/Answer">',
            f'      <p itemprop="text">{_esc(item.answer)}</p>',
            '    </div>',
            '  </div>',
        ]
    lines += ["</section>", "```", "", "## JSON-LD (FAQPage) для вставки в <head>", "", "```json"]
    lines.append(json.dumps(pkg.faq.to_jsonld(), indent=2, ensure_ascii=False))
    lines.append("```")
    return "\n".join(lines) + "\n"


def _render_keywords_md(pkg: SEOPackage) -> str:
    """Рендер семантического ядра."""
    kw = pkg.keywords
    g = kw.groups
    lines = [
        f"# Семантическое ядро: {pkg.book_title}",
        "",
        f"**Главный ключ:** `{kw.main_keyword}`  ",
        f"**Интент:** {kw.intent}  ",
        f"**Skill version:** v{pkg.skill_version}",
        "",
        "## Высокочастотные (ВЧ)",
        *[f"- {k}" for k in g.high_freq],
        "",
        "## Среднечастотные (СЧ)",
        *[f"- {k}" for k in g.mid_freq],
        "",
        "## Низкочастотные (НЧ) — длинный хвост",
        *[f"- {k}" for k in g.low_freq],
        "",
        "## Длинный хвост (long-tail)",
        *[f"- {k}" for k in g.long_tail],
        "",
        "## LSI-слова (топикальное покрытие)",
        *[f"- {k}" for k in g.lsi],
        "",
        "## Рекомендация по использованию",
        "1. Главный ключ — в Title, H1, первые 100 слов",
        "2. LSI-слова — распределить по тексту естественно, не пытаясь впихнуть все",
        "3. Длинный хвост — в H3-заголовках, FAQ, alt-тегах",
        "4. НЧ — во внутренних ссылках и PAA-вопросах",
    ]
    return "\n".join(lines) + "\n"


def _render_report_md(pkg: SEOPackage) -> str:
    """Полный SEO-отчёт (по промпту SKILL.md)."""
    lines = [
        f"# SEO-отчёт: {pkg.book_title}",
        "",
        f"**Автор:** {pkg.book_author}  ",
        f"**Год:** {pkg.book_year or '—'}  ",
        f"**ISBN:** {pkg.book_isbn or '—'}  ",
        f"**Жанр:** {pkg.book_genre or '—'}  ",
        f"**Slug:** `/{pkg.slug}/`  ",
        f"**Canonical:** {pkg.meta.canonical}  ",
        f"**Интент:** {pkg.intent}  ",
        f"**Сгенерировано:** {pkg.generated_at}  ",
        f"**Skill:** SEO Advisor v{pkg.skill_version}",
        "",
        "## ✅ Готовые артефакты",
        "",
        "| Файл | Описание |",
        "|------|----------|",
        "| `meta.md` | Title / Description / Keywords (HTML) |",
        "| `meta.json` | Мета в JSON (для Publisher) |",
        "| `schema.json` | Schema.org JSON-LD (@graph) |",
        "| `og.md` | OG / VK / Twitter превью |",
        "| `faq.md` | FAQ-блок (видимый HTML + JSON-LD) |",
        "| `keywords.md` | Семантическое ядро + LSI |",
        "| `slug.txt` | URL-slug |",
        "| `seo-report.md` | Этот отчёт |",
        "",
        "## 📋 Title",
        f"```\n{pkg.meta.title}\n```",
        f"Длина: {len(pkg.meta.title)} символов (рекомендуется 50-70)",
        "",
        "## 📋 Description",
        f"```\n{pkg.meta.description}\n```",
        f"Длина: {len(pkg.meta.description)} символов (рекомендуется 150-160)",
        "",
        "## 📋 Keywords",
        ", ".join(f"`{k}`" for k in pkg.meta.keywords),
        "",
        "## 📋 Schema.org (@graph)",
        f"Блоков: {len(pkg.schema_block.graph)}",
    ]
    for i, block in enumerate(pkg.schema_block.graph, 1):
        lines.append(f"- Блок {i}: `{block.get('@type', '?')}`")
    lines += [
        "",
        "## 📋 OG / VK / Twitter",
        f"- og:type = `{pkg.og.og_type}`",
        f"- og:image = `{pkg.og.og_image.url}`",
        f"- og:image:alt = `{pkg.og.og_image.alt}`",
        "",
        "## 📋 FAQ",
        f"Вопросов: {len(pkg.faq.items)}",
    ]
    for i, item in enumerate(pkg.faq.items, 1):
        lines.append(f"{i}. {item.question}")
    lines += [
        "",
        "## ⚠️ Дисклеймер (YMYL)",
        "Ниша саморазвития — обязателен дисклеймер:",
        "",
        "```html",
        '<div class="disclaimer">',
        "  ⚠️ <strong>Важно:</strong> Конспект носит информационный характер",
        "  и не заменяет чтение оригинала. Авторская методика, эффективность",
        "  индивидуальна. При наличии психических проблем обратитесь к специалисту.",
        "</div>",
        "```",
        "",
        "## 🎯 Чек-лист внедрения",
        "",
        "- [ ] Title и Description в <head>",
        "- [ ] OG/VK/Twitter мета в <head>",
        "- [ ] Schema JSON-LD в <head> или перед </body>",
        "- [ ] Canonical <link>",
        "- [ ] H1-H3 структура (см. SKILL.md промпт page-optimization)",
        "- [ ] Текст 1500+ слов (для полного конспекта)",
        "- [ ] alt-теги на обложке с ключом",
        "- [ ] Внутренние ссылки (2-5 на страницу)",
        "- [ ] Дисклеймер (YMYL)",
        "- [ ] FAQ-блок (5-7 вопросов)",
        "- [ ] Дата публикации и обновления",
        "- [ ] Schema-validate: `python scripts/schema-validate.py <html>`",
        "",
        "## 🔗 Следующие шаги",
        "1. Publisher (C:/Users/kfigh/publisher_agent/) подхватит `seo/meta.json` + `seo/schema.json`",
        "2. На странице вставляется готовый HTML из `seo/meta.md` + `seo/og.md`",
        "3. FAQ вставляется в конец страницы из `seo/faq.md`",
        "4. После публикации — запуск `/seo audit` для проверки",
    ]
    return "\n".join(lines) + "\n"
