r"""
Получение цен на книги с Литрес и Book24.

Источник цен — DOM после JS-рендера (Playwright).
Litres:  data-testid="art__finalPrice" с aria-label="N RUB"
Book24:  .product-card-price__current .app-price (текущая цена, до скидки не берём)

Использование:
    python scripts/fetch_book_prices.py                   # все книги
    python scripts/fetch_book_prices.py --slug slug-name  # конкретная книга
    python scripts/fetch_book_prices.py --dry-run         # не сохранять в books.json

Что делает:
    1. Читает src/data/books.json
    2. Для каждой книги открывает litres.ru/search и book24.ru/search в headless Chromium
    3. Берёт минимальную цену из первых N карточек результатов (берём все и ищем минимум)
    4. Пишет обратно в books.json в поле prices: { litres, book24, updated_at }

Подводные камни:
    - один общий браузер на все запросы (не пересоздаём)
    - если цена не нашлась — пишем null, не падаем
    - sleep ~1 сек между запросами к разным сайтам
    - на litres выдача идёт через JS, БЕЗ Playwright ничего не парсится
"""
import argparse
import json
import re
import sys
import time
import urllib.parse
from datetime import datetime, timezone
from pathlib import Path

# Windows: UTF-8 в stdout
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8")
    except AttributeError:
        pass

ROOT = Path(__file__).resolve().parent.parent
BOOKS_JSON = ROOT / "src" / "data" / "books.json"

UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
)

# Litres: aria-label="<int> RUB"
LITRES_PRICE_RE = re.compile(r"(\d+)\s*RUB")
# Book24: .product-card-price__current содержит число+₽
PRICE_TEXT_RE = re.compile(r"(\d[\d\s ]*)\s*₽")

_PW_BROWSER = None
_PW_PW = None


def _browser():
    """Ленивая инициализация headless Chromium. Один на сессию."""
    global _PW_BROWSER, _PW_PW
    if _PW_BROWSER is None:
        from playwright.sync_api import sync_playwright
        _PW_PW = sync_playwright().start()
        _PW_BROWSER = _PW_PW.chromium.launch(headless=True, args=["--no-sandbox"])
    return _PW_BROWSER


def _new_page():
    browser = _browser()
    ctx = browser.new_context(user_agent=UA, locale="ru-RU")
    return ctx, ctx.new_page()


def _extract_litres_prices(page) -> list[int]:
    """Достаём aria-label="N RUB" у всех финальных цен."""
    labels = page.eval_on_selector_all(
        '[data-testid="art__finalPrice"]',
        "els => els.map(e => e.getAttribute('aria-label'))",
    )
    nums = []
    for label in labels or []:
        if not label:
            continue
        m = LITRES_PRICE_RE.match(label.strip())
        if m:
            n = int(m.group(1))
            if 20 <= n <= 50000:
                nums.append(n)
    return nums


def _extract_book24_prices(page) -> list[int]:
    """Достаём текст всех .product-card-price__current .app-price."""
    texts = page.eval_on_selector_all(
        '.product-card-price__current .app-price',
        "els => els.map(e => e.textContent)",
    )
    nums = []
    for t in texts or []:
        if not t:
            continue
        m = PRICE_TEXT_RE.search(t.replace(" ", " "))
        if m:
            n = int(re.sub(r"[\s ]", "", m.group(1)))
            if 20 <= n <= 50000:
                nums.append(n)
    return nums


def fetch_litres(query: str) -> int | None:
    url = "https://www.litres.ru/search/?q=" + urllib.parse.quote(query)
    ctx = page = None
    try:
        browser = _browser()
        ctx = browser.new_context(user_agent=UA, locale="ru-RU")
        page = ctx.new_page()
        page.goto(url, wait_until="domcontentloaded", timeout=30000)
        try:
            page.wait_for_selector('[data-testid="art__finalPrice"]', timeout=10000)
        except Exception:
            pass
        page.wait_for_timeout(800)
        nums = _extract_litres_prices(page)
        return min(nums) if nums else None
    except Exception as e:
        print(f"  [litres] error: {e}", file=sys.stderr)
        return None
    finally:
        if page:
            page.close()
        if ctx:
            ctx.close()


def fetch_book24(query: str) -> int | None:
    url = "https://book24.ru/search?q=" + urllib.parse.quote(query)
    ctx = page = None
    try:
        browser = _browser()
        ctx = browser.new_context(user_agent=UA, locale="ru-RU")
        page = ctx.new_page()
        page.goto(url, wait_until="domcontentloaded", timeout=30000)
        try:
            page.wait_for_selector('.product-card-price__current .app-price', timeout=10000)
        except Exception:
            pass
        page.wait_for_timeout(800)
        nums = _extract_book24_prices(page)
        return min(nums) if nums else None
    except Exception as e:
        print(f"  [book24] error: {e}", file=sys.stderr)
        return None
    finally:
        if page:
            page.close()
        if ctx:
            ctx.close()


def main() -> int:
    parser = argparse.ArgumentParser(description="Получение цен на книги")
    parser.add_argument("--slug", help="Только эта книга")
    parser.add_argument("--dry-run", action="store_true", help="Не сохранять books.json")
    args = parser.parse_args()

    data = json.loads(BOOKS_JSON.read_text(encoding="utf-8"))
    books = data["books"]
    targets = [b for b in books if not args.slug or b["slug"] == args.slug]
    if not targets:
        print(f"No book matches slug={args.slug!r}", file=sys.stderr)
        return 1

    now = datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")

    print(f"Fetching prices for {len(targets)} book(s)...\n")
    for i, book in enumerate(targets, 1):
        first_author = book["author"].split(",")[0].strip()
        q = f"{book['title']} {first_author}"

        print(f"[{i}/{len(targets)}] {book['slug']}")
        print(f"  query: {q}")

        litres_price = fetch_litres(q)
        time.sleep(1.0)
        book24_price = fetch_book24(q)
        time.sleep(1.0)

        book["prices"] = {
            "litres": litres_price,
            "book24": book24_price,
            "updated_at": now,
        }
        print(f"  litres={litres_price} book24={book24_price}\n")

    if args.dry_run:
        print("DRY RUN — books.json not modified.")
        return 0

    BOOKS_JSON.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"Saved: {BOOKS_JSON}")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    finally:
        if _PW_BROWSER is not None:
            try:
                _PW_BROWSER.close()
            except Exception:
                pass
        if _PW_PW is not None:
            try:
                _PW_PW.stop()
            except Exception:
                pass
