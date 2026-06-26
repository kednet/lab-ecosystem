# Пример успешной публикации

## Книга: Трансерфинг реальности (Вадим Зеланд, 2004)

### Исходные артефакты (после WishLibrarian)

```
wish_librarian/output/library/transerfing-realnosti/
├── metadata.json
├── cover.jpg
├── summary.md
├── practical_tips.md
├── reviews.md
├── workbook.md
├── buy_links.md
└── scientific.md
```

### Запуск

```bash
/publish transerfing-realnosti
```

### Что произошло (логи)

```
[render] ✓ скопировано 8 артефактов в lab_site/src/data/books/transerfing-realnosti/
[render] ✓ сгенерирован transerfing-realnosti.json
[render] ✓ сгенерирована страница transerfing-realnosti.astro
[render] ✓ seo-bundle.json создан
[deploy] ✓ npm run build (12.4 сек)
[deploy] ✓ wrangler pages deploy → https://pulab.online/books/transerfing-realnosti
[deploy] ✓ HTTP 200 OK
[deploy] ✓ скриншот: tmp/transerfing-realnosti-deploy.png
[announce] TG ✓ post sent (id=12345)
[announce] VK ✓ wall.post created (id=67890)
[announce] email — Phase 2+
[admin] TG ✓ @kfigh notified
[state] ✓ status=published, published_at=2026-06-11T10:10:00Z
```

### Итоговые файлы

```
lab_site/src/pages/books/transerfing-realnosti.astro  # страница
lab_site/src/data/books/transerfing-realnosti.json     # мета
lab_site/src/data/books/transerfing-realnosti/         # артефакты (копия)
tmp/transerfing-realnosti-deploy.png                   # скриншот
state/transerfing-realnosti.json                       # финал
```

### Время

- Render: 2.1 сек
- Build: 12.4 сек
- Deploy: 8.7 сек
- Announce (TG + VK): 4.2 сек
- **Итого: 27.4 сек** на полный цикл.

### Стоимость

- Cloudflare Pages: бесплатно (Free tier).
- TG Bot: бесплатно.
- VK API: бесплатно.
- **Итого: $0** за публикацию одной книги.
