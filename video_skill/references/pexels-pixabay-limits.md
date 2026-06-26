# Pexels & Pixabay API Limits (Phase 2+)

Справка по лимитам стоковых API. Файл пустой — наполняется в Phase 2.

## Pexels

- **Endpoint:** https://api.pexels.com/videos/search
- **Auth header:** `Authorization: <PEXELS_API_KEY>`
- **Бесплатный план:** 200 запросов/час, 20 000 запросов/месяц
- **Размер видео:** несколько разрешений (HD/SD/4K), обычно 1920×1080 или 4K
- **Длительность:** клипы 5–60 сек
- **Формат:** mp4
- **License:** бесплатно для коммерческого использования, без атрибуции

### Пример запроса
```bash
curl -H "Authorization: $PEXELS_API_KEY" \
  "https://api.pexels.com/videos/search?query=forest&per_page=5"
```

## Pixabay

- **Endpoint:** https://pixabay.com/api/videos/
- **Auth query:** `?key=<PIXABAY_API_KEY>`
- **Бесплатный план:** 100 запросов/мин, 5 000 запросов/час
- **Размер видео:** 4K/HD/SD
- **Длительность:** клипы 5–60 сек
- **Формат:** mp4
- **License:** Pixabay License (бесплатно для коммерческого использования, без атрибуции)

### Пример запроса
```bash
curl "https://pixabay.com/api/videos/?key=$PIXABAY_API_KEY&q=ocean&per_page=5"
```

## Стратегия (Phase 2)

1. Сначала Pexels (качественнее), fallback на Pixabay
2. По одному запросу на шот (`per_page=5` → выбрать первый)
3. Кешировать результаты в `data/library/<sha1>.json` (избежать повторов)
4. Rate limit: 1 запрос/сек на сервис (safety margin)
5. Логировать в `logs/pexels.log` и `logs/pixabay.log`

## Связано с

- `sub-skills/auto-mode.md` — Phase 2
- `scripts/pexels_client.py` — клиент (stub)
- `scripts/pixabay_client.py` — клиент (stub)
- `scripts/fetch_clips.py` — orchestrator (stub)
- `data/library/.gitkeep` — кеш
