# Литрес парсер — отзывы от купивших книгу

## Назначение
Сбор отзывов с litres.ru — особенность: пишут только те, кто **купил книгу** (вес выше, чем LiveLib).

## Вход
- **Название книги** (с автором)
- (опционально) URL на litres.ru

## Алгоритм

### Шаг 1. Найти страницу книги

#### 1.1. WebSearch
```
site:litres.ru "{Книга}" "{Автор}"
"{Книга}" litres отзывы
```

#### 1.2. Прямой поиск
WebFetch `https://www.litres.ru/search/?q={Книга}+{Автор}` → спарсить

#### 1.3. URL-паттерны
- Книга: `https://www.litres.ru/{author-slug}/{book-slug}/`
- Отзывы: `https://www.litres.ru/{author-slug}/{book-slug}/otzyvy/`
- (иногда) `https://www.litres.ru/pages/biblio_book/?item={id}`

### Шаг 2. Спарсить основную страницу

```html
<!-- Рейтинг -->
<div class="rating-value">{4.8}</div>
<div class="rating-count">{234}</div>

<!-- 5 параметров (Литрес оценивает) -->
<div class="rating-aspects">
  <div class="aspect" data-aspect="plot">{4.5}</div>
  <div class="aspect" data-aspect="style">{4.7}</div>
  <div class="aspect" data-aspect="cover">{4.6}</div>
  <div class="aspect" data-aspect="printing">{4.4}</div>
  <div class="aspect" data-aspect="idea">{4.8}</div>
</div>
```

### Шаг 3. Спарсить отзывы (только от купивших)

Литрес показывает **только verified-покупки** в отзывах:
```html
<div class="review" data-purchased="true">
  <div class="review-author">{Имя}</div>
  <div class="review-purchased-badge">✓ Купил</div>
  <div class="review-rating">{5}</div>
  <div class="review-date">{2024-12-15}</div>
  <div class="review-text">{Полный текст}</div>
  <div class="review-likes">{45}</div>
  <div class="review-comments">{3}</div>
</div>
```

### Шаг 4. Структурировать

```json
{
  "source": "litres",
  "source_url": "https://www.litres.ru/.../otzyvy/",
  "fetched_at": "2026-06-10T14:45:00",
  "book": {
    "title": "Трансерфинг реальности",
    "author": "Вадим Зеланд",
    "litres_url": "...",
    "cover": "...",
    "isbn": "...",
    "year": 2004,
    "publisher": "VSE"
  },
  "rating": {
    "average": 4.8,
    "count": 234,
    "aspects": {
      "plot": 4.5,
      "style": 4.7,
      "cover": 4.6,
      "printing": 4.4,
      "idea": 4.8
    },
    "distribution": {
      "5": 180,
      "4": 35,
      "3": 12,
      "2": 5,
      "1": 2
    }
  },
  "reviews": [
    {
      "id": "...",
      "author": "Анна",
      "rating": 5,
      "date": "2024-12-15",
      "text": "...",
      "purchased": true,
      "verified": true,  // всегда true на litres
      "likes": 45,
      "comments": 3,
      "url": "..."
    }
  ],
  "weight": "high",  // покупатели весят больше
  "notes": "Все отзывы от покупателей (verified)"
}
```

### Шаг 5. Особенности Литрес

- **Verified by default** — все отзывы от купивших
- **5-параметровая оценка** (сюжет/стиль/обложка/печать/идея)
- **Меньше отзывов**, чем на LiveLib (Литрес — магазин, а не соцсеть)
- **Длиннее тексты** (покупатели пишут осмысленнее)
- **Вес в 1.5x** при сведении (verified > unverified)

### Шаг 6. AI-суммаризация (опционально)

После сбора:
- Pros/cons из verified-отзывов
- Сравнение с LiveLib (где отзывы могут быть менее вдумчивыми)
- Топ-цитаты

## Скрипт-парсер
`scripts/parse_litres.py` — requests + BeautifulSoup + lxml

## Rate limit
- **1 запрос в 2-3 сек**
- **User-Agent обязательно** (Литрес агрессивный к ботам)
- **До 100 отзывов за сессию**

## Анти-бан
- Ротация User-Agent
- Случайные задержки 2-5 сек
- Использование cookies при необходимости
- Прокси при массовом парсинге

## Этические ограничения
- Не обходим авторизацию
- Уважаем robots.txt
- Не публикуем отзывы с личными данными других людей
- Указываем источник при цитировании

## Пример вызова
```
/reviews litres "Трансерфинг реальности"
/reviews litres "Сила настоящего момента" "Экхарт Толле"
```
