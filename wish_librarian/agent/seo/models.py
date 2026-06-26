"""
Pydantic-модели для SEO-пакета.
"""
from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field


class SEOMeta(BaseModel):
    """Мета-теги страницы."""
    title: str = Field(..., min_length=20, max_length=90)
    description: str = Field(..., min_length=100, max_length=200)
    keywords: List[str] = Field(default_factory=list)
    canonical: Optional[str] = None
    author: Optional[str] = None
    robots: str = "index, follow"
    language: str = "ru"


class SEOFAQItem(BaseModel):
    """Один вопрос FAQ."""
    question: str
    answer: str = Field(..., min_length=20, max_length=600)


class SEOFAQ(BaseModel):
    """FAQ-блок для страницы."""
    items: List[SEOFAQItem] = Field(default_factory=list)

    def to_jsonld(self) -> dict:
        """Генерация JSON-LD FAQPage schema."""
        return {
            "@context": "https://schema.org",
            "@type": "FAQPage",
            "mainEntity": [
                {
                    "@type": "Question",
                    "name": item.question,
                    "acceptedAnswer": {
                        "@type": "Answer",
                        "text": item.answer,
                    },
                }
                for item in self.items
            ],
        }


class SEOKeywordGroup(BaseModel):
    """Группа ключей по типу."""
    high_freq: List[str] = Field(default_factory=list)        # ВЧ
    mid_freq: List[str] = Field(default_factory=list)         # СЧ
    low_freq: List[str] = Field(default_factory=list)         # НЧ
    long_tail: List[str] = Field(default_factory=list)        # длинный хвост
    lsi: List[str] = Field(default_factory=list)              # LSI-слова


class SEOKeywords(BaseModel):
    """Семантическое ядро страницы."""
    main_keyword: str
    groups: SEOKeywordGroup
    intent: str = "informational"  # informational / commercial / transactional / navigational


class SEOSchema(BaseModel):
    """Schema.org JSON-LD блок (или @graph из нескольких)."""
    graph: List[dict] = Field(default_factory=list)

    def to_jsonld(self) -> dict:
        """Вернуть полный JSON-LD с @graph или одним блоком."""
        if len(self.graph) == 1:
            return self.graph[0]
        return {
            "@context": "https://schema.org",
            "@graph": self.graph,
        }


class SEOOGImage(BaseModel):
    url: str
    width: int = 1200
    height: int = 630
    alt: str = ""


class SEOOGMeta(BaseModel):
    """Open Graph + Twitter Card + VK мета-теги."""
    og_type: str = "book"
    og_title: str
    og_description: str
    og_image: SEOOGImage
    og_url: str
    og_locale: str = "ru_RU"
    og_site_name: str = "Лаборатория желаний"
    book_author: Optional[str] = None
    book_isbn: Optional[str] = None
    book_release_date: Optional[str] = None
    twitter_card: str = "summary_large_image"
    twitter_title: str
    twitter_description: str
    twitter_image: str
    vk_image: Optional[str] = None


class SEOPackage(BaseModel):
    """Полный SEO-пакет для книги."""
    book_title: str
    book_author: str
    book_year: Optional[int] = None
    book_isbn: Optional[str] = None
    book_genre: Optional[str] = None
    book_description: Optional[str] = None

    slug: str
    meta: SEOMeta
    schema_block: SEOSchema = Field(alias="schema")
    og: SEOOGMeta
    faq: SEOFAQ
    keywords: SEOKeywords

    # Мета
    intent: str = "informational"
    has_ymyl_warning: bool = True
    generated_at: Optional[str] = None
    skill_version: str = "2.0"

    model_config = {"populate_by_name": True}
