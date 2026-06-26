"""
LiveLib parser — отзывы с livelib.ru
Использование:
  python parse_livelib.py "Трансерфинг реальности" "Вадим Зеланд"
  python parse_livelib.py --url "https://www.livelib.ru/book/1000283027"
Выход: reviews/{book-slug}/livelib.json
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
from html.parser import HTMLParser


# === UTF-8 fix for Windows ===
try:
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')
except Exception:
    pass


# === HTML парсер для отзывов LiveLib ===
class LiveLibReviewParser(HTMLParser):
    """Извлекает отзывы из HTML LiveLib.

    LiveLib использует упрощённую HTML-структуру без микроразметки:
        <article class="book-card-comment">
            <div class="comment-user">
                <a class="comment-user__name">...</a>
            </div>
            <div class="comment-rating">5</div>
            <div class="comment-date">15 декабря 2024</div>
            <div class="comment-text">...</div>
        </article>
    """
    def __init__(self):
        super().__init__()
        self.reviews = []
        self.current = None
        self.tag_stack = []
        self.in_text = False
        self.text_buf = []

    def handle_starttag(self, tag, attrs):
        attrs_d = dict(attrs)
        self.tag_stack.append((tag, attrs_d))

        # Начало нового отзыва
        if tag == 'article' and 'book-card-comment' in attrs_d.get('class', ''):
            self.current = {
                'author': None,
                'rating': None,
                'date': None,
                'text': None,
                'likes': 0,
                'url': None,
            }

        elif self.current is not None:
            if tag == 'div' and 'comment-rating' in attrs_d.get('class', ''):
                # Рейтинг в data-атрибуте
                self.current['rating'] = attrs_d.get('data-rating')

            elif tag == 'div' and 'comment-date' in attrs_d.get('class', ''):
                # Дата в datetime-атрибуте или в тексте
                if 'datetime' in attrs_d:
                    self.current['date'] = attrs_d['datetime']

            elif tag == 'a' and 'comment-user__name' in attrs_d.get('class', ''):
                self.in_text = True
                self.text_buf = []
                self._capturing = 'author'

            elif tag == 'div' and 'comment-text' in attrs_d.get('class', ''):
                self.in_text = True
                self.text_buf = []
                self._capturing = 'text'

    def handle_endtag(self, tag):
        if self.current is not None and self.in_text and tag == self._last_tag():
            text = ''.join(self.text_buf).strip()
            if self._capturing == 'author' and not self.current['author']:
                self.current['author'] = text
            elif self._capturing == 'text':
                self.current['text'] = text
            self.in_text = False
            self.text_buf = []

        if self.current is not None and tag == 'article':
            if self.current.get('text') and len(self.current['text']) > 30:
                self.reviews.append(self.current)
            self.current = None

        if self.tag_stack:
            self.tag_stack.pop()

    def handle_data(self, data):
        if self.in_text:
            self.text_buf.append(data)

    def _last_tag(self):
        if not self.tag_stack:
            return None
        return self.tag_stack[-1][0]


# === HTTP fetcher ===
def fetch(url, retries=3, delay=2.0):
    """Получить HTML с User-Agent и задержкой."""
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
                      '(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml',
        'Accept-Language': 'ru-RU,ru;q=0.9,en;q=0.8',
    }
    req = urllib.request.Request(url, headers=headers)
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                # Читаем с правильной кодировкой
                raw = resp.read()
                if resp.headers.get('content-type', '').find('charset=') >= 0:
                    return raw.decode('utf-8', errors='replace')
                # По умолчанию — utf-8
                return raw.decode('utf-8', errors='replace')
        except urllib.error.HTTPError as e:
            if e.code == 429:  # Too Many Requests
                time.sleep(delay * (attempt + 1) * 2)
            elif e.code in (403, 503):
                time.sleep(delay * (attempt + 1))
            else:
                raise
        except Exception:
            if attempt == retries - 1:
                raise
            time.sleep(delay)
    raise RuntimeError(f"Failed to fetch {url} after {retries} retries")


# === Поиск книги ===
def find_book_url(title, author=None):
    """WebSearch через прямой запрос к LiveLib."""
    q = f"{title} {author or ''}".strip()
    search_url = f"https://www.livelib.ru/search?search={quote(q)}"
    html = fetch(search_url)

    # Найти первую ссылку на книгу
    m = re.search(r'href="(/book/\d+)"', html)
    if m:
        return urljoin('https://www.livelib.ru', m.group(1))
    return None


# === Парсинг страницы отзывов ===
def parse_reviews_page(book_url, max_pages=3):
    """Парсит отзывы на странице + пагинация."""
    all_reviews = []
    for page in range(1, max_pages + 1):
        page_url = f"{book_url}?tab=reviews&page={page}" if page > 1 else f"{book_url}?tab=reviews"
        try:
            html = fetch(page_url)
        except Exception as e:
            print(f"  ! Page {page} failed: {e}", file=sys.stderr)
            break

        parser = LiveLibReviewParser()
        parser.feed(html)
        if not parser.reviews:
            break
        all_reviews.extend(parser.reviews)
        print(f"  Page {page}: +{len(parser.reviews)} reviews", file=sys.stderr)
        time.sleep(2.0)

    return all_reviews


# === Извлечение общей информации о книге ===
def extract_book_meta(html, book_url):
    """Извлекает title, author, rating, count."""
    meta = {'book_url': book_url}

    # Title
    m = re.search(r'<h1[^>]*class="book-title[^"]*"[^>]*>([^<]+)</h1>', html)
    if not m:
        m = re.search(r'<title>([^<]+)</title>', html)
    if m:
        title = re.sub(r'\s+', ' ', m.group(1)).strip()
        # Убрать суффиксы типа "— LiveLib"
        title = re.sub(r'\s*[—\-]\s*LiveLib.*$', '', title)
        title = re.sub(r'\s*/\s*Отзывы\s*$', '', title)
        meta['title'] = title

    # Author
    m = re.search(r'<a[^>]*class="book-author[^"]*"[^>]*>([^<]+)</a>', html)
    if not m:
        m = re.search(r'<meta[^>]+name="author"[^>]+content="([^"]+)"', html)
    if m:
        meta['author'] = re.sub(r'\s+', ' ', m.group(1)).strip()

    # Rating
    m = re.search(r'<div[^>]+class="book-rating[^"]*"[^>]*>(\d+[\.,]\d+)', html)
    if m:
        meta['rating_avg'] = float(m.group(1).replace(',', '.'))
    else:
        m = re.search(r'data-rating="(\d+[\.,]\d+)"', html)
        if m:
            meta['rating_avg'] = float(m.group(1).replace(',', '.'))

    # Count
    m = re.search(r'(\d+)\s*(?:отзыв|реценз)', html, re.IGNORECASE)
    if m:
        meta['rating_count'] = int(m.group(1))

    return meta


# === Slugify ===
def slugify(text):
    """Транслитерация для slug."""
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
    p = argparse.ArgumentParser(description='LiveLib reviews parser')
    p.add_argument('title', nargs='?', help='Название книги')
    p.add_argument('author', nargs='?', help='Автор (опционально)')
    p.add_argument('--url', help='Прямой URL книги на LiveLib')
    p.add_argument('--max-pages', type=int, default=3, help='Макс страниц отзывов')
    p.add_argument('--out', default='reviews', help='Папка для сохранения')
    args = p.parse_args()

    # Найти URL книги
    if args.url:
        book_url = args.url
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

    # Получить основную страницу
    main_html = fetch(book_url)
    book_meta = extract_book_meta(main_html, book_url)
    print(f"Книга: {book_meta.get('title', '?')} — {book_meta.get('author', '?')}", file=sys.stderr)
    print(f"Рейтинг: {book_meta.get('rating_avg', '?')} ({book_meta.get('rating_count', '?')} отзывов)", file=sys.stderr)

    # Пауза перед запросом отзывов
    time.sleep(2.0)

    # Парсить отзывы
    reviews = parse_reviews_page(book_url, max_pages=args.max_pages)
    print(f"Собрано: {len(reviews)} отзывов", file=sys.stderr)

    # Собрать финальный JSON
    book_slug = slugify(book_meta.get('title', args.title or 'unknown'))
    bundle = {
        'source': 'livelib',
        'source_url': book_url,
        'fetched_at': datetime.now().isoformat(timespec='seconds'),
        'book': book_meta,
        'rating': {
            'average': book_meta.get('rating_avg'),
            'count': book_meta.get('rating_count', len(reviews)),
        },
        'reviews': reviews,
        'weight': 1.2,  # см. data/sources-rating.md
        'notes': f"Спарсено {len(reviews)} отзывов с {args.max_pages} страниц"
    }

    # Сохранить
    out_dir = Path(args.out) / book_slug
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / 'livelib.json'
    out_path.write_text(json.dumps(bundle, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f"Сохранено: {out_path}", file=sys.stderr)


if __name__ == '__main__':
    main()
