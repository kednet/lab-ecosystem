# Render — WL артефакты → Astro-страница

## Источник

`wish_librarian/output/library/<slug>/`:
- `metadata.json` — `{title, author, year, isbn, language, cover, slug}`
- `cover.jpg` (или `.png`) — обложка
- `summary.md` — основной конспект
- `practical_tips.md` — практические советы
- `reviews.md` — отзывы
- `workbook.md` — упражнения
- `buy_links.md` — где купить
- `scientific.md` — научные ссылки (опционально)

## Алгоритм

### 1. Прочитать `metadata.json`

```json
{
  "title": "Трансерфинг реальности",
  "author": "Вадим Зеланд",
  "year": 2004,
  "isbn": "...",
  "language": "ru",
  "slug": "transerfing-realnosti"
}
```

### 2. Скопировать артефакты в `lab_site/src/data/books/<slug>/`

```bash
cp -r wish_librarian/output/library/<slug>/* lab_site/src/data/books/<slug>/
```

### 3. Сгенерировать `lab_site/src/data/books/<slug>.json`

```json
{
  "slug": "transerfing-realnosti",
  "title": "Трансерфинг реальности",
  "author": "Вадим Зеланд",
  "year": 2004,
  "isbn": "...",
  "language": "ru",
  "summary_path": "/src/data/books/transerfing-realnosti/summary.md",
  "cover_path": "/src/data/books/transerfing-realnosti/cover.jpg",
  "tips_path": "/src/data/books/transerfing-realnosti/practical_tips.md",
  "reviews_path": "/src/data/books/transerfing-realnosti/reviews.md",
  "workbook_path": "/src/data/books/transerfing-realnosti/workbook.md",
  "buy_links_path": "/src/data/books/transerfing-realnosti/buy_links.md"
}
```

### 4. Сгенерировать `lab_site/src/pages/books/<slug>.astro`

Использовать `templates/book-page-astro.astro` как основу.

Layout: `lab_site/src/layouts/Base.astro`.

Импортировать JSON: `import book from '../../data/books/<slug>.json'`.

### 5. Сгенерировать `seo-bundle.json`

```json
{
  "title": "{title} — конспект и практика | Лаборатория желаний",
  "description": "Краткое содержание, практические советы и упражнения по книге {title} автора {author}.",
  "og_image": "/src/data/books/<slug>/cover.jpg",
  "schema": {
    "@context": "https://schema.org",
    "@type": "Book",
    "name": "{title}",
    "author": {"@type": "Person", "name": "{author}"},
    "datePublished": "{year}",
    "isbn": "{isbn}",
    "image": "/cover.jpg"
  }
}
```

### 6. Записать state

```json
{
  "rendered_at": "2026-06-11T10:00:00Z",
  "page_path": "lab_site/src/pages/books/transerfing-realnosti.astro",
  "data_path": "lab_site/src/data/books/transerfing-realnosti.json",
  "artifacts_dir": "lab_site/src/data/books/transerfing-realnosti/",
  "seo_path": "lab_site/src/data/books/transerfing-realnosti/seo-bundle.json"
}
```

## Скрипт

`scripts/render_book.py` — выполняет шаги 2–6 одной командой.
