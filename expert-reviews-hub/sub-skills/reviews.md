# Подскил: REVIEWS (отзывы)

## Назначение
Сбор, структурирование и AI-суммаризация отзывов на книги и услуги. Включает парсинг 6+ источников + свои отзывы + AI-аналитику (pro/cons, рейтинг, тренды) + **видео-отзывы с YouTube (v2026-06-21)**.

## Режимы

### 1. `/reviews {Книга}` — все источники

#### Вход
- Название книги
- (опционально) автор

#### Что делает
1. Запускает ВСЕ парсеры параллельно (через Bash):
   - `scripts/parse_livelib.py`
   - `scripts/parse_litres.py`
   - `scripts/parse_ozon.py`
   - `scripts/parse_vk_reviews.py`
   - `scripts/parse_author_today.py` (для самоиздата)
   - `scripts/parse_goodreads.py` (для англоязычных)
2. Собирает результаты в единый bundle
3. Запускает `/reviews summarize` для AI-аналитики
4. Генерит:
   - `reviews/{book-slug}/bundle.json` — все отзывы + мета
   - `reviews/{book-slug}/bundle.md` — читаемая сводка
   - `reviews/{book-slug}/schema.json` — JSON-LD (Review + AggregateRating)
   - `reviews/{book-slug}/stats.json` — статистика

#### Источники с весами (см. `data/sources-rating.md`)
| Источник | Вес | Примечание |
|----------|-----|------------|
| LiveLib | 🟢 высокий | 100K+ книг, рунете №1 |
| Литрес | 🟢 высокий | Купленные отзывы, более релевантные |
| Ozon | 🟡 средний | Много «купленных» |
| Author.Today | 🟡 средний | Самоиздат, длинные отзывы |
| Goodreads | 🟡 средний | Англоязычные |
| VK (сообщества) | 🟡 средний | Живые обсуждения |
| Telegram | 🟠 живой | Мнения, без оценок |
| YouTube | 🟠 живой | Обзоры |
| Свои (лендинг) | 🟢 высокий | Прямой контакт с клиентом |

### 2. `/reviews livelib {Книга}` — только LiveLib

#### Алгоритм
1. WebFetch `https://www.livelib.ru/book/{slug}` → HTML
2. Grep по HTML: рейтинг, кол-во отзывов, pros/cons
3. WebFetch страницы отзывов (пагинация)
4. Структурировать: `[{author, rating, text, date, source, pros, cons, url}]`

#### Выход
```json
{
  "source": "livelib",
  "book": "Трансерфинг реальности",
  "total_reviews": 1247,
  "average_rating": 4.7,
  "distribution": {"5": 850, "4": 250, "3": 100, "2": 30, "1": 17},
  "reviews": [
    {
      "author": "Иван Петров",
      "rating": 5,
      "text": "...",
      "date": "2024-12-15",
      "url": "...",
      "pros": "Изменил мышление",
      "cons": "Нет научной базы"
    }
  ]
}
```

См. `prompts/review-livelib.md` и `scripts/parse_livelib.py`

### 3. `/reviews litres {Книга}` — только Литрес

#### Особенности
- Отзывы только от купивших книгу (вес выше)
- Есть рейтинг и оценка по 5 параметрам (сюжет, стиль, оформление)
- Длинные развёрнутые отзывы

### 4. `/reviews ozon {Книга}` — только Ozon

#### Особенности
- Много «купленных» — дедуп по шаблонам
- Фильтр: только verified покупка
- Используем как дополнительный источник

### 5. `/reviews social {Книга}` — соцсети

#### Источники
- **VK** — поиск постов по хэштегам и в сообществах
  - Требуется VK API token (опционально)
  - Скрипт: `scripts/parse_vk_reviews.py`
- **Telegram** — парсинг каналов через WebSearch
  - Поиск по ключевым словам в публичных каналах
- **YouTube** — обзоры на книгу
  - Поиск видео, метаданные, транскрипты

