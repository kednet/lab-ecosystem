"""
YouTube-парсер отзывов на книги.
Использование:
  # По конкретной книге:
  python parse_youtube.py --book-slug alhimik-koeluo --mode=book
  # Fallback по автору (если по книге 0 видео):
  python parse_youtube.py --book-slug alhimik-koeluo --mode=author --author "Пауло Коэльо"
  # Только сухой прогон (без AI-суммаризации):
  python parse_youtube.py --book-slug alhimik-koeluo --no-ai
Выход: output/{slug}/video_reviews.json или output/authors/{author_slug}/video_reviews.json

Fallback-логика:
  1. mode=book — ищем "<title> <author> отзыв"
  2. Если 0 релевантных видео и YOUTUBE_FALLBACK_TO_AUTHOR=true → mode=author
  3. mode=author — ищем "<author> книги отзыв" / "<author> рекомендации"
"""
import sys
import os
import json
import re
import time
import argparse
import logging
from pathlib import Path
from datetime import datetime, timezone
from urllib.parse import quote
from pathlib import Path as PathLib

# Загрузка .env без зависимостей (простое чтение)
# Ищем в: 1) <skill_root>/.env, 2) <skill_root>/scripts/.env
def load_env() -> dict:
    env = {}
    candidates = [
        PathLib(__file__).parent.parent / '.env',
        PathLib(__file__).parent / '.env',
    ]
    for path in candidates:
        if path.exists():
            for line in path.read_text(encoding='utf-8').splitlines():
                line = line.strip()
                if not line or line.startswith('#') or '=' not in line:
                    continue
                k, v = line.split('=', 1)
                env[k.strip()] = v.strip().strip('"').strip("'")
            break
    return env

ENV = load_env()

# UTF-8 fix
try:
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')
except Exception:
    pass

# Logging
log_level = ENV.get('LOG_LEVEL', 'INFO').upper()
logging.basicConfig(
    level=getattr(logging, log_level, logging.INFO),
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%H:%M:%S',
    stream=sys.stderr,
)
log = logging.getLogger('parse_youtube')

# === Config ===
YOUTUBE_API_KEY = ENV.get('YOUTUBE_API_KEY', '')
MAX_CANDIDATES = int(ENV.get('YOUTUBE_MAX_CANDIDATES', '15'))
MIN_VIEWS = int(ENV.get('YOUTUBE_MIN_VIEWS', '200'))
MAX_AGE_YEARS = int(ENV.get('YOUTUBE_MAX_AGE_YEARS', '6'))
FINAL_TOP = int(ENV.get('YOUTUBE_FINAL_TOP', '3'))
RELEVANCE_LANG = ENV.get('YOUTUBE_RELEVANCE_LANG', 'ru')
FALLBACK_TO_AUTHOR = ENV.get('YOUTUBE_FALLBACK_TO_AUTHOR', 'true').lower() == 'true'
USE_AI_SUMMARY = ENV.get('YOUTUBE_USE_AI_SUMMARY', 'true').lower() == 'true'
AI_PROVIDER = ENV.get('YOUTUBE_SUMMARY_AI_PROVIDER', 'yandex')

OUTPUT_DIR = PathLib(__file__).parent.parent / ENV.get('OUTPUT_DIR', './output')
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# === Books registry (минимальный — для подтягивания title/author по slug) ===
# Ищем в нескольких местах: относительно скрипта, относительно cwd, по env
def _find_books_json() -> Path | None:
    script_dir = PathLib(__file__).parent.parent
    candidates = [
        # 1) <skill>/lab_site/src/data/books.json
        script_dir / 'lab_site' / 'src' / 'data' / 'books.json',
        # 2) <skill>/../lab_site/src/data/books.json
        script_dir.parent / 'lab_site' / 'src' / 'data' / 'books.json',
        # 3) по env (если переопределено)
        PathLib(ENV.get('BOOKS_JSON_PATH', '')) if ENV.get('BOOKS_JSON_PATH') else None,
        # 4) относительно cwd
        PathLib.cwd() / 'lab_site' / 'src' / 'data' / 'books.json',
        # 5) /var/www/lab-site/dist — копия после билда? Нет, в dist нет books.json. Skip.
    ]
    for p in candidates:
        if p and p.exists():
            return p
    return None


