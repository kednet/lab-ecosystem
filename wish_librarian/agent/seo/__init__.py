"""
SEO Advisor — модуль для WishLibrarian.

Автоматически генерирует SEO-пакет для каждой обработанной книги:
- Meta Title / Description / Keywords
- URL-slug
- Schema.org JSON-LD (Book + FAQ + Breadcrumb)
- OG / VK / Twitter превью
- FAQ-блок с PAA-вопросами
- Семантическое ядро + LSI
- Полный SEO-отчёт (отчёт SEO Advisor skill)

Использует логику из C:/Users/kfigh/seo-advisor-skill/
(промпты, шаблоны, data-файлы, Python-скрипты).

Включение:
  python -m agent.cli --url ... --seo
  python -m agent.cli --url ... --no-seo
  или через .env: SEO_AUTO=true
"""
from __future__ import annotations

from agent.seo.generator import SEOPackageGenerator, render_seo_files
from agent.seo.models import (
    SEOPackage,
    SEOMeta,
    SEOSchema,
    SEOFAQ,
    SEOKeywords,
    SEOOGMeta,
    SEOFAQItem,
    SEOKeywordGroup,
    SEOOGImage,
)

__all__ = [
    "SEOPackageGenerator",
    "render_seo_files",
    "SEOPackage",
    "SEOMeta",
    "SEOSchema",
    "SEOFAQ",
    "SEOFAQItem",
    "SEOKeywords",
    "SEOKeywordGroup",
    "SEOOGMeta",
    "SEOOGImage",
]