### 6. `/reviews own {URL}` — свои отзывы (с лендинга/сайта)

#### Алгоритм
1. WebFetch `URL` → HTML
2. Парсинг структуры отзывов (Schema Review, hReview, Microdata)
3. Если Schema Review — извлечь JSON-LD
4. Иначе — эвристический парсинг (блоки с классом `.review`, `.testimonial`)

#### Выход
- Структурированный JSON в том же формате
- В `source: "own"` и `verified: true` (свои — всегда верифицированы)

### 7. `/reviews summarize {Книга}` — AI-суммаризация

#### Вход
- Bundle отзывов (JSON из любого источника)

#### Алгоритм
1. Собрать все тексты отзывов
2. AI-анализ:
   - **Pros** (3-7 пунктов) — что хвалят
   - **Cons** (3-7 пунктов) — что ругают
   - **Средняя оценка** — взвешенная по весам источников
   - **Тренды** — динамика по времени (растёт/падает популярность)
   - **Цитаты** — 3-5 самых ярких (с указанием автора/источника)
3. **Скоринг доверия** — на основе распределения оценок и источников
4. **Финальный verdict** — 1-2 предложения для карточки книги

#### Выход
```markdown
# Анализ отзывов: {Книга}

## Средняя оценка: 4.7/5 (взвешенная)
Источники: LiveLib 4.7 (847 отзывов), Литрес 4.8 (234), Ozon 4.5 (166)

## ✅ Что хвалят
- Изменяет мышление (87% отзывов)
- Практические техники
- Простой язык

## ❌ Что ругают
- Нет научного обоснования
- Повторы в серии книг
- Местами вода

## 📊 Распределение оценок
[диаграмма]

## 💬 Лучшие цитаты
- "Эта книга перевернула моё отношение к мыслям" — Анна К., LiveLib
- ...

## 🔮 Тренды
Популярность растёт: +15% отзывов в 2026 vs 2025
```

## 📁 СТРУКТУРА ВЫХОДОВ

```
reviews/
└── {book-slug}/
    ├── bundle.json            ← все отзывы со всех источников
    ├── bundle.md              ← читаемая сводка
    ├── livelib.json           ← отзывы с LiveLib
    ├── litres.json            ← отзывы с Литрес
    ├── ozon.json              ← отзывы с Ozon
    ├── vk.json                ← VK
    ├── tg.json                ← Telegram
    ├── youtube.json           ← YouTube (метаданные, без AI-суммаризации)
    ├── video_reviews.json     ← YouTube (с AI-суммаризацией, для рендера на сайте)
    ├── own.json               ← свои
    ├── stats.json             ← статистика
    ├── schema.json            ← JSON-LD (Review[] + AggregateRating)
    └── summary.md             ← AI-аналитика
```

## 🔗 ИНТЕГРАЦИЯ С SEO ADVISOR

`reviews/{slug}/schema.json` → готов к вставке в `schema.json` книги Лаборатории:
```json
{
  "@type": "Book",
  ...
  "aggregateRating": { ... },  // из stats.json
  "review": [ ... ]             // из bundle.json (5-10 лучших)
}
```

## 🔗 ИНТЕГРАЦИЯ С WISHLIBRARIAN

WL уже собирает отзывы через свой `ReviewsParser`. Hub-скил дополняет:
- WL собирает: LiveLib, www.koob.ru (2 источника)
- Hub добавляет: Литрес, Ozon, VK, TG, YouTube, свои (4+ источника)

Подключение:
1. После `process_book` WL → запустить `scripts/sweep_reviews.py` (TBD)
2. Результат скопировать в `<book_folder>/reviews_extended/`
3. Добавить в `metadata.json` поле `reviews_extended_path`

## ⚖️ ЭТИКА

- **Не публикуем отзывы без указания источника**
- **Не искажаем смысл** при цитировании (дословно)
- **Уважаем авторские отзывы** — если автор отзыва против публикации, исключаем
- **YMYL-осторожность** — для психологии/здоровья предупреждаем «субъективное мнение»
- **Rate limit** — не более 1 запроса в 2-3 сек к источнику (см. `scripts/`)

