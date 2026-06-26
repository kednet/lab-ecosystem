"""
Pydantic-модели данных для WishLibrarian.

Описывают структуру книг, глав, отзывов, научных статей и т.д.
"""
from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field, HttpUrl


class ChapterInfo(BaseModel):
    """Информация о главе книги."""

    number: int = Field(..., ge=0)
    title: str
    summary: Optional[str] = None
    key_points: List[str] = Field(default_factory=list)


class BookInfo(BaseModel):
    """Метаданные книги, извлечённые парсером."""

    title: str
    author: str
    year: Optional[int] = None
    source_url: str
    # URL обложки с сайта-источника (Литрес, Лабиринт и т.п.).
    # Используется парсерами как факт-источник, но НЕ для рендера на нашем сайте
    # (юридические риски). Для рендера используется локально сгенерированная
    # SVG-обложка из agent/cover/generator.py.
    cover_url: Optional[str] = None

    short_description: Optional[str] = None
    key_ideas: List[str] = Field(default_factory=list)
    quotes: List[str] = Field(default_factory=list)
    chapters: List[ChapterInfo] = Field(default_factory=list)

    genre: Optional[str] = None
    original_title: Optional[str] = None
    isbn: Optional[str] = None
    page_count: Optional[int] = None

    raw_html_path: Optional[str] = None
    parsed_at: datetime = Field(default_factory=lambda: datetime.now())

    def folder_name(self) -> str:
        """Сгенерировать имя папки: {Автор}{Название}{Год}."""
        # Убираем недопустимые символы
        def _safe(s: str) -> str:
            return "".join(c for c in s if c.isalnum() or c in " _-").strip()

        author = _safe(self.author or "Unknown")
        title = _safe(self.title or "Untitled")
        year = f"{self.year}" if self.year else ""
        parts = [author, title]
        if year:
            parts.append(year)
        return "_".join(p for p in parts if p).replace(" ", "_")

    def fingerprint(self) -> str:
        """Канонический отпечаток для дедупа (ISBN → (author+title+year))."""
        from agent.utils.normalize import book_fingerprint
        return book_fingerprint(self.title, self.author, self.year, self.isbn)


class Review(BaseModel):
    """Один отзыв."""

    author: str
    rating: Optional[float] = None
    text: str
    source: str = "LiveLib"
    url: Optional[str] = None
    date: Optional[str] = None


class ReviewBundle(BaseModel):
    """Набор отзывов о книге."""

    book_title: str
    average_rating: Optional[float] = None
    total_reviews: int = 0
    reviews: List[Review] = Field(default_factory=list)
    pros: List[str] = Field(default_factory=list)
    cons: List[str] = Field(default_factory=list)


class ScientificArticle(BaseModel):
    """Научная статья."""

    title: str
    authors: List[str] = Field(default_factory=list)
    abstract: Optional[str] = None
    url: str
    year: Optional[int] = None
    journal: Optional[str] = None
    citation_count: Optional[int] = None
    keywords: List[str] = Field(default_factory=list)


class AffiliateLink(BaseModel):
    """Партнёрская ссылка на магазин."""

    store: str
    url: str
    price: Optional[str] = None
    partner_id: Optional[str] = None


class BookAssets(BaseModel):
    """Все артефакты, сгенерированные для одной книги."""

    book: BookInfo
    summary_path: Optional[str] = None
    workbook_path: Optional[str] = None
    reviews_path: Optional[str] = None
    tips_path: Optional[str] = None
    scientific_path: Optional[str] = None
    buy_links_path: Optional[str] = None
    metadata_path: Optional[str] = None
    cover_path: Optional[str] = None
    raw_path: Optional[str] = None

    # SEO-артефакты (от SEO Advisor skill)
    seo_meta_path: Optional[str] = None          # seo/meta.json + seo/meta.md
    seo_schema_path: Optional[str] = None        # seo/schema.json (JSON-LD)
    seo_og_path: Optional[str] = None            # seo/og.md (OG/VK/Twitter мета)
    seo_slug_path: Optional[str] = None          # seo/slug.txt
    seo_report_path: Optional[str] = None        # seo/seo-report.md (полный отчёт)
    seo_faq_path: Optional[str] = None           # seo/faq.md (FAQ-блок + JSON-LD)
    seo_keywords_path: Optional[str] = None      # seo/keywords.md (LSI + PAA)

    folder: Optional[str] = None
    processed_at: Optional[datetime] = None
    errors: List[str] = Field(default_factory=list)