def load_books_registry() -> dict:
    """Загрузить slug → {title, author} из books.json. Возвращает пустой dict при ошибке."""
    p = _find_books_json()
    if not p:
        log.warning("books.json не найден ни в одном из путей. Используй --author вручную.")
        return {}
    log.debug(f"books.json: {p}")
    try:
        data = json.loads(p.read_text(encoding='utf-8'))
        return {b['slug']: {'title': b['title'], 'author': b['author']} for b in data.get('books', [])}
    except Exception as e:
        log.warning(f"Не удалось загрузить books.json: {e}")
        return {}


def slugify(text: str) -> str:
    table = {
        'а': 'a', 'б': 'b', 'в': 'v', 'г': 'g', 'д': 'd', 'е': 'e', 'ё': 'yo',
        'ж': 'zh', 'з': 'z', 'и': 'i', 'й': 'i', 'к': 'k', 'л': 'l', 'м': 'm',
        'н': 'n', 'о': 'o', 'п': 'p', 'р': 'r', 'с': 's', 'т': 't', 'у': 'u',
        'ф': 'f', 'х': 'h', 'ц': 'ts', 'ч': 'ch', 'ш': 'sh', 'щ': 'sch',
        'ъ': '', 'ы': 'y', 'ь': '', 'э': 'e', 'ю': 'yu', 'я': 'ya',
    }
    out = []
    for ch in text.lower():
        out.append(table.get(ch, ch))
    s = ''.join(out)
    s = re.sub(r'[^a-z0-9]+', '-', s).strip('-')
    return s[:80]


def parse_duration_iso8601(d: str) -> int:
    """PT4M13S → 253 секунды. Возвращает 0 при ошибке."""
    if not d:
        return 0
    m = re.match(r'PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?', d)
    if not m:
        return 0
    h = int(m.group(1) or 0)
    mi = int(m.group(2) or 0)
    s = int(m.group(3) or 0)
    return h * 3600 + mi * 60 + s


def format_duration(seconds: int) -> str:
    if seconds <= 0:
        return "?:??"
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    if h:
        return f"{h}:{m:02d}:{s:02d}"
    return f"{m}:{s:02d}"


# === YouTube API (через прямой REST — google-api-python-client падает на корп. MITM) ===
def _yt_get(path: str, params: dict) -> dict:
    """Прямой GET к YouTube Data API v3. Без google-api-python-client.
    Причина: googleapiclient использует httplib2, который плохо дружит с TLS-MITM.
    """
    if not YOUTUBE_API_KEY:
        raise RuntimeError("YOUTUBE_API_KEY не задан в .env")
    import urllib.request
    import urllib.parse
    import ssl

    params = {**params, 'key': YOUTUBE_API_KEY}
    qs = urllib.parse.urlencode(params)
    url = f"https://www.googleapis.com/youtube/v3/{path}?{qs}"

    req = urllib.request.Request(url)
    ctx = ssl._create_unverified_context()
    with urllib.request.urlopen(req, timeout=30, context=ctx) as resp:
        raw = resp.read().decode('utf-8')
        return json.loads(raw)


def yt_search_videos(query: str, max_results: int = MAX_CANDIDATES) -> list:
    """Поиск видео через YouTube Data API v3."""
    data = _yt_get('search', {
        'part': 'id',
        'q': query,
        'type': 'video',
        'maxResults': min(max_results, 50),
        'relevanceLanguage': RELEVANCE_LANG,
        'videoDuration': 'medium',
        'order': 'relevance',
    })
    video_ids = [item['id']['videoId'] for item in data.get('items', [])]
    if not video_ids:
        return []

    # Метаданные
    videos_data = _yt_get('videos', {
        'part': 'snippet,statistics,contentDetails',
        'id': ','.join(video_ids),
    })
    return videos_data.get('items', [])


