# Ozon парсер — отзывы с маркетплейса

## Назначение
Сбор отзывов с ozon.ru — много отзывов, но много «купленных». Используем как дополнительный источник.

## Вход
- **Название книги**
- (опционально) URL на ozon.ru

## Алгоритм

### Шаг 1. Найти страницу

WebSearch: `site:ozon.ru "{Книга}" "{Автор}"` или прямой URL `https://www.ozon.ru/search/?text={Книга}+{Автор}`

URL-паттерны:
- Книга: `https://www.ozon.ru/product/{slug}/{id}/`
- Отзывы: `https://www.ozon.ru/product/{slug}/{id}/reviews/`

### Шаг 2. Спарсить страницу

```html
<div class="product-rating">
  <div class="rating-value">{4.5}</div>
  <div class="rating-count">{166}</div>
</div>

<div class="review" data-verified="true">
  <div class="review-author">{Имя}</div>
  <div class="review-rating">{5}</div>
  <div class="review-date">{2024-12-15}</div>
  <div class="review-text">{...}</div>
  <div class="review-pros">{pros}</div>
  <div class="review-cons">{cons}</div>
  <div class="review-verified-badge">✓ Покупка подтверждена</div>
</div>
```

### Шаг 3. Фильтрация (важно для Ozon!)

#### 3.1. Детекция «купленных» отзывов

Паттерны спама/накрутки:
- ❌ Только 5 звёзд без текста
- ❌ Текст < 30 символов
- ❌ Шаблонные фразы («Отличный товар! Рекомендую!»)
- ❌ Массово от 1-3 аккаунтов
- ❌ Дата публикации = дата доставки
- ❌ Аккаунт создан в день отзыва

**Фильтр:** оставлять только verified-покупки с текстом > 50 символов

#### 3.2. Дедуп по тексту
- Найти похожие отзывы (fuzzy match)
- Оставить 1, пометить как `duplicates: N`

### Шаг 4. Структурировать

```json
{
  "source": "ozon",
  "source_url": "https://www.ozon.ru/product/.../reviews/",
  "fetched_at": "2026-06-10T14:45:00",
  "book": {
    "title": "Трансерфинг реальности",
    "author": "Вадим Зеланд",
    "ozon_url": "...",
    "price": 850
  },
  "rating": {
    "average": 4.5,
    "count_raw": 166,
    "count_filtered": 120,
    "filtered_out": 46,
    "filter_reasons": {
      "no_text": 30,
      "template": 10,
      "duplicate": 6
    }
  },
  "reviews": [
    {
      "id": "...",
      "author": "...",
      "rating": 5,
      "date": "2024-12-15",
      "text": "...",
      "pros": "...",
      "cons": "...",
      "verified": true,
      "purchased": true,
      "weight": "medium",  // ниже litres
      "spam_score": 0.05
    }
  ],
  "weight": "medium",
  "notes": "Отфильтровано 46 спам-отзывов"
}
```

### Шаг 5. Особенности Ozon

- **Много накруток** — фильтруем обязательно
- **Verified badge** — показывает покупку
- **Большой объём** — 100-1000+ отзывов на популярные книги
- **Вес в 0.7x** (средний — спам снижает доверие)
- **Полезен для трендов** — динамика по времени

## Скрипт-парсер
`scripts/parse_ozon.py` — requests + BeautifulSoup + эвристики антиспама

## Rate limit
- **1 запрос в 3-5 сек** (Ozon более строгий)
- **Случайные задержки** 3-7 сек
- **User-Agent + Accept-Language обязательно**
- **До 50 отзывов за сессию**

## Анти-бан
- Ротация прокси
- Имитация реального поведения (запросы к смежным страницам)
- Cookies + Referer
- Обход anti-bot через cloudscraper или undetected-chromedriver (крайний случай)

## Этические ограничения
- **Не покупаем отзывы** (мы их собираем, не накручиваем)
- **Уважаем robots.txt**
- **Не публикуем отзывы с ПДн других людей** (email, телефон)

## Пример вызова
```
/reviews ozon "Трансерфинг реальности"
/reviews ozon "Атомные привычки" "Джеймс Клир"
```
