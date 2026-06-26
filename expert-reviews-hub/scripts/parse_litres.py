"""
Литрес parser — отзывы от покупателей
Использование:
  python parse_litres.py "Трансерфинг реальности" "Вадим Зеланд"
  python parse_litres.py --url "https://www.litres.ru/vadim-zeland/transerfing-realnosti/otzyvy/"
Выход: reviews/{book-slug}/litres.json
"""
import sys
import os
import json
import re
import time
import argparse
from pathlib import Path
from datetime import datetime
from urllib.parse import quote, urljoin
import urllib.request
import urllib.error


# === UTF-8 fix for Windows ===
try:
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')
except Exception:
    pass


# === HTTP ===
def fetch(url, retries=3, delay=3.0):
    """Получить HTML с User-Agent (Литрес агрессивный к ботам!)."""
    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) '
                      'AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'ru-RU,ru;q=0.9,en;q=0.8',
        'Accept-Encoding': 'gzip, deflate, br',
        'DNT': '1',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1',
    }
    req = urllib.request.Request(url, headers=headers)
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                raw = resp.read()
                # Попробовать определить кодировку
                ct = resp.headers.get('content-type', '')
                m = re.search(r'charset=([\w-]+)', ct)
                if m:
                    return raw.decode(m.group(1), errors='replace')
                return raw.decode('utf-8', errors='replace')
        except urllib.error.HTTPError as e:
            if e.code in (429, 503):
                time.sleep(delay * (attempt + 1) * 2)
            elif e.code == 403:
                time.sleep(delay * (attempt + 1))
            else:
                raise
        except Exception:
            if attempt == retries - 1:
                raise
            time.sleep(delay)
    raise RuntimeError(f"Failed to fetch {url}")


# === Поиск книги ===
def find_book_url(title, author=None):
    """Найти книгу на litres.ru."""
    q = f"{title} {author or ''}".strip()
    search_url = f"https://www.litres.ru/search/?q={quote(q)}"
    try:
        html = fetch(search_url)
    except Exception as e:
        print(f"  ! Search failed: {e}", file=sys.stderr)
        return None

    # Паттерн: /author-slug/book-slug/ — обычно первая ссылка
    m = re.search(r'href="(/[a-z0-9-]+/[a-z0-9-]+)/?"', html)
    if m:
        path = m.group(1)
        # Фильтруем не-книги
        if '/search' in path or '/account' in path or '/cart' in path:
            pass
        else:
            return urljoin('https://www.litres.ru', path)
    return None


# === Парсинг отзывов ===
def parse_reviews_html(html):
    """Извлекает отзывы из HTML Литрес.

    Литрес показывает только verified-покупки:
        <div class="review-item" data-purchased="true">
            <div class="review-item__author">Анна</div>
            <div class="review-item__rating" data-rating="5">5</div>
            <div class="review-item__date" datetime="2024-12-15">15 декабря 2024</div>
            <div class="review-item__text">...</div>
            <div class="review-item__likes">45</div>
        </div>
    """
    reviews = []
    # Упрощённый regex-парсинг
    pattern = re.compile(
        r'<div[^>]+class="[^"]*review-item[^"]*"[^>]*>(.*?)</div>\s*</div>\s*</div>',
        re.DOTALL
    )

    for m in pattern.finditer(html):
        block = m.group(1)

        rev = {
            'author': None,
            'rating': None,
            'date': None,
            'text': None,
            'purchased': True,  # Литрес — всегда покупка
            'verified': True,
            'likes': 0,
        }

        # Author
        am = re.search(r'class="[^"]*review-item__author[^"]*"[^>]*>([^<]+)</div>', block)
        if am:
            rev['author'] = am.group(1).strip()

        # Rating
        rm = re.search(r'data-rating="(\d)"', block)
        if rm:
            rev['rating'] = int(rm.group(1))

        # Date
        dm = re.search(r'datetime="([^"]+)"', block)
        if dm:
            rev['date'] = dm.group(1)

        # Text
        tm = re.search(r'class="[^"]*review-item__text[^"]*"[^>]*>(.*?)</div>', block, re.DOTALL)
        if tm:
            text = re.sub(r'<[^>]+>', ' ', tm.group(1))
            text = re.sub(r'\s+', ' ', text).strip()
            rev['text'] = text

        # Likes
        lm = re.search(r'class="[^"]*review-item__likes[^"]*"[^>]*>(\d+)', block)
        if lm:
            rev['likes'] = int(lm.group(1))

        if rev['text'] and len(rev['text']) > 20:
            reviews.append(rev)

    return reviews