def yt_get_transcript(video_id: str) -> list:
    """Получить транскрипт видео. Возвращает [{text, start, duration}] или []."""
    try:
        from youtube_transcript_api import YouTubeTranscriptApi
        # API 1.x — через fetch
        api = YouTubeTranscriptApi()
        snippets = api.fetch(video_id, languages=[RELEVANCE_LANG, 'ru', 'en'])
        return [{'text': s.text, 'start': s.start, 'duration': s.duration} for s in snippets]
    except Exception as e:
        log.debug(f"Транскрипт {video_id} недоступен: {e}")
        return []


def transcript_to_text(snippets: list, max_chars: int = 12000) -> str:
    """Собрать транскрипт в текст с таймкодами. Ограничение max_chars для контекста LLM."""
    lines = []
    total = 0
    for s in snippets:
        ts = format_duration(int(s['start']))
        text = s['text'].replace('\n', ' ').strip()
        line = f"[{ts}] {text}"
        if total + len(line) > max_chars:
            lines.append(f"...[truncated at {total} chars]...")
            break
        lines.append(line)
        total += len(line)
    return '\n'.join(lines)


# === Фильтрация ===
def filter_relevant(videos: list, title: str, author: str, transcripts: dict) -> list:
    """Оставляем только видео, относящиеся к книге/автору.
    Логика (от сильного к слабому):
      1) Транскрипт упоминает название книги или автора — сильный сигнал
      2) Название видео содержит название книги или автора — средний сигнал
      3) Нет ни транскрипта, ни явного упоминания в title — отбрасываем
    """
    title_words = [w for w in re.findall(r'\w+', title.lower()) if len(w) >= 4]
    author_words = [w for w in re.findall(r'\w+', author.lower()) if len(w) >= 4]
    if not title_words and not author_words:
        return videos  # нет ключевых слов — не фильтруем

    relevant = []
    for v in videos:
        vid = v.get('id')
        snippet = v.get('snippet', {})
        v_title = (snippet.get('title', '') + ' ' + snippet.get('description', '')).lower()
        transcript = transcripts.get(vid, [])
        transcript_text = ' '.join(s['text'].lower() for s in transcript) if transcript else ''

        # 1) Сильный сигнал: транскрипт упоминает книгу/автора
        transcript_match = False
        if transcript_text:
            title_match = any(w in transcript_text for w in title_words) if title_words else False
            author_match = any(w in transcript_text for w in author_words) if author_words else False
            transcript_match = title_match or (author_match and not title_words)

        # 2) Средний сигнал: название видео содержит название книги/автора
        title_match_v = any(w in v_title for w in title_words) if title_words else False
        author_match_v = any(w in v_title for w in author_words) if author_words else False
        title_match_overall = title_match_v or (author_match_v and not title_words)

        if transcript_match or title_match_overall:
            relevant.append(v)
    return relevant


def filter_by_age(videos: list) -> list:
    """Фильтр по дате — только свежие видео (не старше MAX_AGE_YEARS)."""
    cutoff = datetime.now(timezone.utc).timestamp() - MAX_AGE_YEARS * 365 * 24 * 3600
    fresh = []
    for v in videos:
        published = v.get('snippet', {}).get('publishedAt')
        if not published:
            fresh.append(v)
            continue
        try:
            ts = datetime.fromisoformat(published.replace('Z', '+00:00')).timestamp()
            if ts >= cutoff:
                fresh.append(v)
        except Exception:
            fresh.append(v)
    return fresh


def filter_by_views(videos: list) -> list:
    """Минимум MIN_VIEWS просмотров."""
    return [v for v in videos if int(v.get('statistics', {}).get('viewCount', 0)) >= MIN_VIEWS]


def rank_videos(videos: list) -> list:
    """Ранжирование: views * recency_weight. Свежие видео получают буст."""
    now = datetime.now(timezone.utc).timestamp()
    scored = []
    for v in videos:
        views = int(v.get('statistics', {}).get('viewCount', 0))
        published = v.get('snippet', {}).get('publishedAt')
        age_days = 365 * 3  # дефолт 3 года
        if published:
            try:
                ts = datetime.fromisoformat(published.replace('Z', '+00:00')).timestamp()
                age_days = max(1, (now - ts) / 86400)
            except Exception:
                pass
        # recency_weight: видео младше года = 1.0, 3 года = 0.5, 6 лет = 0.25
        recency = max(0.1, 1.0 / (1.0 + age_days / 365))
        score = views * recency
        scored.append((score, v))
    scored.sort(key=lambda x: -x[0])
    return [v for _, v in scored]


