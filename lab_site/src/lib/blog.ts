import { readFileSync, existsSync } from 'node:fs';
import { join } from 'node:path';
import { marked } from 'marked';

const PROJECT_ROOT = process.cwd();
const BLOG_DIR = join(PROJECT_ROOT, 'src', 'data', 'blog');

export interface BlogPostMeta {
  slug: string;
  title: string;
  excerpt: string;
  date: string; // ISO yyyy-mm-dd
  author: string;
  tags: string[];
  read_min: number;
  cover: string | null;
  /** FAQ-блок для JSON-LD FAQPage. Опционально. Парсится из frontmatter. */
  faq?: { question: string; answer: string }[];
}

export interface BlogPost extends BlogPostMeta {
  html: string;
}

let cache: BlogPost[] | null = null;

/**
 * Убирает YAML frontmatter (если есть) и ведущий H1 из markdown —
 * чтобы избежать дубля заголовка, который рендерится в [slug].astro header.
 * Метаданные хранятся в blog.json, поэтому frontmatter тут не нужен.
 */
function preprocessMarkdown(raw: string): string {
  // 1) Снять YAML frontmatter в начале файла (от `---` до следующего `---`)
  const fmMatch = raw.match(/^---\r?\n[\s\S]*?\r?\n---\r?\n?/);
  let text = fmMatch ? raw.slice(fmMatch[0].length) : raw;

  // 2) Снять ведущий H1 (`# Заголовок` в самом начале) — с или без пустых строк перед
  //    Допускаем варианты: `# title`, `# title\n`, `   # title\n`
  const h1Match = text.match(/^\s*#\s+[^\n]*\n+/);
  text = h1Match ? text.slice(h1Match[0].length) : text;

  return text;
}

function loadAll(): BlogPost[] {
  if (cache) return cache;
  const jsonPath = join(PROJECT_ROOT, 'src', 'data', 'blog.json');
  const file = readFileSync(jsonPath, 'utf-8');
  const parsed = JSON.parse(file) as { posts: BlogPostMeta[] };
  cache = parsed.posts
    .map((p) => {
      const mdPath = join(BLOG_DIR, `${p.slug}.md`);
      if (!existsSync(mdPath)) return null;
      const raw = readFileSync(mdPath, 'utf-8');
      const cleaned = preprocessMarkdown(raw);
      const html = marked.parse(cleaned, { async: false }) as string;
      return { ...p, html };
    })
    .filter((p): p is BlogPost => p !== null)
    // свежие сверху
    .sort((a, b) => b.date.localeCompare(a.date));
  return cache;
}

export function getAllPosts(): BlogPost[] {
  return loadAll();
}

export function getPost(slug: string): BlogPost | null {
  return loadAll().find((p) => p.slug === slug) ?? null;
}

/**
 * Связанные посты по пересечению тегов. Возвращает до N постов,
 * отсортированных по количеству общих тегов (убывание), затем по дате.
 * Если общих тегов нет — отдаёт свежие посты этого блога.
 */
export function getRelatedPosts(slug: string, limit = 3): BlogPost[] {
  const all = loadAll();
  const current = all.find((p) => p.slug === slug);
  if (!current) return all.slice(0, limit);

  const currentTags = new Set(current.tags);
  const scored = all
    .filter((p) => p.slug !== slug)
    .map((p) => ({
      post: p,
      score: p.tags.filter((t) => currentTags.has(t)).length,
    }))
    .sort((a, b) => {
      if (b.score !== a.score) return b.score - a.score;
      return b.post.date.localeCompare(a.post.date);
    });

  const related = scored.filter((s) => s.score > 0).slice(0, limit);
  if (related.length < limit) {
    const filler = scored
      .filter((s) => s.score === 0)
      .slice(0, limit - related.length);
    related.push(...filler);
  }
  return related.map((s) => s.post);
}

export function formatDate(iso: string): string {
  const d = new Date(iso);
  return d.toLocaleDateString('ru-RU', {
    day: 'numeric',
    month: 'long',
    year: 'numeric',
  });
}
