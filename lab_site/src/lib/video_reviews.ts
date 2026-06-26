import { readFileSync, existsSync } from 'node:fs';
import { dirname, join } from 'node:path';

const PROJECT_ROOT = process.cwd();
const BOOKS_JSON_PATH = join(PROJECT_ROOT, 'src', 'data', 'books.json');
const VIDEO_REVIEWS_DIR = join(PROJECT_ROOT, 'src', 'data', 'books');  // <slug>/video_reviews.json

export interface VideoReview {
  video_id: string;
  title: string;
  channel: string;
  published_at: string;
  duration_sec: number;
  duration_str: string;
  views: number;
  likes: number;
  thumbnail_default: string;
  thumbnail_maxres: string;
  watch_url: string;
  embed_url: string;
  transcript_chars: number;
  mentions_book?: boolean | null;
  mentioned_book_title?: string | null;
  mentioned_author?: string | null;
  summary?: string | null;
  key_quotes?: Array<{ text: string; timestamp: string; context: string }>;
  sentiment?: 'positive' | 'mixed' | 'negative' | 'neutral' | null;
  topics?: string[];
  recommendation?: 'рекомендует' | 'с оговорками' | 'не рекомендует' | 'без оценки' | null;
  confidence?: 'high' | 'medium' | 'low' | null;
  ai_skipped?: boolean;
  no_transcript?: boolean;
  ai_error?: string;
}

export interface VideoReviewsBundle {
  scope: 'book' | 'author';
  slug: string;
  book_title?: string;
  book_author?: string;
  target_book_title?: string;
  author?: string;
  search_query?: string;
  search_queries?: string[];
  videos: VideoReview[];
  generated_at: string;
  source: string;
  weight: number;
}

/**
 * Загрузить video_reviews.json для книги.
 * 1) Сначала ищем <slug>/video_reviews.json (scope=book)
 * 2) Fallback: <author_slug>/video_reviews.json в authors/ (scope=author, target на этот slug)
 * 3) Из books.json берём source_path — там лежит копия от парсера
 */
export function loadVideoReviews(slug: string): VideoReviewsBundle | null {
  const candidates: string[] = [];

  // 1) Канонический путь: src/data/books/<slug>/video_reviews.json
  candidates.push(join(VIDEO_REVIEWS_DIR, slug, 'video_reviews.json'));

  // 2) Через source_path (WL-папка)
  if (existsSync(BOOKS_JSON_PATH)) {
    const data = JSON.parse(readFileSync(BOOKS_JSON_PATH, 'utf-8')) as {
      books: { slug: string; source_path?: string; author?: string }[];
    };
    const book = data.books.find((b) => b.slug === slug);
    if (book?.source_path) {
      candidates.push(join(book.source_path, 'video_reviews.json'));
    }
    // 3) Author fallback — ищем по всем папкам
    if (book?.author) {
      const authorSlug = slugify(book.author);
      candidates.push(join(VIDEO_REVIEWS_DIR, 'authors', authorSlug, 'video_reviews.json'));
    }
  }

  for (const path of candidates) {
    if (existsSync(path)) {
      try {
        return JSON.parse(readFileSync(path, 'utf-8')) as VideoReviewsBundle;
      } catch {
        continue;
      }
    }
  }
  return null;
}

function slugify(text: string): string {
  const table: Record<string, string> = {
    'а': 'a', 'б': 'b', 'в': 'v', 'г': 'g', 'д': 'd', 'е': 'e', 'ё': 'yo',
    'ж': 'zh', 'з': 'z', 'и': 'i', 'й': 'i', 'к': 'k', 'л': 'l', 'м': 'm',
    'н': 'n', 'о': 'o', 'п': 'p', 'р': 'r', 'с': 's', 'т': 't', 'у': 'u',
    'ф': 'f', 'х': 'h', 'ц': 'ts', 'ч': 'ch', 'ш': 'sh', 'щ': 'sch',
    'ъ': '', 'ы': 'y', 'ь': '', 'э': 'e', 'ю': 'yu', 'я': 'ya',
  };
  const out: string[] = [];
  for (const ch of text.toLowerCase()) {
    out.push(table[ch] ?? ch);
  }
  return out.join('').replace(/[^a-z0-9]+/g, '-').replace(/^-+|-+$/g, '').slice(0, 80);
}