# === LLM суммаризация ===
def summarize_with_ai(video: dict, book_title: str, book_author: str, transcript_text: str) -> dict:
    """YandexGPT-суммаризация транскрипта. Возвращает dict с полями промпта."""
    if not transcript_text or not USE_AI_SUMMARY:
        return {
            'mentions_book': None,
            'summary': None,
            'key_quotes': [],
            'sentiment': None,
            'topics': [],
            'recommendation': None,
            'confidence': 'low',
            'ai_skipped': True,
        }

    # Подгружаем промпт
    prompt_path = PathLib(__file__).parent.parent / 'prompts' / 'review-summarize-youtube.md'
    system_prompt = prompt_path.read_text(encoding='utf-8') if prompt_path.exists() else ''

    snippet = video.get('snippet', {})
    user_msg = (
        f"Книга: «{book_title}»\n"
        f"Автор: {book_author}\n"
        f"Название видео: {snippet.get('title', '')}\n"
        f"Канал: {snippet.get('channelTitle', '')}\n\n"
        f"Транскрипт:\n{transcript_text}"
    )

    try:
        # Используем WL фабрику, если есть
        sys.path.insert(0, str(PathLib(__file__).parent.parent.parent / 'wish_librarian'))
        try:
            from agent.ai.factory import get_llm_client  # type: ignore
            client = get_llm_client(provider=AI_PROVIDER)
            response = client.generate(
                system=system_prompt,
                user=user_msg,
                max_tokens=2000,
                temperature=0.2,
            )
            raw = response.text if hasattr(response, 'text') else str(response)
        except Exception as e:
            log.warning(f"WL фабрика недоступна ({e}), пробую прямой YandexGPT")
            raw = _direct_yandexgpt(system_prompt, user_msg)

        # Парсим JSON из ответа (могут быть ```json ... ```)
        raw_clean = raw.strip()
        if raw_clean.startswith('```'):
            raw_clean = re.sub(r'^```(?:json)?\s*\n?', '', raw_clean)
            raw_clean = re.sub(r'\n?```\s*$', '', raw_clean)

        parsed = json.loads(raw_clean)
        return parsed
    except Exception as e:
        log.error(f"Ошибка суммаризации: {e}")
        return {
            'mentions_book': None,
            'summary': None,
            'key_quotes': [],
            'sentiment': None,
            'topics': [],
            'recommendation': None,
            'confidence': 'low',
            'ai_error': str(e),
        }


def _direct_yandexgpt(system: str, user: str) -> str:
    """Прямой вызов YandexGPT (fallback если WL фабрика не подгрузилась)."""
    import urllib.request
    import ssl
    api_key = ENV.get('YANDEX_API_KEY', '') or os.environ.get('YANDEX_API_KEY', '')
    folder_id = ENV.get('YANDEX_FOLDER_ID', '') or os.environ.get('YANDEX_FOLDER_ID', '')
    if not api_key or not folder_id:
        raise RuntimeError("YANDEX_API_KEY / YANDEX_FOLDER_ID не найдены в .env")

    url = "https://llm.api.cloud.yandex.net/foundationModels/v1/completion"
    payload = {
        "modelUri": f"gpt://{folder_id}/yandexgpt/latest",
        "completionOptions": {
            "stream": False,
            "temperature": 0.2,
            "maxTokens": 2000,
        },
        "messages": [
            {"role": "system", "text": system},
            {"role": "user", "text": user},
        ],
    }

    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode('utf-8'),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Api-Key {api_key}",
        },
    )
    # Корпоративный MITM — отключаем проверку сертификата
    ctx = ssl._create_unverified_context()
    with urllib.request.urlopen(req, timeout=60, context=ctx) as resp:
        body = json.loads(resp.read().decode('utf-8'))
        return body['result']['alternatives'][0]['message']['text']