# === Извлечение общей информации о книге ===
def extract_book_meta(html, book_url):
    meta = {'book_url': book_url}

    # Title
    m = re.search(r'<h1[^>]+itemprop="name"[^>]*>([^<]+)</h1>', html)
    if not m:
        m = re.search(r'<title>([^<]+)</title>', html)
    if m:
        title = re.sub(r'\s+', ' ', m.group(1)).strip()
        title = re.sub(r'\s*[—\-]\s*Литрес.*$', '', title)
        title = re.sub(r'\s*—\s*отзывы\s*$', '', title, flags=re.IGNORECASE)
        meta['title'] = title

    # Author
    m = re.search(r'<a[^>]+itemprop="author"[^>]*>([^<]+)</a>', html)
    if not m:
        m = re.search(r'<meta[^>]+name="author"[^>]+content="([^"]+)"', html)
    if m:
        meta['author'] = re.sub(r'\s+', ' ', m.group(1)).strip()

    # Rating
    m = re.search(r'<span[^>]+itemprop="ratingValue"[^>]*>([\d.,]+)</span>', html)
    if m:
        meta['rating_avg'] = float(m.group(1).replace(',', '.'))

    # Count
    m = re.search(r'<span[^>]+itemprop="reviewCount"[^>]*>(\d+)</span>', html)
    if m:
        meta['rating_count'] = int(m.group(1))

    return meta


# === Slugify ===
def slugify(text):
    table = {
        'а': 'a', 'б': 'b', 'в': 'v', 'г': 'g', 'д': 'd', 'е': 'e', 'ё': 'yo',
        'ж': 'zh', 'з': 'z', 'и': 'i', 'й': 'i', 'к': 'k', 'л': 'l', 'м': 'm',
        'н': 'n', 'о': 'o', 'п': 'p', 'р': 'r', 'с': 's', 'т': 't', 'у': 'u',
        'ф': 'f', 'х': 'h', 'ц': 'ts', 'ч': 'ch', 'ш': 'sh', 'щ': 'sch',
        'ъ': '', 'ы': 'y', 'ь': '', 'э': 'e', 'ю': 'yu', 'я': 'ya',
    }
    result = []
    for ch in text.lower():
        result.append(table.get(ch, ch))
    slug = ''.join(result)
    slug = re.sub(r'[^a-z0-9]+', '-', slug).strip('-')
    return slug[:80]


# === MAIN ===
def main():
    p = argparse.ArgumentParser(description='Литрес reviews parser')
    p.add_argument('title', nargs='?', help='Название книги')
    p.add_argument('author', nargs='?', help='Автор (опционально)')
    p.add_argument('--url', help='Прямой URL книги')
    p.add_argument('--max-pages', type=int, default=5)
    p.add_argument('--out', default='reviews')
    args = p.parse_args()

    if args.url:
        book_url = args.url.rstrip('/')
    elif args.title:
        print(f"Ищу: {args.title} {args.author or ''}", file=sys.stderr)
        book_url = find_book_url(args.title, args.author)
        if not book_url:
            print("Книга не найдена", file=sys.stderr)
            sys.exit(1)
    else:
        p.print_help()
        sys.exit(1)

    print(f"URL: {book_url}", file=sys.stderr)

    # Основная страница
    main_html = fetch(book_url)
    book_meta = extract_book_meta(main_html, book_url)
    print(f"Книга: {book_meta.get('title', '?')} — {book_meta.get('author', '?')}", file=sys.stderr)
    print(f"Рейтинг: {book_meta.get('rating_avg', '?')} ({book_meta.get('rating_count', '?')} отзывов)", file=sys.stderr)

    time.sleep(3.0)

    # Отзывы с пагинацией
    all_reviews = []
    reviews_base = f"{book_url}/otzyvy/"
    for page in range(1, args.max_pages + 1):
        page_url = reviews_base if page == 1 else f"{reviews_base}?page={page}"
        try:
            html = fetch(page_url)
        except Exception as e:
            print(f"  ! Page {page} failed: {e}", file=sys.stderr)
            break

        reviews = parse_reviews_html(html)
        if not reviews:
            break
        all_reviews.extend(reviews)
        print(f"  Page {page}: +{len(reviews)} отзывов", file=sys.stderr)
        time.sleep(3.0)

    print(f"Собрано: {len(all_reviews)} отзывов (все verified)", file=sys.stderr)

    # Сохранить
    book_slug = slugify(book_meta.get('title', args.title or 'unknown'))
    bundle = {
        'source': 'litres',
        'source_url': book_url,
        'fetched_at': datetime.now().isoformat(timespec='seconds'),
        'book': book_meta,
        'rating': {
            'average': book_meta.get('rating_avg'),
            'count': book_meta.get('rating_count', len(all_reviews)),
        },
        'reviews': all_reviews,
        'weight': 1.5,  # verified покупатели
        'notes': f"Все отзывы от покупателей. Спарсено {len(all_reviews)} с {args.max_pages} страниц."
    }

    out_dir = Path(args.out) / book_slug
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / 'litres.json'
    out_path.write_text(json.dumps(bundle, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f"Сохранено: {out_path}", file=sys.stderr)


if __name__ == '__main__':
    main()