## 🚀 БЫСТРЫЙ СТАРТ

```
/reviews "Трансерфинг реальности"
/reviews livelib "Трансерфинг реальности"
/reviews social "Трансерфинг реальности"
/reviews video "Алхимик" --author "Пауло Коэльо"  # см. режим 8
/reviews own https://lab.com/library/transerfing
/reviews summarize "Трансерфинг реальности"
```

См. также: `sub-skills/experts.md` (карточка автора книги)

---

## 8. `/reviews video {slug-книги}` — видео-отзывы с YouTube (NEW 2026-06-21)

### Назначение
Сбор видео-обзоров и отзывов с YouTube для конкретной книги. Без своего видео — мы собираем чужие обзоры и легально встраиваем через превью + ссылку (fair use, embed-формат YouTube ToS).

### Использование
```bash
# По конкретной книге (ищет "<title> <author> отзыв")
python scripts/parse_youtube.py --book-slug alhimik-koeluo --mode=book

# Fallback по автору (если по книге 0 видео с транскриптами)
python scripts/parse_youtube.py --book-slug alhimik-koeluo --mode=author --author "Пауло Коэльо"

# Без AI-суммаризации (только метаданные — быстрее, для отладки)
python scripts/parse_youtube.py --book-slug alhimik-koeluo --mode=book --no-ai

# Сколько видео оставить (default 3, max ~10)
python scripts/parse_youtube.py --book-slug alhimik-koeluo --mode=book --top 5
```

### Алгоритм
1. **Поиск видео** — YouTube Data API v3 (`search.list`):
   - Запрос: `"{title} {author} отзыв"`
   - Фильтры: `type=video`, `relevanceLanguage=ru`, `videoDuration=medium` (4-20 мин, исключаем Shorts)
   - Берём top-15 кандидатов
2. **Метаданные** — `videos.list` (название, канал, длительность, просмотры, лайки, дата)
3. **Транскрипты** — `youtube-transcript-api` (Python-библиотека). До 12 КБ на видео (лимит контекста LLM).
4. **Фильтрация релевантности**:
   - В транскрипте должно быть название книги (длина ≥4 букв) ИЛИ имя автора
   - Минимум просмотров: 200 (настраивается `YOUTUBE_MIN_VIEWS`)
   - Свежесть: ≤6 лет (настраивается `YOUTUBE_MAX_AGE_YEARS`)
5. **Ранжирование**: `views × recency_weight` (новые получают буст, старые — штраф)
6. **AI-суммаризация** (опционально) — YandexGPT через промпт `prompts/review-summarize-youtube.md`:
   - Извлекает `mentions_book`, `summary`, `key_quotes` (с таймкодами), `sentiment`, `topics`, `recommendation`, `confidence`
   - Жёсткие правила: не выдумывать цитаты, только дословно из транскрипта
7. **Fallback book → author**: если по книге 0 видео с транскриптами, ищем по автору:
   - Запросы: `"{author} книги отзыв"`, `"{author} рекомендации книг"`, `"{author} обзор книг"`
   - В результат добавляется `scope: "author"`, `target_slug: <slug-книги-куда-показывать>`
8. **Сохранение**:
   - `output/<slug>/video_reviews.json` — режим `book`
   - `output/authors/<author-slug>/video_reviews.json` — режим `author`