# === Main ===
def run_book_mode(slug: str, registry: dict) -> dict:
    if slug not in registry:
        raise SystemExit(f"Slug '{slug}' не найден в books.json. Используй --author для fallback-режима.")

    book = registry[slug]
    title, author = book['title'], book['author']
    log.info(f"[book] {title} — {author}")

    query = f"{title} {author} отзыв"
    videos = yt_search_videos(query, MAX_CANDIDATES)
    log.info(f"  Найдено кандидатов: {len(videos)}")

    # Получаем транскрипты
    transcripts = {}
    for v in videos:
        vid = v['id']
        transcripts[vid] = yt_get_transcript(vid)
    with_transcripts = sum(1 for t in transcripts.values() if t)
    log.info(f"  С транскриптами: {with_transcripts}/{len(videos)}")

    # Фильтрация
    relevant = filter_relevant(videos, title, author, transcripts)
    log.info(f"  Релевантных (упоминают книгу): {len(relevant)}")
    fresh = filter_by_age(relevant)
    log.info(f"  Свежих (≤ {MAX_AGE_YEARS} лет): {len(fresh)}")
    by_views = filter_by_views(fresh)
    log.info(f"  С {MIN_VIEWS}+ просмотрами: {len(by_views)}")

    if not by_views and FALLBACK_TO_AUTHOR:
        log.info("  По книге видео не найдено → fallback на автора")
        return None  # Сигнал для main()

    ranked = rank_videos(by_views)
    final = ranked[:FINAL_TOP]
    log.info(f"  Финальный топ-{FINAL_TOP}: {len(final)} видео")

    return {
        'scope': 'book',
        'slug': slug,
        'book_title': title,
        'book_author': author,
        'search_query': query,
        'videos': [_video_to_dict(v, title, author, transcripts.get(v['id'], [])) for v in final],
    }


