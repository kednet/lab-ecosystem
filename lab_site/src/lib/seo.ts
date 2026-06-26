/**
 * Генераторы JSON-LD (Schema.org) для Yandex/Google rich results.
 *
 * - organizationLd(): Organization + WebSite + SearchAction — на КАЖДОЙ странице.
 *   Эмитит единый ld+json блок в Base.astro (один раз).
 * - blogPostingLd(): BlogPosting — на каждой странице блога.
 * - breadcrumbLd(): хлебные крошки (опционально).
 *
 * Все эмиттеры возвращают строку JSON, экранируя закрывающие теги в строках,
 * чтобы Yandex/Google валидаторы не сломались.
 */
import { legal } from '../data/legal';

const SITE = 'https://app.pulab.ru';
const SITE_NAME = 'ЛАБОРАТОРИЯ ЖЕЛАНИЙ';

export function organizationLd(): string {
  return JSON.stringify({
    '@context': 'https://schema.org',
    '@graph': [
      {
        '@type': 'Organization',
        '@id': `${SITE}/#organization`,
        name: SITE_NAME,
        url: SITE,
        logo: {
          '@type': 'ImageObject',
          url: `${SITE}/avatar.jpg`,
          width: 512,
          height: 512,
        },
        description:
          'Сообщество осознанных желаний. Библиотека конспектов, трекер, AI-коуч и аудио-медитации.',
        email: legal.complaintsEmail,
        address: {
          '@type': 'PostalAddress',
          addressLocality: legal.legalAddress,
          addressCountry: 'RU',
        },
        sameAs: [
          'https://vk.com/club237295798',
          'https://t.me/wishlab_channel',
        ],
      },
      {
        '@type': 'WebSite',
        '@id': `${SITE}/#website`,
        url: SITE,
        name: SITE_NAME,
        inLanguage: 'ru-RU',
        publisher: { '@id': `${SITE}/#organization` },
        // SearchAction — для будущего поиска по сайту (Google отдаёт sitelinks searchbox).
        potentialAction: {
          '@type': 'SearchAction',
          target: {
            '@type': 'EntryPoint',
            urlTemplate: `${SITE}/library/?q={search_term_string}`,
          },
          'query-input': 'required name=search_term_string',
        },
      },
    ],
  });
}

export interface BlogPostingInput {
  slug: string;
  title: string;
  excerpt: string;
  date: string; // ISO yyyy-mm-dd
  author: string;
  tags: string[];
  read_min: number;
  cover?: string | null;
}

export function blogPostingLd(post: BlogPostingInput): string {
  const url = `${SITE}/blog/${post.slug}/`;
  const image = post.cover ? (post.cover.startsWith('http') ? post.cover : `${SITE}${post.cover}`) : `${SITE}/og-default.png`;

  return JSON.stringify({
    '@context': 'https://schema.org',
    '@type': 'BlogPosting',
    '@id': url,
    mainEntityOfPage: { '@type': 'WebPage', '@id': url },
    url,
    headline: post.title,
    description: post.excerpt,
    datePublished: post.date,
    dateModified: post.date,
    inLanguage: 'ru-RU',
    author: {
      '@type': 'Organization',
      name: post.author,
      url: SITE,
    },
    publisher: {
      '@type': 'Organization',
      name: SITE_NAME,
      logo: { '@type': 'ImageObject', url: `${SITE}/avatar.jpg` },
    },
    image: {
      '@type': 'ImageObject',
      url: image,
      width: 1200,
      height: 630,
    },
    keywords: post.tags.join(', '),
    timeRequired: `PT${post.read_min}M`,
    articleSection: 'Саморазвитие',
  });
}

export function breadcrumbLd(items: Array<{ name: string; url: string }>): string {
  return JSON.stringify({
    '@context': 'https://schema.org',
    '@type': 'BreadcrumbList',
    itemListElement: items.map((it, i) => ({
      '@type': 'ListItem',
      position: i + 1,
      name: it.name,
      item: it.url.startsWith('http') ? it.url : `${SITE}${it.url}`,
    })),
  });
}

export interface FaqItem {
  question: string;
  answer: string;
}

export function faqLd(items: FaqItem[]): string {
  return JSON.stringify({
    '@context': 'https://schema.org',
    '@type': 'FAQPage',
    mainEntity: items.map((it) => ({
      '@type': 'Question',
      name: it.question,
      acceptedAnswer: {
        '@type': 'Answer',
        text: it.answer,
      },
    })),
  });
}

export function itemListLd(
  name: string,
  items: Array<{ name: string; url: string; description?: string }>,
): string {
  return JSON.stringify({
    '@context': 'https://schema.org',
    '@type': 'ItemList',
    name,
    itemListElement: items.map((it, i) => ({
      '@type': 'ListItem',
      position: i + 1,
      name: it.name,
      url: it.url.startsWith('http') ? it.url : `${SITE}${it.url}`,
      description: it.description,
    })),
  });
}

