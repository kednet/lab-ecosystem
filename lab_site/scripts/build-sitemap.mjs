/**
 * Генератор sitemap.xml. Запускается как prebuild шаг:
 *   - читает src/data/blog.json (даты публикаций),
 *   - собирает статические разделы (библиотека, эксперты, ...),
 *   - пишет public/sitemap.xml.
 *
 * @astrojs/sitemap@3.7.3 падает на Astro 4.16 (_routes undefined) — обходим своим скриптом.
 */
import { readFileSync, writeFileSync } from 'node:fs';
import { join, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = dirname(fileURLToPath(import.meta.url));
const ROOT = join(__dirname, '..');
const SITE = 'https://app.pulab.ru';

// --- 1) Блог: берём из blog.json ---
const blogJson = JSON.parse(readFileSync(join(ROOT, 'src/data/blog.json'), 'utf-8'));
const blogUrls = blogJson.posts.map((p) => ({
  loc: `${SITE}/blog/${p.slug}/`,
  lastmod: p.date,
  changefreq: 'monthly',
  priority: '0.7',
}));
const blogIndex = {
  loc: `${SITE}/blog/`,
  lastmod: blogJson.updated_at,
  changefreq: 'weekly',
  priority: '0.8',
};

// --- 2) Библиотека: парсим каталог книг (по тому же паттерну, что и library/index.astro) ---
// Список книг пока захардкожен — синхронизирован с build выводом.
const books = [
  'dumai-medlenno-reshai-bystro-daniel-kaneman-daniel-kaneman',
  'ot-mechty-do-uspeha-trunin-r-a',
  'transerfing-realnosti-i-prostranstvo-variantov-zeland-vadim',
  'transerfing-realnosti-vadim-zeland',
  'k-sebe-nezhno-primachenko',
];
const bookUrls = books.map((slug) => ({
  loc: `${SITE}/library/${slug}/`,
  lastmod: '2026-06-21',
  changefreq: 'monthly',
  priority: '0.6',
}));
const libraryIndex = {
  loc: `${SITE}/library/`,
  lastmod: '2026-06-21',
  changefreq: 'weekly',
  priority: '0.9',
};

// --- 3) Эксперты ---
const expertUrls = [
  { loc: `${SITE}/experts/`, lastmod: '2026-06-01', changefreq: 'monthly', priority: '0.6' },
  { loc: `${SITE}/experts/mark-rozin/`, lastmod: '2026-06-01', changefreq: 'monthly', priority: '0.5' },
];

// --- 4) Статические страницы ---
const staticPages = [
  { loc: `${SITE}/`, lastmod: '2026-06-21', changefreq: 'weekly', priority: '1.0' },
  { loc: `${SITE}/about/`, lastmod: '2026-06-21', changefreq: 'monthly', priority: '0.6' },
  { loc: `${SITE}/audio/`, lastmod: '2026-06-21', changefreq: 'weekly', priority: '0.8' },
  { loc: `${SITE}/wish-map/`, lastmod: '2026-06-21', changefreq: 'monthly', priority: '0.9' },
  { loc: `${SITE}/generate/`, lastmod: '2026-06-21', changefreq: 'monthly', priority: '0.6' },
  { loc: `${SITE}/pricing/`, lastmod: '2026-06-21', changefreq: 'monthly', priority: '0.7' },
  { loc: `${SITE}/detector/`, lastmod: '2026-06-21', changefreq: 'monthly', priority: '0.9' },
  { loc: `${SITE}/book-club/`, lastmod: '2026-06-21', changefreq: 'weekly', priority: '0.9' },
  { loc: `${SITE}/experiments/`, lastmod: '2026-06-21', changefreq: 'weekly', priority: '0.7' },
  { loc: `${SITE}/my-experiment/`, lastmod: '2026-06-21', changefreq: 'monthly', priority: '0.5' },
  { loc: `${SITE}/blog/`, lastmod: '2026-06-21', changefreq: 'weekly', priority: '0.8' },
  { loc: `${SITE}/offer/`, lastmod: '2026-06-01', changefreq: 'yearly', priority: '0.3' },
  { loc: `${SITE}/privacy/`, lastmod: '2026-06-01', changefreq: 'yearly', priority: '0.3' },
];

const all = [...staticPages, libraryIndex, ...bookUrls, ...expertUrls, blogIndex, ...blogUrls];

const escape = (s) => s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');

const xml = `<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
${all
  .map(
    (u) => `  <url>
    <loc>${escape(u.loc)}</loc>
    <lastmod>${u.lastmod}</lastmod>
    <changefreq>${u.changefreq}</changefreq>
    <priority>${u.priority}</priority>
  </url>`,
  )
  .join('\n')}
</urlset>
`;

writeFileSync(join(ROOT, 'public/sitemap.xml'), xml, 'utf-8');
console.log(`[sitemap] wrote ${all.length} URLs to public/sitemap.xml`);
