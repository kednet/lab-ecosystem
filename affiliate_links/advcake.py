"""
AdvCake → Литрес affiliate link builder.

Генерирует партнёрские URL по шаблону:

    https://www.litres.ru/<book_path>/?utm_source=advcake
                                    &utm_medium=cpa
                                    &utm_campaign=affiliate
                                    &utm_content=<HASH>
                                    &erid=<ERID>
                                    &advcake_method=1
                                    &m=1
                                    [&subid=<subid>]

Параметры HASH (utm_content) и ERID берутся из .env:
    ADVCAKE_HASH=c280b701         # уникальный ID партнёрской ссылки
    ADVCAKE_ERID=2VfnxyNkZrY      # маркер рекламы (ОRD)
    ADVCAKE_BASE_URL=https://www.litres.ru  # домен Литреса (https, без /)

Usage:
    from affiliate_links.advcake import build_litres_url

    url = build_litres_url("/book/paulo-koelo/alhimik-122351/")
    # → https://www.litres.ru/book/paulo-koelo/alhimik-122351/?utm_source=advcake&...

    url = build_litres_url(
        "/book/paulo-koelo/alhimik-122351/",
        subid="tg_post_2026-06-25_alhimik",
    )

    # Полный набор для поста в ВК/TG:
    link = build_litres_url_with_label(book_path, channel="vk", post_id=42)
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Union
from urllib.parse import urlparse, urlunparse, parse_qsl, urlencode, quote

# ─── Конфигурация из окружения ────────────────────────────────────────────

ADVCAKE_HASH = os.environ.get("ADVCAKE_HASH", "c280b701")
ADVCAKE_ERID = os.environ.get("ADVCAKE_ERID", "2VfnxyNkZrY")
ADVCAKE_BASE_URL = os.environ.get("ADVCAKE_BASE_URL", "https://www.litres.ru").rstrip("/")
ADVCAKE_CAMPAIGN = os.environ.get("ADVCAKE_CAMPAIGN", "affiliate")
ADVCAKE_METHOD = os.environ.get("ADVCAKE_METHOD", "1")  # 1 = postback

# Кеш (файл рядом с модулем, формат JSON)
_CACHE_PATH = Path(__file__).parent / "cache" / "advcake_urls.json"


# ─── Модели ───────────────────────────────────────────────────────────────

@dataclass
class BookAffiliate:
    """Партнёрские ссылки одной книги."""
    slug: str
    book_path: str                     # относительный путь на litres.ru, напр. "/book/paulo-koelo/alhimik-122351/"
    litres_url: str                    # чистый URL Литреса (без UTM)
    advcake_url: str                   # партнёрский URL с UTM + erid
    hash: str                          # ADVCAKE_HASH
    erid: str                          # ADVCAKE_ERID
    subid: Optional[str] = None        # маркер источника (subid)
    generated_at: str = ""             # ISO 8601

    def to_dict(self) -> dict:
        return {k: v for k, v in asdict(self).items() if v not in (None, "")}

    @classmethod
    def from_dict(cls, d: dict) -> "BookAffiliate":
        # Устойчиво к отсутствующим полям
        return cls(
            slug=d.get("slug", ""),
            book_path=d.get("book_path", ""),
            litres_url=d.get("litres_url", ""),
            advcake_url=d.get("advcake_url", ""),
            hash=d.get("hash", ADVCAKE_HASH),
            erid=d.get("erid", ADVCAKE_ERID),
            subid=d.get("subid"),
            generated_at=d.get("generated_at", ""),
        )


# ─── Основные функции ─────────────────────────────────────────────────────

def _normalize_book_path(book_path: str) -> str:
    """'/book/foo/bar-123/' → '/book/foo/bar-123' (без хвостового /).

    На Windows под Git-Bash MSYS2 иногда подставляет префикс
    'C:/Program Files/Git/' к путям вроде '/book/...' (path-conversion).
    Чиним такие случаи — вырезаем ведущий '/<буква диска>:/...' до ближайшего
    '/book/' или '/audiobook/'.
    """
    if not book_path:
        return ""
    # Если это полный URL — выделяем path
    if book_path.startswith("http://") or book_path.startswith("https://"):
        parsed = urlparse(book_path)
        book_path = parsed.path

    book_path = book_path.strip()

    # Фикс MSYS2 path-conversion: '/C:/Program Files/Git/book/foo' → '/book/foo'
    m = re.match(
        r"^/[A-Za-z]:/Program Files/Git(/.*)$",
        book_path,
    )
    if m:
        book_path = m.group(1)

    # Точечно: если где-то посередине всё ещё '/Program Files/Git/' — вырежем
    book_path = book_path.replace("/Program Files/Git/", "/")

    if not book_path.startswith("/"):
        book_path = "/" + book_path
    book_path = book_path.rstrip("/")
    return book_path


def _safe_subid(raw: str) -> str:
    """subid должен быть коротким и безопасным для URL.
    Только [a-zA-Z0-9_-], остальное → '_'. Длина ≤ 80.
    """
    if not raw:
        return ""
    cleaned = re.sub(r"[^a-zA-Z0-9_\-]", "_", str(raw))
    return cleaned[:80]


def build_litres_url(
    book_path: str,
    *,
    subid: Optional[str] = None,
    base_url: Optional[str] = None,
    hash_: Optional[str] = None,
    erid: Optional[str] = None,
    campaign: Optional[str] = None,
    method: Optional[str] = None,
) -> str:
    """Собрать партнёрский URL на книгу.

    Args:
        book_path: "/book/paulo-koelo/alhimik-122351/" или полный URL.
        subid: опциональный маркер источника (канал/пост).
        base_url: домен Литреса (по умолчанию из ENV).
        hash_: ADVCAKE_HASH (по умолчанию из ENV).
        erid: ADVCAKE_ERID (по умолчанию из ENV).
        campaign: ADVCAKE_CAMPAIGN (по умолчанию из ENV).
        method: ADVCAKE_METHOD (по умолчанию из ENV).

    Returns:
        Полный партнёрский URL со всеми UTM-метками.
    """
    path = _normalize_book_path(book_path)
    if not path:
        raise ValueError("book_path is required")

    base = (base_url or ADVCAKE_BASE_URL).rstrip("/")
    h = hash_ or ADVCAKE_HASH
    e = erid or ADVCAKE_ERID
    c = campaign or ADVCAKE_CAMPAIGN
    m = method or ADVCAKE_METHOD

    params = [
        ("utm_source", "advcake"),
        ("utm_medium", "cpa"),
        ("utm_campaign", c),
        ("utm_content", h),
        ("advcake_params", ""),         # заполнится при клике
        ("utm_term", ""),                # без ключевого слова
        ("erid", e),
        ("advcake_method", m),
        ("m", "1"),                       # мобильный трафик
    ]
    if subid:
        params.append(("subid", _safe_subid(subid)))

    query = urlencode(params, quote_via=quote)
    return f"{base}{path}/?{query}"


def build_litres_url_with_label(
    book_path: str,
    *,
    channel: str = "site",
    post_id: Optional[Union[int, str]] = None,
    slug: Optional[str] = None,
    date: Optional[str] = None,
    **kwargs,
) -> str:
    """Удобный wrapper для постов в соцсетях.

    Собирает subid вида: <channel>_<post_id>_<date>_<slug>

    Пример:
        build_litres_url_with_label(
            book_path, channel="vk", post_id=42,
            slug="alhimik-koeluo", date="2026-06-25",
        )
        → "...&subid=vk_42_2026-06-25_alhimik-koeluo"
    """
    parts = [channel]
    if post_id is not None:
        parts.append(str(post_id))
    if date:
        parts.append(date)
    elif slug:
        parts.append(datetime.now(timezone.utc).strftime("%Y-%m-%d"))
    if slug:
        parts.append(slug)
    subid = "_".join(parts)
    return build_litres_url(book_path, subid=subid, **kwargs)


def make_book_affiliate(
    slug: str,
    book_path: str,
    *,
    subid: Optional[str] = None,
    **kwargs,
) -> BookAffiliate:
    """BookAffiliate dataclass с заполненными полями + ISO timestamp."""
    path = _normalize_book_path(book_path)
    litres_url = f"{ADVCAKE_BASE_URL}{path}/"
    advcake_url = build_litres_url(book_path, subid=subid, **kwargs)
    return BookAffiliate(
        slug=slug,
        book_path=path,
        litres_url=litres_url,
        advcake_url=advcake_url,
        hash=ADVCAKE_HASH,
        erid=ADVCAKE_ERID,
        subid=subid,
        generated_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
    )


# ─── Кеш (JSON на диске) ──────────────────────────────────────────────────

def _ensure_cache_dir() -> None:
    _CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)


def load_cache() -> dict[str, dict]:
    """Загрузить кеш affiliate-ссылок: {slug → dict}."""
    if not _CACHE_PATH.exists():
        return {}
    import json
    try:
        return json.loads(_CACHE_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}


def save_cache(cache: dict[str, dict]) -> None:
    _ensure_cache_dir()
    import json
    _CACHE_PATH.write_text(
        json.dumps(cache, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def cache_book(aff: BookAffiliate) -> None:
    """Положить/обновить запись в кеше."""
    cache = load_cache()
    cache[aff.slug] = aff.to_dict()
    save_cache(cache)


def get_cached(slug: str) -> Optional[BookAffiliate]:
    cache = load_cache()
    if slug in cache:
        return BookAffiliate.from_dict(cache[slug])
    return None


# ─── CLI ──────────────────────────────────────────────────────────────────

def _cli() -> None:
    import argparse
    import json as _json
    import sys

    parser = argparse.ArgumentParser(
        description="Генератор партнёрских ссылок AdvCake → Литрес"
    )
    parser.add_argument(
        "book_path", nargs="?", default=None,
        help="Путь книги (/book/foo/bar-123/). "
             "На Windows/Git-Bash используйте BOOK_PATH=... или --book-path=.",
    )
    parser.add_argument("--book-path", dest="book_path_flag", default=None,
                        help="явный путь книги (если positional ломается на MSYS)")
    parser.add_argument(
        "--from-env", action="store_true",
        help="читать путь из $BOOK_PATH (надёжнее всего на Windows/Git-Bash)",
    )
    parser.add_argument("--subid", default=None, help="маркер источника")
    parser.add_argument("--channel", default="cli",
                        help="канал для subid (cli/vk/tg/ok/zen)")
    parser.add_argument("--post-id", default=None)
    parser.add_argument("--slug", default=None)
    parser.add_argument("--save-cache", action="store_true",
                        help="сохранить результат в локальный кеш")
    parser.add_argument("--json", action="store_true",
                        help="вывести JSON вместо URL")
    args = parser.parse_args()

    # Приоритет: --from-env → --book-path → positional
    if args.from_env:
        book_path = os.environ.get("BOOK_PATH", "")
    else:
        book_path = args.book_path_flag or args.book_path
    if not book_path:
        parser.error(
            "укажи book_path / --book-path / --from-env + BOOK_PATH=..."
        )

    use_label = args.channel != "cli" or args.post_id or args.slug
    url = (
        build_litres_url_with_label(
            book_path,
            channel=args.channel,
            post_id=args.post_id,
            slug=args.slug,
        )
        if use_label
        else build_litres_url(book_path, subid=args.subid)
    )

    if args.json:
        aff = make_book_affiliate(args.slug or "_ad_hoc", book_path,
                                  subid=args.subid)
        sys.stdout.write(_json.dumps(aff.to_dict(), ensure_ascii=False, indent=2))
        sys.stdout.write("\n")
    else:
        sys.stdout.write(url + "\n")

    if args.save_cache and args.slug:
        aff = make_book_affiliate(args.slug, book_path, subid=args.subid)
        cache_book(aff)
        print(f"[cached] {args.slug} → {_CACHE_PATH}",
              file=sys.stderr, flush=True)


if __name__ == "__main__":
    _cli()