/**
 * JSON-LD для интерактивного теста/квиза (Schema.org Quiz).
 * Полезно для /detector/ и подобных лид-магнитов:
 * поисковики могут показывать блок «Тест» в расширенных сниппетах.
 */
export interface QuizInput {
  name: string;
  description: string;
  about: string;
  url: string;
  /** Количество вопросов (для hasPart). */
  questionCount?: number;
}

export function quizLd(input: QuizInput): Record<string, unknown> {
  const base: Record<string, unknown> = {
    '@context': 'https://schema.org',
    '@type': 'Quiz',
    name: input.name,
    description: input.description,
    about: input.about,
    url: input.url.startsWith('http') ? input.url : `${SITE}${input.url}`,
    inLanguage: 'ru-RU',
    isAccessibleForFree: true,
    provider: {
      '@type': 'Organization',
      name: 'ЛАБОРАТОРИЯ ЖЕЛАНИЙ',
      url: SITE,
    },
  };
  if (input.questionCount) {
    base.numberOfQuestions = input.questionCount;
    base.educationalAlignment = {
      '@type': 'AlignmentObject',
      alignmentType: 'teaches',
      targetName: 'Самопознание через различение навязанных и истинных желаний',
    };
  }
  return base;
}

/**
 * JSON-LD для онлайн-встречи (Schema.org Event).
 * Используется на лендингах клубов/вебинаров: первая встреча клуба,
 * открытая лекция и т.п. Поисковики могут показывать расширенный сниппет
 * с датой, временем, местом и кнопкой «Записаться».
 */
export interface EventInput {
  name: string;
  description: string;
  /** ISO datetime, например "2026-07-28T19:00:00+03:00". */
  startDate: string;
  endDate: string;
  /** URL виртуальной площадки (для OnlineEventAttendanceMode). */
  url: string;
  /** Free / paid: true для бесплатного события. */
  free?: boolean;
  /** image (полный URL). */
  image?: string;
  /** performer / organizer override. */
  organizerName?: string;
  inLanguage?: string;
}

export function eventLd(input: EventInput): string {
  return JSON.stringify({
    '@context': 'https://schema.org',
    '@type': 'Event',
    name: input.name,
    description: input.description,
    startDate: input.startDate,
    endDate: input.endDate,
    eventAttendanceMode: 'https://schema.org/OnlineEventAttendanceMode',
    eventStatus: 'https://schema.org/EventScheduled',
    location: {
      '@type': 'VirtualLocation',
      url: input.url.startsWith('http') ? input.url : `${SITE}${input.url}`,
    },
    organizer: {
      '@type': 'Organization',
      name: input.organizerName ?? SITE_NAME,
      url: SITE,
      logo: `${SITE}/avatar.jpg`,
    },
    image: input.image ? [input.image] : [`${SITE}/og-default.png`],
    inLanguage: input.inLanguage ?? 'ru-RU',
    isAccessibleForFree: input.free !== false,
    offers: {
      '@type': 'Offer',
      price: '0',
      priceCurrency: 'RUB',
      availability: 'https://schema.org/InStock',
      url: input.url.startsWith('http') ? input.url : `${SITE}${input.url}`,
      validFrom: new Date().toISOString(),
    },
  });
}

/**
 * JSON-LD для книги (Schema.org Book).
 * Используется в карточках книг и в лендингах клубов, чтобы
 * поисковики показывали расширенный сниппет с автором и обложкой.
 */
export interface BookInput {
  name: string;
  author: string;
  /** URL страницы с подробностями о книге. */
  url: string;
  /** URL обложки. */
  image?: string;
  /** ISBN, если есть. */
  isbn?: string;
  /** Год издания. */
  datePublished?: string;
  /** Краткое описание (1-2 предложения). */
  description?: string;
  /** Художественная / нон-фикшн. */
  genre?: string;
}

export function bookLd(input: BookInput): string {
  const url = input.url.startsWith('http') ? input.url : `${SITE}${input.url}`;
  return JSON.stringify({
    '@context': 'https://schema.org',
    '@type': 'Book',
    name: input.name,
    author: {
      '@type': 'Person',
      name: input.author,
    },
    url,
    image: input.image
      ? input.image.startsWith('http')
        ? input.image
        : `${SITE}${input.image}`
      : undefined,
    isbn: input.isbn,
    datePublished: input.datePublished,
    description: input.description,
    genre: input.genre,
    inLanguage: 'ru-RU',
    publisher: {
      '@type': 'Organization',
      name: SITE_NAME,
      url: SITE,
    },
  });
}
