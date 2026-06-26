#!/usr/bin/env python3
"""
spy_livelib_books.py — топ книг LiveLib по теме/нише.

Парсит страницу поиска livelib.ru/find?q=<запрос> и отдаёт:
- title, author, rating, ratings_count, year, url

БЕСПЛАТНО, без API-токенов, только stdlib (urllib + re).

Использование:
    python spy_livelib_books.py --query "психология" --limit 20
    python spy_livelib_books.py --query "саморазвитие" --limit 30 --output books.csv
    python spy_livelib_books.py --query "когнитивные искажения" --min-rating 4.0

⚠️  Сайт защищён DDoS-Guard. Используем реальный User-Agent + Referer.
⚠️  Если 0 результатов — обнови селекторы в find_book_cards().

Связь с expert-reviews-hub:
  Этот скрипт — ТОП книг ниши. Для ОТЗЫВОВ на конкретную книгу
  используй expert-reviews-hub/scripts/parse_livelib.py.
"""

import argparse
import csv
import json
import re
import sys
import time
import urllib.request
import urllib.error
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote


LIVELIB_URL = "https://www.livelib.ru"


def _check_deps():
    """Зависимости: только stdlib."""
    # Проверяем что urllib работает (всегда должно быть)
    pass


def fetch(url, retries=3, delay=1.5, referer=None):
    """GET с User-Agent + Referer + ретраи. Обязательно для обхода DDoS-Guard."""
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "ru-RU,ru;q=0.9,en;q=0.8",
        "Accept-Encoding": "gzip, deflate",
    }
    if referer:
        headers["Referer"] = referer

    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=30) as resp:
                raw = resp.read()
                # LiveLib отдаёт utf-8
                return raw.decode("utf-8", errors="replace")
        except urllib.error.HTTPError as e:
            if e.code in (403, 429, 503):
                wait = delay * (attempt + 1) * 2
                print(f"   ⚠️ HTTP {e.code}, повтор через {wait:.0f} сек...", file=sys.stderr)
                time.sleep(wait)
            elif e.code == 404:
                print(f"   ❌ 404 Not Found: {url}", file=sys.stderr)
                return None
            else:
                raise
        except Exception as e:
            if attempt < retries - 1:
                wait = delay * (attempt + 1)
                print(f"   ⚠️ Ошибка: {e}, повтор через {wait:.0f} сек...", file=sys.stderr)
                time.sleep(wait)
            else:
                raise
    raise RuntimeError(f"Failed after {retries} retries: {url}")


def find_book_cards(html):
    """
    Извлекает карточки книг из выдачи /find?q=... .

    Актуальная вёрстка (13.06.2026):
        <div class="object-cover">
            <a class="object-cover__link" href="/book/1000...">
                <img ... data-lazy-src="...jpg" />
            </a>
        </div>
        <a class="brow-title" href="/book/1000...">Название книги</a>
        <a class="ll2015b4 ... author" href="/author/...">Автор</a>
        <span class="object-rating">4.42</span>
        <span class="rating-text">(<число>)</span>
    """
    if not html:
        return []

    # Сначала находим все ссылки на книги и пытаемся привязать метаданные
    # Используем простую стратегию: парсим весь HTML в окнах по book_url
    results = []
    seen = set()

    # 1) Сначала вытащим заголовки и URL — самые надёжные
    # Шаблон (13.06.2026), атрибуты в любом порядке:
    #   <div class="brow-title">
    #     <a href="/book/ID-slug" class="title">Title</a>
    #     или  <a class="title" href="/book/ID-slug">Title</a>
    #   </div>
    # Используем два регекспа и объединяем.
    brow_pattern_a = re.compile(
        r'<div[^>]+class="[^"]*brow-title[^"]*"[^>]*>\s*'
        r'<a[^>]+class="[^"]*title[^"]*"[^>]+href="(/book/(\d+)[^"]*)"[^>]*>([^<]+)</a>',
        re.IGNORECASE | re.DOTALL,
    )
    brow_pattern_b = re.compile(
        r'<div[^>]+class="[^"]*brow-title[^"]*"[^>]*>\s*'
        r'<a[^>]+href="(/book/(\d+)[^"]*)"[^>]+class="[^"]*title[^"]*"[^>]*>([^<]+)</a>',
        re.IGNORECASE | re.DOTALL,
    )
    for m in list(brow_pattern_a.finditer(html)) + list(brow_pattern_b.finditer(html)):
        url_path, book_id, title = m.group(1), m.group(2), m.group(3)
        title = re.sub(r"\s+", " ", title).strip()
        if not title or len(title) < 2:
            continue
        key = (book_id, title.lower())
        if key in seen:
            continue
        seen.add(key)
        results.append({
            "title": title,
            "book_id": book_id,
            "url": LIVELIB_URL + url_path,
        })

    # 2) Ищем рейтинги: идём последовательно по документу
    # Шаблон: data-rating="4.42" или class="object-rating">4.42<
    rating_pattern = re.compile(
        r'(?:data-rating="([\d.]+)"|<span[^>]*class="[^"]*object-rating[^"]*"[^>]*>([\d.,]+))',
        re.IGNORECASE,
    )
    ratings = []
    for m in rating_pattern.finditer(html):
        val = m.group(1) or m.group(2)
        if val:
            try:
                ratings.append(float(val.replace(",", ".")))
            except ValueError:
                pass

    # Привязываем рейтинги к книгам по порядку (грубое соответствие)
    for i, book in enumerate(results):
        if i < len(ratings):
            book["rating"] = ratings[i]

    # 3) Количество оценок: "(1 234)" или "(<число>)"
    count_pattern = re.compile(r">\((\d[\d\s\xa0]*)\)<", re.IGNORECASE)
    counts = []
    for m in count_pattern.finditer(html):
        try:
            counts.append(int(re.sub(r"[\s\xa0]", "", m.group(1))))
        except ValueError:
            pass
    for i, book in enumerate(results):
        if i < len(counts):
            book["ratings_count"] = counts[i]

    # 4) Авторы: <a href="/author/..." class="...">Автор</a>
    # Ищем в окрестности каждой книги (грубо, по порядку)
    author_pattern = re.compile(
        r'<a[^>]+href="/author/(\d+)[^"]*"[^>]*>([^<]+)</a>',
        re.IGNORECASE,
    )
    authors = []
    for m in author_pattern.finditer(html):
        authors.append({
            "author_id": m.group(1),
            "author_name": re.sub(r"\s+", " ", m.group(2)).strip(),
        })
    for i, book in enumerate(results):
        if i < len(authors):
            book["author"] = authors[i]["author_name"]
            book["author_id"] = authors[i]["author_id"]
            book["author_url"] = f"{LIVELIB_URL}/author/{authors[i]['author_id']}"

    return results


