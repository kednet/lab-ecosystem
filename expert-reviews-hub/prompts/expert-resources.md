# Каталог ресурсов эксперта

## Назначение
Собрать полный каталог ресурсов эксперта: книги, курсы, видео, подкасты, статьи, сайты.

## Вход
- **Имя эксперта**
- (опционально) фильтр по типу ресурса (только книги / только видео)

## Что ищем (типы ресурсов)

| Тип | Иконка | Источники |
|-----|--------|-----------|
| 📚 Книги | ISBN, обложка, год, издательство | Ozon, Литрес, Author.Today, Ridero |
| 🎓 Курсы | Платформа, длительность, цена | Skillbox, Нетология, Udemy, свои |
| 🎥 Видео | YouTube, VK Video, RuTube | YouTube API, WebSearch |
| 🎙 Подкасты | Apple Podcasts, Spotify, Mave | Apple Podcasts, Spotify |
| 📝 Статьи | СМИ, блоги, научные | Google Scholar, eLibrary |
| 🌐 Сайты | Официальный, школа, метод | WebSearch, Whois |

## Алгоритм

### Шаг 1. WebSearch по типу ресурса

#### 1.1. Книги
```
"{Имя}" книга
"{Имя}" автор книги
"{Имя}" ISBN
"{Имя}" издание
"{Имя}" "{Издательство}"  # VSE, AST, Eksmo, Mann-Ivanov
```

Парсим:
- Ozon: `https://www.ozon.ru/search/?text={Имя}`
- Литрес: `https://www.litres.ru/search/?q={Имя}`
- Author.Today: `https://author.today/search?q={Имя}`
- Google Books: `https://www.google.com/search?q={Имя}+book+isbn`

#### 1.2. Курсы
```
"{Имя}" курс
"{Имя}" обучение
"{Имя}" тренинг
"{Имя}" "{Платформа}"  # Skillbox, Нетология, Udemy
"{Имя}" школа
```

#### 1.3. Видео
```
"{Имя}" youtube
"{Имя}" видео
"{Имя}" лекция
"{Имя}" "{Канал}"  # если есть
```

YouTube: `https://www.youtube.com/results?search_query={Имя}`

#### 1.4. Подкасты
```
"{Имя}" подкаст
"{Имя}" podcast
"{Имя}" выпуск
"{Имя}" "{Шоу}"
```

Apple Podcasts: `https://podcasts.apple.com/search?term={Имя}`

#### 1.5. Статьи
```
"{Имя}" статья
"{Имя}" публикация
"{Имя}" исследование
"{Имя}" "{Журнал}"
```

Google Scholar: `https://scholar.google.com/scholar?q={Имя}`

#### 1.6. Сайты
```
"{Имя}" официальный сайт
"{Имя}" "{Метод}"
"{Имя}" "{Школа}"
```

### Шаг 2. Для каждой книги — обогащение

Найденную книгу дополняй:
- **ISBN** — по Google Books, Ozon
- **Обложка** — URL (с проверкой лицензии)
- **Год** — дата публикации
- **Издательство** — официальный сайт
- **Страниц** — кол-во
- **Цена** — Ozon, Литрес (текущая)
- **Отзывы** — ссылка на LiveLib (если есть)
- **Краткое описание** — первые 2-3 предложения

### Шаг 3. Для видео — метаданные

YouTube видео:
- Длительность
- Просмотры
- Дата публикации
- Канал
- Embed URL
- Описание (если есть)
- Субтитры (если доступны)

### Шаг 4. Bundle

```yaml
# resources/{slug}.json
expert: "Вадим Зеланд"
total_resources: 23
categories:
  books: 5
  courses: 2
  videos: 12
  podcasts: 1
  articles: 2
  sites: 1

books:
  - title: "Трансерфинг реальности"
    year: 2004
    isbn: "978-5-9573-2563-4"
    publisher: "VSE"
    pages: 320
    cover: "https://..."
    description: "..."
    price_rub: 850
    buy_links:
      - store: "Ozon"
        url: "https://ozon.ru/..."
        price: 850
      - store: "Литрес"
        url: "https://litres.ru/..."
        price: 599
    reviews_url: "https://livelib.ru/book/..."
    in_wl: true  # уже в WishLibrarian
    wl_slug: "transerfing-realnosti"

courses:
  - title: "Трансерфинг за 30 дней"
    platform: "Skillbox"
    url: "https://skillbox.ru/..."
    price_rub: 25000
    duration_hours: 24
    students: 1200
    rating: 4.6

videos:
  - title: "Вадим Зеланд: интервью о методе"
    platform: "YouTube"
    url: "https://youtube.com/watch?v=..."
    channel: "..."
    duration: "45:20"
    views: 1200000
    date: "2024-12-15"
    embed_url: "https://youtube.com/embed/..."
    has_subtitles: true
    description_preview: "..."

podcasts:
  - title: "Трансерфинг в реальной жизни"
    show: "Подкаст саморазвития"
    platform: "Apple Podcasts"
    url: "..."
    date: "2025-06-10"
    duration: "1:12:30"

articles:
  - title: "..."
    journal: "..."
    year: 2023
    url: "..."
    citations: 5

sites:
  - type: "official"
    url: "https://..."
    description: "Официальный сайт"
  - type: "method"
    url: "https://..."
    description: "Сайт метода/школы"

generated_at: "2026-06-10T14:45:00"
skill_version: "1.0"
```

### Шаг 5. Markdown-отчёт

`resources/{slug}.md`:

```markdown
# Ресурсы: {Имя}

**Всего:** {N} ресурсов в {M} категориях

## 📚 Книги ({N})

### Трансерфинг реальности (2004)
- ISBN: 978-5-9573-2563-4
- Издательство: VSE, 320 стр.
- 💰 Ozon: 850₽ | Литрес: 599₽
- 🔗 Купить: [Ozon](url) | [Литрес](url)
- 💬 Отзывы: [LiveLib](url)
- ✅ В нашей библиотеке: [конспект](/library/transerfing-realnosti/)

### Шелест утренних звёзд (2005)
- ...

## 🎓 Курсы ({N})

### Трансерфинг за 30 дней
- Платформа: Skillbox
- 💰 25 000₽
- ⏱ 24 часа
- 👥 1 200 студентов
- ⭐ 4.6/5
- 🔗 [Записаться](url)

## 📺 Видео ({N})

| Название | Длительность | Просмотры | Дата | Канал |
|----------|--------------|-----------|------|-------|
| Вадим Зеланд: интервью | 45:20 | 1.2M | 2024-12-15 | ... |
| ... | | | | |

## 🎙 Подкасты ({N})

### Трансерфинг в реальной жизни
- Шоу: Подкаст саморазвития
- ⏱ 1:12:30
- 📅 2025-06-10
- 🔗 [Слушать](url)

## 📝 Статьи ({N})

- *{Название}* — {Журнал}, {год} | [Читать](url) ({citations} цитирований)

## 🌐 Сайты ({N})

- 🌐 [Официальный сайт](url)
- 🌐 [Школа метода](url)
```

## Использование
- Для карточки эксперта на лендинге WishCoach
- Для страницы книг (ссылки на автора)
- Для email-рассылки (топ-3 книги + курс)
- Для партнёрских программ (через buy_links)

## Пример вызова
```
/expert resources "Вадим Зеланд"
/expert resources "Борис Ананьев" --type books
/expert resources "Марк Розин" --type courses
```
