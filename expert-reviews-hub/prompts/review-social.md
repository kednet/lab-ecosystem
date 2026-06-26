# Парсинг соцсетей и мессенджеров (VK, Telegram, YouTube)

## Назначение
Сбор живых обсуждений и обзоров из VK, Telegram, YouTube — без формальной оценки, зато с эмоциями.

## Вход
- **Название книги** (с автором)
- (опционально) список VK-групп / Telegram-каналов для поиска
- (опционально) VK API token (для расширенного поиска)

## Источники

### 1. VK (ВКонтакте)

#### 1.1. Где искать
- **Сообщества** книжных клубов, психологии, саморазвития
  - `vk.com/pulabru` (наше!)
  - `vk.com/livelib`
  - `vk.com/psychology_ru`
  - Тематические: «Книги по саморазвитию», «Трансерфинг», «Психология»
- **Хэштеги**: `#трансерфинг #книга #рецензия #обзоркниги`
- **Поиск постов**: `vk.com/search?c[per_page]=40&c[q]={Книга}`

#### 1.2. WebSearch для поиска
```
site:vk.com "{Книга}" отзыв
site:vk.com "{Книга}" "{Автор}"
"{Книга}" "{Автор}" вконтакте
```

#### 1.3. WebFetch → HTML
```html
<div class="post">
  <div class="post-author">{Имя}</div>
  <div class="post-date">{2024-12-15}</div>
  <div class="post-text">{Полный текст поста}</div>
  <div class="post-likes">{45}</div>
  <div class="post-reposts">{3}</div>
  <div class="post-comments">{7}</div>
  <div class="post-images">[{...}]</div>
</div>
```

#### 1.4. VK API (опционально)
- `wall.search` — поиск постов по ключевому слову
- `groups.search` — поиск тематических групп
- `video.search` — поиск видео
- Требуется: service token или user token с правами

#### 1.5. Скрипт
`scripts/parse_vk_reviews.py` — автопарсинг с rate limit

### 2. Telegram

#### 2.1. Где искать
- **Каналы** о книгах:
  - `@bookster` (если есть)
  - `@livelib_official`
  - `@psychology_channel`
  - `@popmech_ru` (популярная наука)
  - Тематические: «Трансерфинг», «Книги по саморазвитию»
- **Поиск постов** через `tgstat.ru` или `tgram.me/search`

#### 2.2. WebSearch
```
site:t.me "{Книга}" "{Автор}"
telegram "{Книга}" отзыв
```

#### 2.3. WebFetch (с ограничениями)
Telegram Web (web.telegram.org) — можно парсить публичные каналы без авторизации.

#### 2.4. Структура
```json
{
  "id": 1234,
  "channel": "@psychology_channel",
  "channel_name": "Психология и саморазвитие",
  "text": "...",
  "date": "2024-12-15T10:30:00",
  "views": 1500,
  "forwards": 25,
  "replies": 5,
  "url": "https://t.me/psychology_channel/1234"
}
```

#### 2.5. Ограничения
- Нельзя парсить приватные каналы
- Нет API для поиска сообщений
- Только WebSearch + WebFetch

### 3. YouTube

#### 3.1. Где искать
- **Обзоры книг** — каналы типа:
  - «Книги за 10 минут»
  - «Умный рецензент»
  - «Что почитать»
  - Блогерские каналы
- **Интервью с автором** (если есть)
- **Лекции эксперта** о книге

#### 3.2. WebSearch
```
"{Книга}" youtube обзор
"{Книга}" "{Автор}" youtube
youtube "{Книга}" рецензия
```

#### 3.3. WebFetch
- `https://www.youtube.com/results?search_query={Книга}+{Автор}+обзор`
- Спарсить список видео (title, channel, views, duration, date)

#### 3.4. Метаданные видео
```json
{
  "id": "dQw4w9WgXcQ",
  "title": "Обзор книги «Трансерфинг реальности»",
  "channel": "Книги за 10 минут",
  "channel_url": "...",
  "duration": "12:34",
  "views": 125000,
  "likes": 4500,
  "date": "2024-12-15",
  "url": "https://youtube.com/watch?v=...",
  "embed_url": "https://youtube.com/embed/...",
  "description": "Полное описание...",
  "has_subtitles": true,
  "transcript": "..."  // если нужна расшифровка
}
```

#### 3.5. AI-суммаризация транскрипта
Если есть субтитры/транскрипт — AI-анализ:
- Что говорят о книге
- Плюсы/минусы по мнению блогера
- Цитаты

## Формат выхода

```yaml
# reviews/{book-slug}/social.json
book: "Трансерфинг реальности"
total_mentions: 47
sources:
  vk: 18
  telegram: 5
  youtube: 24

posts:
  # VK
  - id: "vk_123"
    source: "vk"
    author: "Иван Петров"
    group: "psychology_ru"
    text: "..."
    date: "2024-12-15"
    likes: 145
    reposts: 23
    comments: 12
    url: "https://vk.com/wall..."
    tone: "positive"  # positive | neutral | negative (AI)
  
  # Telegram
  - id: "tg_456"
    source: "telegram"
    channel: "@psychology_channel"
    text: "..."
    date: "2024-12-15T10:30:00"
    views: 1500
    forwards: 25
    url: "https://t.me/..."
    tone: "positive"
  
  # YouTube
  - id: "yt_789"
    source: "youtube"
    title: "Обзор Трансерфинга за 12 минут"
    channel: "Книги за 10 минут"
    duration: "12:34"
    views: 125000
    likes: 4500
    date: "2024-12-15"
    url: "https://youtube.com/watch?v=..."
    embed_url: "https://youtube.com/embed/..."
    tone: "mixed"  # AI-анализ транскрипта
    ai_summary: "Блогер хвалит практичность, критикует отсутствие научной базы"

generated_at: "2026-06-10T14:45:00"
```

## Особенности

- **VK** — много обсуждений, можно фильтровать по группе
- **Telegram** — качественный контент, нет API
- **YouTube** — длинные обзоры, AI-анализ транскриптов

## Вес в bundle
- VK — 0.8x (живой, но без рейтинга)
- Telegram — 0.7x (хороший контент, но коротко)
- YouTube — 0.9x (развёрнуто, с AI-анализом)

## Rate limit
- VK: 3 запроса в сек (с токеном)
- Telegram Web: 1 запрос в 3 сек
- YouTube: без ограничений, но осторожно с innode

## Этические ограничения
- **Не постим от имени пользователя**
- **Не читаем личные сообщения** (только публичные посты)
- **Указываем источник** при цитировании
- **Не нарушаем ToS** платформ

## Пример вызова
```
/reviews social "Трансерфинг реальности"
/reviews social "Трансерфинг реальности" --vk-groups pulabru,psychology_ru
/reviews social "Атомные привычки" --include-tg
```