def _wait_for_ddos_guard(page, html_sink, max_wait=20):
    """
    Ждёт, пока DDoS-Guard challenge пройдёт.
    Признак challenge: в HTML есть 'DDoS-Guard' или 'jschl' и нет /book/ ссылок.
    Ждёт появления первых /book/ ссылок ИЛИ роста HTML выше 100КБ.
    """
    import re
    deadline = time.time() + max_wait
    attempts = 0
    while time.time() < deadline:
        attempts += 1
        html = page.content()
        html_sink["html"] = html
        html_sink["size"] = len(html)
        # Признаки DDoS-Guard
        is_challenge = (
            "DDoS-Guard" in html or
            "jschl" in html.lower() or
            "Checking your browser" in html
        )
        has_books = bool(re.search(r'href="/book/\d+', html))
        if has_books and not is_challenge:
            return True
        if not is_challenge and len(html) > 100_000:
            # Не challenge, и не нашли книги — может конец выдачи
            return "no_books"
        time.sleep(1.0)
    return False


def search_books(query, limit=20, min_rating=None, debug=False):
    """Ищет книги по запросу через livelib.ru/find?q=... с пагинацией.
    Использует Playwright (headless), чтобы обойти DDoS-Guard challenge.
    Главная → cookies → submit формы поиска → AJAX-выдача с карточками.
    """
    from playwright.sync_api import sync_playwright

    all_books = []
    page_num = 1
    max_pages = 5

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=not debug)
        context = browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1280, "height": 800},
            locale="ru-RU",
        )
        page_obj = context.new_page()

        # Шаг 1: Главная → DDoS-Guard cookies (с ретраем)
        print("   🛡️ Прогрев DDoS-Guard через главную...", file=sys.stderr)
        for attempt in range(3):
            try:
                page_obj.goto(LIVELIB_URL, wait_until="domcontentloaded", timeout=30000)
                # Даём время DDoS-Guard challenge пройти
                for _ in range(20):
                    time.sleep(1)
                    h = page_obj.content()
                    is_chal = ("DDoS-Guard" in h or "jschl" in h.lower() or "Checking your browser" in h)
                    if not is_chal and len(h) > 200_000:
                        break
                h = page_obj.content()
                if len(h) > 200_000 and "livelib.ru" in page_obj.url:
                    break
                print(f"   ⚠️ Главная загрузилась, но подозрительно: {len(h)} Б (попытка {attempt+1})", file=sys.stderr)
                time.sleep(5)
            except Exception as e:
                print(f"   ⚠️ Попытка {attempt+1}: {e}", file=sys.stderr)
                time.sleep(5)
        else:
            print(f"   ❌ Не удалось прогреть DDoS-Guard за 3 попытки", file=sys.stderr)
            browser.close()
            return []

        while len(all_books) < limit and page_num <= max_pages:
            print(f"   📄 Страница {page_num}...", file=sys.stderr)
            try:
                if page_num == 1:
                    # Шаг 2: Submit формы поиска (GET /find?q=... редиректит на главную)
                    sel = 'input[name="filter[search]"]'
                    loc = page_obj.locator(sel).first
                    loc.fill(query)
                    time.sleep(0.5)
                    page_obj.keyboard.press("Enter")
                else:
                    # Пагинация через URL с offset (LiveLib использует &offset=N)
                    # Безопасный путь: тот же submit формы
                    sel = 'input[name="filter[search]"]'
                    loc = page_obj.locator(sel).first
                    loc.fill("")
                    loc.fill(query)
                    time.sleep(0.3)
                    page_obj.keyboard.press("Enter")

                # Ждём загрузки AJAX-выдачи
                time.sleep(6)
            except Exception as e:
                print(f"   ⚠️ Ошибка загрузки страницы {page_num}: {e}", file=sys.stderr)
                break

            html = page_obj.content()
            cards = find_book_cards(html)
            if not cards:
                print(f"   ⚠️ На странице {page_num} не найдено карточек. Конец выдачи.", file=sys.stderr)
                if debug:
                    Path(r"C:/Users/kfigh/AppData/Local/Temp/ll_debug.html").write_text(
                        html, encoding="utf-8"
                    )
                break

            # Фильтр по рейтингу
            if min_rating is not None:
                cards = [c for c in cards if c.get("rating") and c["rating"] >= min_rating]

            # Дедуп по book_id
            existing_ids = {b["book_id"] for b in all_books}
            new_cards = [c for c in cards if c["book_id"] not in existing_ids]

            all_books.extend(new_cards)
            print(f"   ✅ +{len(new_cards)} новых книг (всего {len(all_books)})", file=sys.stderr)

            if len(new_cards) < 3:
                break

            page_num += 1
            time.sleep(1.5)  # вежливая пауза

        browser.close()

    return all_books[:limit]


