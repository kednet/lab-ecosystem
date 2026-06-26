/**
 * Загрузчик экспертов для Astro-страниц.
 *
 * Источник: src/data/experts/{slug}.json + src/data/experts/index.json
 * (генерируется scripts/sync_reviews_hub.py)
 *
 * Использует import.meta.glob для статического чтения JSON на этапе build —
 * работает в SSG + hybrid output без node:fs.
 */
import indexData from '../data/experts/index.json';

export interface ExpertQuote {
  quote: string;
  author: string;
  source: string;
  year?: number | null;
}

export interface ExpertRecommendedBook {
  slug: string;
  title?: string;
  context?: string;
}

export interface Expert {
  slug: string;
  name: string;
  jobTitle: string;
  description: string;
  url: string;
  image: string;
  email: string;
  sameAs: string[];
  knowsAbout: string[];
  alumniOf: string[];
  awards: string[];
  worksFor: string;
  quotes: ExpertQuote[];
  media: { youtube?: string; telegram?: string; vk?: string };
  tags: string[];
  score: number;
  schema_jsonld: Record<string, unknown>;
  recommended_books: ExpertRecommendedBook[];
  source_path: string;
  generated_at: string;
  featured_video: string;            // YouTube video ID (11 chars), optional
}

export interface ExpertsIndex {
  generated_at: string;
  total: number;
  experts: Array<{
    slug: string;
    name: string;
    jobTitle: string;
    tags: string[];
    score: number;
    image: string;
  }>;
}

// import.meta.glob со статическим шаблоном — Vite/Astro собирает все .json
// на этапе build и инлайнит в бандл. Никаких node:fs в runtime.
const expertModules = import.meta.glob<Expert>('../data/experts/*.json', { eager: true });

const allExperts: Expert[] = Object.values(expertModules)
  .filter((e) => e && e.slug)
  .sort((a, b) => (b.score - a.score) || a.name.localeCompare(b.name, 'ru'));

const indexCache: ExpertsIndex = {
  generated_at: (indexData as any)?.generated_at ?? '',
  total: (indexData as any)?.total ?? allExperts.length,
  experts: (indexData as any)?.experts ?? allExperts.map((e) => ({
    slug: e.slug,
    name: e.name,
    jobTitle: e.jobTitle,
    tags: e.tags,
    score: e.score,
    image: e.image,
  })),
};

export function getExpertsIndex(): ExpertsIndex {
  return indexCache;
}

export function getAllExperts(): Expert[] {
  return allExperts;
}

const bySlug = new Map<string, Expert>(allExperts.map((e) => [e.slug, e]));

export function getExpert(slug: string): Expert | null {
  return bySlug.get(slug) ?? null;
}

export function getExpertSchemaJsonLd(expert: Expert): string {
  if (expert.schema_jsonld && expert.schema_jsonld['@type']) {
    return JSON.stringify(expert.schema_jsonld, null, 2);
  }

  return JSON.stringify(
    {
      '@context': 'https://schema.org',
      '@type': 'Person',
      name: expert.name,
      jobTitle: expert.jobTitle,
      description: expert.description,
      url: expert.url || undefined,
      image: expert.image || undefined,
      sameAs: expert.sameAs?.filter(Boolean) ?? [],
      knowsAbout: expert.knowsAbout?.filter(Boolean) ?? [],
      award: expert.awards?.filter(Boolean) ?? [],
      worksFor: expert.worksFor
        ? { '@type': 'Organization', name: expert.worksFor }
        : undefined,
    },
    null,
    2,
  );
}
