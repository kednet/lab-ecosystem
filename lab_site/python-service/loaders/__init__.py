"""
Loaders — единая точка входа для данных из WishLibrarian, Reviews Hub и SEO Advisor.

Использование:
    from loaders import (
        load_all_experts, load_expert,
        load_all_review_summaries, load_review_summary,
        load_seo_package,
    )
"""
from .experts import (
    ExpertCard,
    load_expert,
    load_all_experts,
    load_index,
    EXPERTS_HUB_ROOT,
)

from .reviews import (
    ReviewSummary,
    ReviewSource,
    load_review_summary,
    load_all_review_summaries,
    REVIEWS_HUB_ROOT,
    SOURCE_WEIGHTS,
)

from .seo import (
    SeoMeta,
    SeoSchema,
    SeoPackage,
    BookMeta,
    load_seo_package,
    WL_OUTPUT_ROOT,
)

__all__ = [
    # Experts
    "ExpertCard",
    "load_expert",
    "load_all_experts",
    "load_index",
    "EXPERTS_HUB_ROOT",
    # Reviews
    "ReviewSummary",
    "ReviewSource",
    "load_review_summary",
    "load_all_review_summaries",
    "REVIEWS_HUB_ROOT",
    "SOURCE_WEIGHTS",
    # SEO
    "SeoMeta",
    "SeoSchema",
    "SeoPackage",
    "BookMeta",
    "load_seo_package",
    "WL_OUTPUT_ROOT",
]