def print_report(books, query, min_rating=None):
    print(f"\n{'='*70}")
    print(f"📚 LIVE LIB: «{query}»")
    if min_rating:
        print(f"   Фильтр: рейтинг ≥ {min_rating}")
    print(f"{'='*70}\n")
    print(f"Найдено книг: {len(books)}\n")

    if not books:
        print("⚠️ Ничего не найдено. Возможные причины:")
        print("   — LiveLib изменил вёрстку (обнови селекторы в find_book_cards)")
        print("   — Слишком специфичный запрос")
        print("   — Включи VPN\n")
        return

    print(f"{'#':<3} {'Рейтинг':<8} {'Оценок':<8} {'Книга':<40} {'Автор'}")
    print("-" * 100)
    for i, b in enumerate(books, 1):
        rating = f"{b.get('rating', 0):.2f}" if b.get("rating") else "—"
        cnt = f"{b.get('ratings_count', 0):,}".replace(",", " ") if b.get("ratings_count") else "—"
        title = (b["title"][:38] + "…") if len(b["title"]) > 39 else b["title"]
        author = b.get("author", "—")[:25]
        print(f"{i:<3} {rating:<8} {cnt:<8} {title:<40} {author}")
    print()

    # Топ-3 для быстрого использования
    print(f"\n💎 ТОП-3 по рейтингу:")
    top3 = sorted(
        [b for b in books if b.get("rating")],
        key=lambda x: (x.get("rating", 0), x.get("ratings_count", 0)),
        reverse=True,
    )[:3]
    for b in top3:
        print(f"   • {b['title']} — {b.get('author', '?')} (⭐ {b.get('rating')}, {b.get('ratings_count', 0):,})")


def save_json(books, path, query, min_rating=None):
    payload = {
        "source": "livelib.ru",
        "query": query,
        "min_rating": min_rating,
        "collected_at": datetime.now(timezone.utc).isoformat(),
        "count": len(books),
        "books": books,
    }
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n💾 JSON: {path}")


def save_csv(books, path):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=["title", "author", "rating", "ratings_count", "book_id", "url", "author_url"],
        )
        writer.writeheader()
        for b in books:
            writer.writerow({k: b.get(k, "") for k in writer.fieldnames})
    print(f"💾 CSV:  {path}")


def main():
    parser = argparse.ArgumentParser(
        description="Парсер топа книг LiveLib по теме/нише (бесплатно, без API)"
    )
    parser.add_argument("--query", required=True, help="Поисковый запрос (тема/ниша)")
    parser.add_argument("--limit", type=int, default=20, help="Сколько книг собрать (по умолчанию 20)")
    parser.add_argument("--min-rating", type=float, default=None,
                        help="Минимальный рейтинг (например 4.0)")
    parser.add_argument("--output", help="Путь к CSV")
    parser.add_argument("--json", help="Путь к JSON (если не задан — печатает в stdout)")
    parser.add_argument("--debug", action="store_true",
                        help="Показать браузер и сохранить HTML в AppData для диагностики")
    args = parser.parse_args()

    print(f"🔍 LiveLib: «{args.query}» (limit={args.limit})", file=sys.stderr)
    books = search_books(args.query, args.limit, args.min_rating, debug=args.debug)
    print_report(books, args.query, args.min_rating)

    if args.output:
        save_csv(books, args.output)
    if args.json:
        save_json(books, args.json, args.query, args.min_rating)
    elif not args.output:
        # по умолчанию — сохранить в текущую папку
        default_json = f"livelib_books_{args.query.replace(' ', '_')}.json"
        save_json(books, default_json, args.query, args.min_rating)


if __name__ == "__main__":
    main()
