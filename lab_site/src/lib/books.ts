import { readFileSync, existsSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';
import { marked } from 'marked';

const __dirname = dirname(fileURLToPath(import.meta.url));
void __dirname; // reserved for future use
// process.cwd() — это корень проекта и в dev, и в build
const PROJECT_ROOT = process.cwd();
const BOOKS_DIR = join(PROJECT_ROOT, 'src', 'data', 'books');

export interface BookMD {
  raw: string;
  html: string;
}

export type BookContentType = 'summary' | 'workbook' | 'tips' | 'buy_links' | 'reviews';

export interface Book {
  slug: string;
  title: string;
  author: string;
  year: number;
  description: string;
  tags: string[];
  themes: string[];
  queries: string[];
  cover: string | null;
  free: boolean;
  has_summary: boolean;
  has_workbook: boolean;
  has_tips: boolean;
  has_buy_links: boolean;
  has_pdf: boolean;
  source_path: string;
  // v1.7: тип контента (опц.). "fiction-reflective" = художка с зерном для рефлексии
  book_type?: 'nonfiction' | 'fiction-reflective' | string;
  // Загруженные MD (html и raw), null если файл отсутствует
  summary: BookMD | null;
  workbook: BookMD | null;
  tips: BookMD | null;
  buy_links: BookMD | null;
  reviews: BookMD | null;
}

const contentTypeMap: Record<BookContentType, keyof Pick<Book, 'summary' | 'workbook' | 'tips' | 'buy_links' | 'reviews'>> = {
  summary: 'summary',
  workbook: 'workbook',
  tips: 'tips',
  buy_links: 'buy_links',
  reviews: 'reviews',
};

function loadMD(slug: string, type: BookContentType): BookMD | null {
  // 1) Канонический путь: src/data/books/<slug>/<type>.md
  // 2) Fallback через source_path из books.json — для книг, импортированных из
  //    wish_librarian/output/library/<wl_dir>/. Там лежат summary.md, workbook.md, tips.md.
  //    Без этого fallback страница /library/<slug>/ не находит контент для новых книг.
  const candidates: string[] = [join(BOOKS_DIR, slug, `${type}.md`)];
  // Fallback через source_path из books.json — для всех типов, включая buy_links.
  // Раньше buy_links исключался (исторически), но это блокировало чтение из WL-папки.
  const jsonPath = join(PROJECT_ROOT, 'src', 'data', 'books.json');
  if (existsSync(jsonPath)) {
    const data = JSON.parse(readFileSync(jsonPath, 'utf-8')) as { books: { slug: string; source_path?: string }[] };
    const book = data.books.find((b) => b.slug === slug);
    if (book?.source_path) {
      // Абсолютный путь к WL-папке
      candidates.push(join(book.source_path, `${type}.md`));
      // wl_dir рядом с books.json (если source_path указывал в общую папку)
      const wlDir = book.source_path.split(/[\\/]/).pop();
      if (wlDir) candidates.push(join(BOOKS_DIR, wlDir, `${type}.md`));
    }
  }
  for (const path of candidates) {
    if (existsSync(path)) {
      const raw = readFileSync(path, 'utf-8');
      const html = marked.parse(raw, { async: false }) as string;
      return { raw, html };
    }
  }
  return null;
}

let allBooksCache: Book[] | null = null;

function loadBooksJson(): Book[] {
  if (allBooksCache) return allBooksCache;
  const dataPath = join(PROJECT_ROOT, 'src', 'data', 'books.json');
  const fileContent = readFileSync(dataPath, 'utf-8');
  const parsed = JSON.parse(fileContent) as { books: Omit<Book, 'summary' | 'workbook' | 'tips' | 'buy_links' | 'reviews'>[] };
  allBooksCache = parsed.books.map((b) => {
    const summary = loadMD(b.slug, 'summary');
    const workbook = loadMD(b.slug, 'workbook');
    const tips = loadMD(b.slug, 'tips');
    const buy_links = loadMD(b.slug, 'buy_links');
    const reviews = loadMD(b.slug, 'reviews');
    return {
      ...b,
      summary,
      workbook,
      tips,
      buy_links,
      reviews,
    };
  });
  return allBooksCache;
}

export function getAllBooks(): Book[] {
  return loadBooksJson();
}

export function getBook(slug: string): Book | null {
  return loadBooksJson().find((b) => b.slug === slug) ?? null;
}

export function hasContent(book: Book, type: BookContentType): boolean {
  return book[contentTypeMap[type]] !== null;
}