### Структура выходного JSON
```json
{
  "scope": "book | author",
  "slug": "alhimik-koeluo",
  "book_title": "Алхимик",
  "book_author": "Пауло Коэльо",
  "videos": [
    {
      "video_id": "dQw4w9WgXcQ",
      "title": "Алхимик — книга, которая...",
      "channel": "Читатель со стажем",
      "published_at": "2026-04-15T00:00:00Z",
      "duration_sec": 522,
      "duration_str": "8:42",
      "views": 12400,
      "likes": 450,
      "thumbnail_default": "https://i.ytimg.com/vi/dQw4w9WgXcQ/hqdefault.jpg",
      "watch_url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
      "embed_url": "https://www.youtube.com/embed/dQw4w9WgXcQ",
      "mentions_book": true,
      "mentioned_book_title": "Алхимик",
      "mentioned_author": "Коэльо",
      "summary": "Рецензент считает книгу руководством...",
      "key_quotes": [
        {"text": "Алхимик учит слышать свою душу", "timestamp": "1:30", "context": "..."}
      ],
      "sentiment": "mixed",
      "topics": ["самопознание", "перемены", "мистика"],
      "recommendation": "с оговорками",
      "confidence": "high"
    }
  ],
  "generated_at": "2026-06-21T...",
  "source": "youtube",
  "weight": 0.9
}
```

### Интеграция с сайтом
- Astro-компонент: `lab_site/src/components/VideoReviews.astro`
- Либа загрузки: `lab_site/src/lib/video_reviews.ts`
- Рендерится внутри таба "Отзывы" на `/library/<slug>/` (если `video_reviews.json` есть)
- Если `scope=author` — плашка «📚 Видео об авторе, а не о книге»
- Метрика: при клике на карточку → `video_review_clicked` (TODO, не реализовано)

### Требования
- **YouTube Data API v3 ключ** в `expert-reviews-hub/.env` → `YOUTUBE_API_KEY=...`
  - Получить: Google Cloud Console → APIs & Services → YouTube Data API v3 → Enable → Credentials
  - Квоты: 10000/день, search.list = 100 квот, videos.list = 1 квота
  - Рекомендуется restrict by IP (VPS 89.108.88.74)
- **YandexGPT** ключ в `wish_librarian/.env` → `YANDEX_API_KEY`, `YANDEX_FOLDER_ID` (для AI-суммаризации)
- **Зависимости**: `pip install google-api-python-client youtube-transcript-api tenacity`
  - `google-api-python-client` не используется напрямую (MITM-конфликт), но нужен для `google-auth`
  - Реальные запросы идут через `urllib.request` с `ssl._create_unverified_context()` (корп. MITM)

### Edge cases
- **API ключ отсутствует** → понятная ошибка "YOUTUBE_API_KEY не задан в .env", exit 1
- **YouTube API квоты исчерпаны** → 403 forbidden, скрипт падает (TODO: retry with backoff)
- **Транскрипт недоступен** (видео без субтитров, автор их отключил) → видео пропускается
- **Не тот автор** в результатах → строгая фильтрация по имени в транскрипте
- **Не та книга** (по запросу «Теория невероятности» нашлась лекция по физике) → фильтр по названию
- **AI-суммаризация упала** (timeout, JSON parse error) → видео сохраняется с `confidence=low`, `ai_error` в JSON
- **Корпоративный MITM** (kednet) → используется `urllib` + `ssl._create_unverified_context()`, google-api-python-client **не работает** (httplib2 не дружит с MITM)
- **Telegram HTML** (`<br>` vs `&nbsp;`) → не применимо, мы только читаем транскрипт
- **Все видео отфильтрованы** (0 релевантных) → fallback на `mode=author` (если `YOUTUBE_FALLBACK_TO_AUTHOR=true`)

### Стоимость и rate limit
- YouTube Data API: 15 видео × 2 запроса (search + videos) = 16 квот на книгу
- YandexGPT: 1 запрос на видео (max 2000 токенов) — 3 видео = 3 запроса
- 100 книг × 16 квот = 1600 квот/день (запас 8400 квот)
- Sleep между запросами не нужен (YouTube сам rate-limit'ит)

### Связанные файлы
- `scripts/parse_youtube.py` — основной скрипт
- `prompts/review-summarize-youtube.md` — YandexGPT-промпт
- `data/sources-rating.md` — youtube вес 0.9 (обновить если меняется)
- `lab_site/src/components/VideoReviews.astro` — рендер на сайте
- `lab_site/src/lib/video_reviews.ts` — загрузчик JSON
