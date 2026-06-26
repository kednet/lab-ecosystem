"""Парсеры WishLibrarian."""
from agent.parsers.base_parser import BaseParser, FetchError, ParseError
from agent.parsers.koob_parser import KoobParser
from agent.parsers.scientific_parser import ScientificParser
from agent.parsers.reviews_parser import ReviewsParser
from agent.parsers.affiliate_links import AffiliateLinksGenerator

__all__ = [
    "BaseParser",
    "FetchError",
    "ParseError",
    "KoobParser",
    "ScientificParser",
    "ReviewsParser",
    "AffiliateLinksGenerator",
]
