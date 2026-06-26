# LiveLib парсер — самый ценный источник отзывов в рунете

## Назначение
Сбор отзывов с LiveLib: рейтинг, pros/cons, распределение оценок, цитаты.

## Вход
- **Название книги** (с автором для точности)
- (опционально) URL книги на LiveLib (если известен)

## Алгоритм

### Шаг 1. Найти страницу книги

#### 1.1. WebSearch
```
site:livelib.ru "{Книга}" "{Автор}"
"{Книга}" "{Автор}" livelib
```

#### 1.2. Или прямой поиск
WebFetch `https://www.livelib.ru/find?q={Книга}+{Автор}` → парсить ссылки

#### 1.3. Паттерн URL
- Книга: `https://www.livelib.ru/book/{id}` или `https://www.livelib.ru/book/{slug}`
- Отзывы: `https://www.livelib.ru/book/{id}/reviews`

### Шаг 2. Спарсить основную страницу

WebFetch → HTML → Grep:

```html
<!-- Рейтинг -->
<span class="rating-value">{4.7}</span>
<span class="rating-count">{1247}</span>

<!-- Обложка -->
<img class="book-cover" src="...">

<!-- Описание -->
<div class="book-description">{...}</div>

<!-- Распределение -->
<div class="rating-distribution">
  <div class="rating-5">{850}</div>
  <div class="rating-4">{250}</div>
  ...
</div>
```

### Шаг 3. Спарсить отзывы

WebFetch `/reviews` (первая страница) + пагинация `/reviews?page={N}`

```html
<div class="review-item">
  <div class="review-author">{Имя}</div>
  <div class="review-rating">{5}</div>
  <div class="review-date">{2024-12-15}</div>
  <div class="review-text">{...}</div>
  <div class="review-pros">
    <span class="pros-label">Достоинства</span>
    {Текст pros}
  </div>
  <div class="review-cons">
    <span class="cons-label">Недостатки</span>
    {Текст cons}
  </div>
</div>
```

### Шаг 4. Структурировать

```json
{
  "source": "livelib",
  "source_url": "https://www.livelib.ru/book/...",
  "fetched_at": "2026-06-10T14:45:00",
  "book": {
    "title": "Трансерфинг реальности",
    "author": "Вадим Зеланд",
    "ll_url": "https://www.livelib.ru/book/...",
    "cover": "https://...",
    "year": 2004
  },
  "rating": {
    "average": 4.7,
    "count": 1247,
    "distribution": {
      "5": 850,
      "4": 250,
      "3": 100,
      "2": 30,
      "1": 17
    }
  },
  "reviews": [
    {
      "id": "...",
      "author": "Иван Петров",
      "author_url": "https://www.livelib.ru/reader/...",
      "rating": 5,
      "date": "2024-12-15",
      "title": "Изменил мышление",
      "text": "Полный текст отзыва...",
      "pros": "Практические техники, простой язык",
      "cons": "Нет научной базы",
      "likes": 245,
      "url": "https://www.livelib.ru/review/...",
      "is_recommended": true
    }
  ],
  "stats": {
    "with_text": 800,
    "with_pros_cons": 600,
    "average_length": 850
  }
}
```

### Шаг 5. Скрипт-парсер (опционально)

См. `scripts/parse_livelib.py` — автоматизация на requests + BeautifulSoup.

Преимущества скрипта:
- Скорость в 10-50 раз быстрее WebFetch
- Можно собрать ВСЕ отзывы (с пагинацией)
- Можно добавить в пайплайн WL

Ограничения:
- Rate limit: 1 запрос в 2-3 сек
- LiveLib может менять HTML-структуру (ломает парсер)
- Часть контента требует авторизации

### Шаг 6. AI-суммаризация (опционально)

После сбора запусти `/reviews summarize`:
- Топ-5 pros по частотности
- Топ-5 cons по частотности
- Средняя длина отзыва
- Тон (позитивный/негативный/нейтральный)
- Аномалии (накрутки, спам)

## Rate limit
- **1 запрос в 2-3 секунды** (с User-Agent)
- **Не более 50 отзывов за сессию** (иначе IP-бан)
- **Кешировать** результаты (не парсить одно и то же)

## Анти-бан
- User-Agent реального браузера
- Cookies (если нужны для отзывов)
- Прокси (если парсим много)

## Этические ограничения
- **Не выдаём себя за другого** (без авторизации)
- **Уважаем robots.txt** LiveLib
- **Не копируем отзывы** с указанием чужого авторства (только цитируем с источником)
- **YMYL**: для психологии/здоровья предупреждаем «субъективное мнение»

## Пример вызова
```
/reviews livelib "Трансерфинг реальности"
/reviews livelib "Сила настоящего момента" "Экхарт Толле"
/reviews livelib "Атомные привычки" "Джеймс Клир"
```