def run_author_mode(author: str, target_slug: str, registry: dict) -> dict:
    log.info(f"[author] {author} → для книги {target_slug}")

    queries = [
        f"{author} книги отзыв",
        f"{author} рекомендации книг",
        f"{author} обзор книг",
    ]

    all_videos = []
    seen_ids = set()
    for q in queries:
        videos = yt_search_videos(q, MAX_CANDIDATES // len(queries) + 3)
        for v in videos:
            if v['id'] not in seen_ids:
                seen_ids.add(v['id'])
                all_videos.append(v)
        if len(all_videos) >= MAX_CANDIDATES:
            break

    log.info(f"  Найдено кандидатов (по всем запросам): {len(all_videos)}")

    # Транскрипты
    transcripts = {}
    for v in all_videos:
        transcripts[v['id']] = yt_get_transcript(v['id'])
    with_transcripts = sum(1 for t in transcripts.values() if t)
    log.info(f"  С транскриптами: {with_transcripts}/{len(all_videos)}")

    # Фильтр: упоминание автора в транскрипте
    relevant = filter_relevant(all_videos, '', author, transcripts)
    log.info(f"  Упоминают автора: {len(relevant)}")

    fresh = filter_by_age(relevant)
    by_views = filter_by_views(fresh)
    log.info(f"  После фильтра age+views: {len(by_views)}")

    ranked = rank_videos(by_views)
    final = ranked[:FINAL_TOP]
    log.info(f"  Финальный топ-{FINAL_TOP}: {len(final)} видео")

    # target_book_title для суммаризации — книга, на чьей странице показываем
    target_title = registry.get(target_slug, {}).get('title', '')

    return {
        'scope': 'author',
        'slug': target_slug,  # slug страницы, где будет рендериться
        'target_book_title': target_title,
        'author': author,
        'search_queries': queries,
        'videos': [_video_to_dict(v, target_title, author, transcripts.get(v['id'], [])) for v in final],
    }


def _video_to_dict(video: dict, book_title: str, book_author: str, transcript: list) -> dict:
    """Сформировать dict видео для JSON."""
    snippet = video.get('snippet', {})
    stats = video.get('statistics', {})
    content = video.get('contentDetails', {})

    video_id = video['id']
    duration_sec = parse_duration_iso8601(content.get('duration', ''))

    # Суммаризация (транскрипт → LLM)
    transcript_text = transcript_to_text(transcript) if transcript else ''
    summary = summarize_with_ai(video, book_title, book_author, transcript_text) if transcript_text else {
        'mentions_book': None,
        'summary': None,
        'key_quotes': [],
        'sentiment': None,
        'topics': [],
        'recommendation': None,
        'confidence': 'low',
        'no_transcript': True,
    }

    return {
        'video_id': video_id,
        'title': snippet.get('title', ''),
        'channel': snippet.get('channelTitle', ''),
        'published_at': snippet.get('publishedAt', ''),
        'duration_sec': duration_sec,
        'duration_str': format_duration(duration_sec),
        'views': int(stats.get('viewCount', 0)),
        'likes': int(stats.get('likeCount', 0)),
        'thumbnail_default': f"https://i.ytimg.com/vi/{video_id}/hqdefault.jpg",
        'thumbnail_maxres': f"https://i.ytimg.com/vi/{video_id}/maxresdefault.jpg",
        'watch_url': f"https://www.youtube.com/watch?v={video_id}",
        'embed_url': f"https://www.youtube.com/embed/{video_id}",
        'transcript_chars': len(transcript_text),
        **summary,
    }


def save_output(data: dict, mode: str, slug_or_author: str) -> Path:
    if mode == 'book':
        out_dir = OUTPUT_DIR / slug_or_author
    else:  # author
        author_slug = slugify(slug_or_author)
        out_dir = OUTPUT_DIR / 'authors' / author_slug
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / 'video_reviews.json'

    data['generated_at'] = datetime.now(timezone.utc).isoformat(timespec='seconds')
    data['source'] = 'youtube'
    data['weight'] = 0.9  # как в expert-reviews-hub data/sources-rating.md

    out_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
    log.info(f"Сохранено: {out_path}")
    return out_path


def main():
    global FINAL_TOP, USE_AI_SUMMARY
    p = argparse.ArgumentParser(description='YouTube reviews parser для expert-reviews-hub')
    p.add_argument('--book-slug', required=True, help='Slug книги из books.json')
    p.add_argument('--mode', choices=['book', 'author'], default='book',
                   help='Режим поиска: book (по книге) или author (fallback)')
    p.add_argument('--author', help='Имя автора (для mode=author)')
    p.add_argument('--no-ai', action='store_true', help='Пропустить AI-суммаризацию (только метаданные)')
    p.add_argument('--top', type=int, default=None, help=f'Сколько видео оставить (default {FINAL_TOP})')
    args = p.parse_args()

    if args.top:
        FINAL_TOP = args.top
    if args.no_ai:
        USE_AI_SUMMARY = False

    if not YOUTUBE_API_KEY:
        log.error("YOUTUBE_API_KEY не задан в .env")
        sys.exit(1)

    registry = load_books_registry()
    log.info(f"Загружено книг из books.json: {len(registry)}")

    try:
        if args.mode == 'book':
            data = run_book_mode(args.book_slug, registry)
            if data is None and FALLBACK_TO_AUTHOR:
                # Fallback на автора
                book = registry.get(args.book_slug, {})
                author = book.get('author') or args.author
                if not author:
                    log.error("Нет автора для fallback. Укажи --author")
                    sys.exit(1)
                data = run_author_mode(author, args.book_slug, registry)
                if data and data.get('videos'):
                    save_output(data, 'author', author)
            else:
                if data:
                    save_output(data, 'book', args.book_slug)
        else:  # author mode
            author = args.author
            if not author and args.book_slug in registry:
                author = registry[args.book_slug].get('author', '')
            if not author:
                log.error("Укажи --author или передай --book-slug существующей книги")
                sys.exit(1)
            data = run_author_mode(author, args.book_slug, registry)
            if data:
                save_output(data, 'author', author)

        log.info("✅ Готово")
    except Exception as e:
        log.exception(f"❌ Ошибка: {e}")
        sys.exit(2)


if __name__ == '__main__':
    main()