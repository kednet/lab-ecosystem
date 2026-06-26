# Сбор СВОИХ отзывов (с лендинга / сайта / Telegram-бота)

## Назначение
Сбор отзывов, оставленных напрямую через наш лендинг, форму на сайте, Telegram-бота, VK-сообщество. **Самый ценный источник** — это наши клиенты/читатели, верифицированы по факту.

## Вход
- **URL** (лендинг, сайт, страница отзывов)
- (опционально) Telegram-бот, VK-группа, форма

## Что собираем

### 1. Отзывы с лендинга/сайта

#### 1.1. Где могут быть
- `/reviews`, `/otzyvy`, `/testimonials`
- Блок на главной («Отзывы клиентов»)
- В карточке книги/курса (блок «Отзывы»)
- Schema.org `Review` разметка (найти через `Grep`)
- Микроразметка hReview

#### 1.2. Алгоритм
1. **WebFetch URL** → HTML
2. **Grep по HTML**:
   - `class="review"` или `class="testimonial"`
   - `itemtype="https://schema.org/Review"`
   - `itemprop="review"`
   - JSON-LD блок с `Review`
3. **Извлечь**:
   - Имя автора
   - Текст отзыва
   - Дата
   - Рейтинг (если есть)
   - Контекст (книга, курс, услуга)

#### 1.3. Структура
```json
{
  "id": "own_1",
  "author": "Анна К.",
  "rating": 5,
  "text": "Трансерфинг реальности изменил мою жизнь...",
  "date": "2026-05-15",
  "context": "Конспект «Трансерфинг реальности»",
  "url": "https://lab.com/library/transerfing#review-1",
  "source": "own",
  "verified": true,  // свой = всегда verified
  "collected_at": "2026-06-10T14:45:00",
  "metadata": {
    "book_slug": "transerfing-realnosti",
    "course_slug": null,
    "user_id": "..."  // если есть
  }
}
```

### 2. Отзывы из Telegram-бота

#### 2.1. Если есть Telegram-бот
- Бот собирает отзывы в `book.feedback` или аналогичное поле
- Парсим `bot_data/reviews.json` или `output/*/feedback.md`

#### 2.2. Структура
```json
{
  "id": "tg_review_1",
  "author": "@username",
  "user_id": 123456,
  "rating": 5,
  "text": "...",
  "date": "2026-05-15T10:30:00",
  "chat_id": -1001234567890,
  "message_id": 42,
  "context": "book:transerfing-realnosti",
  "source": "telegram_bot",
  "verified": true
}
```

### 3. Отзывы из VK-сообщества

#### 3.1. Алгоритм
1. **VK API**: `wall.get` для постов сообщества с хэштегом `#отзыв`
2. **WebFetch** `vk.com/{group}?w=wall-{id}_{post}` → парсить
3. **Только verified** — посты от подписчиков сообщества

#### 3.2. Структура
```json
{
  "id": "vk_wall_123",
  "author": "Иван Петров",
  "author_url": "https://vk.com/id...",
  "text": "...",
  "date": "2026-05-15",
  "likes": 45,
  "reposts": 5,
  "comments": 12,
  "group": "pulabru",
  "source": "vk_community",
  "verified": true,
  "is_member": true
}
```

### 4. Отзывы через Google Forms / Typeform

#### 4.1. Алгоритм
1. WebFetch URL формы → спарсить вопросы
2. **Не парсим ответы** — у нас нет доступа
3. Вместо этого — попросить пользователя выгрузить CSV

#### 4.2. Если есть CSV
- Grep по CSV → извлечь ответы
- Маппить на нашу структуру

## Формат выхода

```yaml
# reviews/{book-slug}/own.json
book: "Трансерфинг реальности"
total_own_reviews: 8
sources:
  site: 5
  telegram_bot: 2
  vk_community: 1

reviews:
  - id: "own_1"
    author: "Анна К."
    rating: 5
    text: "..."
    date: "2026-05-15"
    source: "site"
    url: "https://lab.com/library/transerfing#review-1"
    verified: true
  
  - id: "tg_review_1"
    author: "@username"
    rating: 5
    text: "..."
    date: "2026-05-15T10:30:00"
    source: "telegram_bot"
    verified: true

weight: "high"  // свои отзывы — максимальный вес
```

## Модерация

**Важно:** свои отзывы требуют модерации перед публикацией!

```yaml
# reviews/{book-slug}/own_moderation.json
pending:
  - id: "own_2"
    text: "..."
    submitted_at: "2026-06-10"
    status: "pending"  # pending | approved | rejected
    moderator_notes: ""
    
approved:
  - id: "own_1"
    approved_at: "2026-06-09"
    moderator: "admin"
    
rejected:
  - id: "own_X"
    reason: "spam"  # spam | abuse | off-topic | duplicate
    rejected_at: "2026-06-08"
```

## Интеграция с формой сбора отзывов

На лендинге можно добавить форму:
```html
<form class="review-form" method="POST" action="/api/reviews">
  <input name="book_slug" value="transerfing-realnosti">
  <input name="author" placeholder="Ваше имя">
  <select name="rating">
    <option value="5">5 ⭐</option>
    ...
  </select>
  <textarea name="text" placeholder="Ваш отзыв"></textarea>
  <input name="email" type="email">  <!-- для обратной связи -->
  <button>Отправить</button>
</form>
```

## Скрипт

`scripts/parse_own_reviews.py` — парсит все источники + сохраняет в `own.json`

## Этические ограничения
- **Не публикуем без модерации** (свои — часто спам/оскорбления)
- **Не удаляем негативные** (объективность)
- **Не показываем email/телефон** (только имя/ник)
- **Сохраняем дату** (для динамики)
- **YMYL-предупреждение** для психологии/здоровья

## Пример вызова
```
/reviews own https://lab.com/library/transerfing-realnosti
/reviews own https://lab.com/coach/mark
/reviews own --tg-bot @wishlibrarian_bot
/reviews own --vk-group pulabru
```
