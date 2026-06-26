"""Affiliate links integration: AdvCake → Литрес.

Публичный API:
    from affiliate_links.advcake import build_litres_url, make_book_affiliate
    from affiliate_links.verify_erid import verify_erid
"""
from .advcake import (
    BookAffiliate,
    build_litres_url,
    build_litres_url_with_label,
    make_book_affiliate,
    cache_book,
    get_cached,
    load_cache,
    save_cache,
    ADVCAKE_HASH,
    ADVCAKE_ERID,
    ADVCAKE_BASE_URL,
)
from .verify_erid import EridStatus, verify_erid

__all__ = [
    "BookAffiliate",
    "build_litres_url",
    "build_litres_url_with_label",
    "make_book_affiliate",
    "cache_book",
    "get_cached",
    "load_cache",
    "save_cache",
    "ADVCAKE_HASH",
    "ADVCAKE_ERID",
    "ADVCAKE_BASE_URL",
    "EridStatus",
    "verify_erid",
]