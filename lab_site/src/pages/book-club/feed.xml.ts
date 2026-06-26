import type { APIRoute } from 'astro';

export const prerender = true;

/**
 * RSS-фид для книжного клуба — источник для Дзен-RSS.
 * Контент: анонс клуба, ссылка на страницу /book-club/.
 *
 * Дзен подхватывает фид автоматически после добавления URL
 * `https://app.pulab.ru/book-club/feed.xml` в настройках канала.
 * См. инструкцию в publisher_skill/docs/zen-setup.md.
 */

const SITE_URL = 'https://app.pulab.ru';
const FEED_TITLE = 'Книжный клуб Лаборатории желаний';
const FEED_DESCRIPTION =
  'Читаем «К себе нежно» Ольги Примаченко вместе: 4 недели, главы в своём темпе, практики и встречи по желанию участниц. Бесплатный вход.';

export const GET: APIRoute = () => {
  const pageUrl = `${SITE_URL}/book-club/`;
  const pubDate = new Date().toUTCString();

  const xml = `<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom">
  <channel>
    <title>${escapeXml(FEED_TITLE)}</title>
    <link>${pageUrl}</link>
    <description>${escapeXml(FEED_DESCRIPTION)}</description>
    <language>ru-ru</language>
    <lastBuildDate>${pubDate}</lastBuildDate>
    <atom:link href="${SITE_URL}/book-club/feed.xml" rel="self" type="application/rss+xml" />
    <item>
      <title>Книжный клуб Лаборатории желаний — открыт набор на первую книгу</title>
      <link>${pageUrl}</link>
      <guid isPermaLink="true">${pageUrl}</guid>
      <pubDate>${pubDate}</pubDate>
      <description><![CDATA[
        <p>Первая книга клуба — «К себе нежно» Ольги Примаченко. Читаем в своём темпе, делаем практики, встречаемся, когда группа соберётся.</p>
        <p>4 недели · главы по 10-15 минут в день · бесплатный вход.</p>
        <p>Когда нас наберётся достаточно — откроем чат и вместе выберем время встречи.</p>
        <p><a href="${pageUrl}">Зарегистрироваться на /book-club/</a></p>
      ]]></description>
    </item>
  </channel>
</rss>`;

  return new Response(xml, {
    headers: {
      'Content-Type': 'application/rss+xml; charset=utf-8',
      'Cache-Control': 'public, max-age=3600',
    },
  });
};

function escapeXml(s: string): string {
  return s
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&apos;');
}