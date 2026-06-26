"""
VK reviews parser — посты с хэштегом #отзыв или упоминанием книги
Использование:
  python parse_vk_reviews.py "Трансерфинг реальности" --groups pulabru,psychology_ru
  python parse_vk_reviews.py "Трансерфинг реальности" --search  # только поиск
Выход: reviews/{book-slug}/social.json (секция vk)
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
def fetch(url, retries=3, delay=2.0):
    """Получить HTML с User-Agent (без авторизации — только публичные посты)."""
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
                raw = resp.read()
                return raw.decode('utf-8', errors='replace')
        except urllib.error.HTTPError as e:
            if e.code == 429:
                time.sleep(delay * (attempt + 1) * 2)
            else:
                raise
        except Exception:
            if attempt == retries - 1:
                raise
            time.sleep(delay)
    raise RuntimeError(f"Failed to fetch {url}")


# === Парсинг постов VK из HTML (без авторизации) ===
def parse_vk_search(html):
    """Парсит результаты поиска постов vk.com.

    Без авторизации VK отдаёт превью постов с автором, текстом, датой.
    """
    posts = []
    # Упрощённый regex: ищем блоки <div class="wall_post_text">...</div>
    text_pattern = re.compile(
        r'<div class="wall_post_text[^"]*"[^>]*>(.*?)</div>\s*</div>',
        re.DOTALL
    )
    author_pattern = re.compile(
        r'<a class="post_author[^"]*"[^>]*>([^<]+)</a>'
    )
    date_pattern = re.compile(
        r'<time[^>]+datetime="([^"]+)"'
    )

    for m in text_pattern.finditer(html):
        block = m.group(0)
        text_raw = m.group(1)
        # Очистить HTML
        text = re.sub(r'<[^>]+>', ' ', text_raw)
        text = re.sub(r'&[a-z]+;', ' ', text)
        text = re.sub(r'\s+', ' ', text).strip()

        if len(text) < 50:
            continue

        post = {
            'source': 'vk',
            'text': text,
            'author': None,
            'date': None,
            'url': None,
            'likes': 0,
            'reposts': 0,
            'comments': 0,
            'tone': None,  # AI-классификация (опционально)
        }

        am = author_pattern.search(block)
        if am:
            post['author'] = am.group(1).strip()

        dm = date_pattern.search(block)
        if dm:
            post['date'] = dm.group(1)

        # Лайки/репосты
        lm = re.search(r'(\d+)\s*</span>\s*</a>\s*</div>\s*<div[^>]*>([^<]*?понравилось|лайк)', html[m.end():m.end()+500], re.IGNORECASE)
        # (упрощённо, точная структура VK сложная)

        posts.append(post)

    return posts


# === Поиск постов через vk.com/search ===
def search_vk_posts(query, max_posts=20):
    """Ищет посты через публичный поиск vk.com."""
    search_url = f"https://vk.com/search?c%5Bper_page%5D=40&c%5Bq%5D={quote(query)}&c%5Bsection%5D=news"
    try:
        html = fetch(search_url)
    except Exception as e:
        print(f"  ! Search failed: {e}", file=sys.stderr)
        return []

    posts = parse_vk_search(html)
    print(f"  VK search: {len(posts)} posts for '{query}'", file=sys.stderr)
    return posts[:max_posts]


# === Парсинг постов сообщества через /wall ===
def parse_group_wall(group_slug, max_posts=20):
    """Парсит стену публичного сообщества."""
    wall_url = f"https://vk.com/{group_slug}"
    try:
        html = fetch(wall_url)
    except Exception as e:
        print(f"  ! Wall {group_slug} failed: {e}", file=sys.stderr)
        return []

    posts = parse_vk_search(html)
    print(f"  VK wall {group_slug}: {len(posts)} posts", file=sys.stderr)
    return posts[:max_posts]


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
    p = argparse.ArgumentParser(description='VK reviews parser')
    p.add_argument('query', help='Поисковый запрос (название книги)')
    p.add_argument('--groups', help='VK-группы через запятую (например pulabru,psychology_ru)')
    p.add_argument('--max-posts', type=int, default=20)
    p.add_argument('--out', default='reviews')
    p.add_argument('--search-only', action='store_true', help='Только поиск, без групп')
    args = p.parse_args()

    all_posts = []

    # 1. Поиск по VK
    print(f"Ищу в VK: {args.query}", file=sys.stderr)
    search_posts = search_vk_posts(args.query, max_posts=args.max_posts)
    all_posts.extend(search_posts)
    time.sleep(2.0)

    # 2. Парсинг групп
    if not args.search_only and args.groups:
        for group in args.groups.split(','):
            group = group.strip()
            wall_posts = parse_group_wall(group, max_posts=args.max_posts)
            # Фильтровать по запросу
            filtered = [p for p in wall_posts
                       if args.query.lower().split()[0] in (p.get('text') or '').lower()]
            all_posts.extend(filtered)
            time.sleep(2.0)

    # Дедуп по тексту
    seen_texts = set()
    unique_posts = []
    for p in all_posts:
        text_norm = re.sub(r'\s+', ' ', (p.get('text') or '').lower())[:100]
        if text_norm and text_norm not in seen_texts:
            seen_texts.add(text_norm)
            unique_posts.append(p)

    print(f"Уникальных постов: {len(unique_posts)}", file=sys.stderr)

    # Сохранить
    book_slug = slugify(args.query)
    bundle = {
        'source': 'social',
        'fetched_at': datetime.now().isoformat(timespec='seconds'),
        'query': args.query,
        'total_mentions': len(unique_posts),
        'sources': {'vk': len(unique_posts)},
        'posts': unique_posts,
        'weight': 0.8,  # см. data/sources-rating.md
        'notes': f"VK: {len(unique_posts)} постов (без авторизации, только публичные)"
    }

    out_dir = Path(args.out) / book_slug
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / 'social.json'
    out_path.write_text(json.dumps(bundle, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f"Сохранено: {out_path}", file=sys.stderr)


if __name__ == '__main__':
    main()
