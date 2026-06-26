# OG / VK / Twitter мета-теги (превью в соц.сетях)

## Зачем
Когда ссылку на страницу шарят в VK, Telegram, Twitter, Slack, мессенджеры — парсеры берут `og:*` мета-теги и формируют превью:
- **Заголовок** (обычно og:title)
- **Описание** (og:description)
- **Картинка** (og:image) — 1200×630 px
- **Домен** (og:site_name)
- **Тип контента** (og:type)

Без OG-разметки:
- Превью формируется автоматически, криво
- Картинка случайная или вообще без
- Описание обрезано
- Нет брендинга

С OG-разметкой:
- Чистое, брендированное превью
- Контролируешь, что видят люди
- CTR перехода выше

## Шаблон: универсальный (для всех соц.сетей)

```html
<!-- Open Graph (Facebook, VK, LinkedIn, Telegram) -->
<meta property="og:type" content="article">
<meta property="og:site_name" content="Лаборатория желаний">
<meta property="og:locale" content="ru_RU">
<meta property="og:url" content="{canonical URL}">
<meta property="og:title" content="{title 60-90 символов}">
<meta property="og:description" content="{description до 200 символов}">
<meta property="og:image" content="{URL картинки 1200x630}">
<meta property="og:image:width" content="1200">
<meta property="og:image:height" content="630">
<meta property="og:image:alt" content="{alt = og:title}">
<meta property="og:determiner" content="auto">
<meta property="og:updated_time" content="{ISO 8601 datetime}">

<!-- Статья (для блога) -->
<meta property="article:published_time" content="{ISO 8601}">
<meta property="article:modified_time" content="{ISO 8601}">
<meta property="article:author" content="{имя автора}">
<meta property="article:section" content="{категория}">
<meta property="article:tag" content="{тег1}">
<meta property="article:tag" content="{тег2}">

<!-- Книга (для конспекта) -->
<meta property="book:author" content="{автор}">
<meta property="book:isbn" content="{ISBN}">
<meta property="book:release_date" content="{ГГГГ-ММ-ДД}">
<meta property="book:tag" content="{жанр}">

<!-- VK-specific -->
<meta property="vk:image" content="{URL, обычно = og:image}">
<meta name="vk:card" content="article">

<!-- Twitter Card -->
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:site" content="@pulabru">
<meta name="twitter:creator" content="@{автор}">
<meta name="twitter:title" content="{title до 70 символов}">
<meta name="twitter:description" content="{description до 200 символов}">
<meta name="twitter:image" content="{URL = og:image}">
<meta name="twitter:image:alt" content="{alt}">
<meta name="twitter:label1" content="Автор">
<meta name="twitter:data1" content="{имя}">
<meta name="twitter:label2" content="Время чтения">
<meta name="twitter:data2" content="{N} мин">
```

## Различия по платформам

| Платформа | Что парсит первым | Особенности |
|-----------|-------------------|-------------|
| **VK** | `og:title`, `og:description`, `og:image` | Дополнительно `vk:image` (если есть, перебивает og:image). Картинка режется до 537×240 в превью чата. |
| **Telegram** | `og:title`, `og:description`, `og:image` | Instant View если есть article-разметка. Картинка 1200×630 OK. |
| **Twitter** | `twitter:card` → если `summary_large_image`, то `twitter:image` 2:1 | Картинка обязательна. |
| **Facebook** | `og:*` | Картинка 1200×630, минимум 600×315. |
| **LinkedIn** | `og:*` | Только summary, без больших картинок. |
| **Slack** | `og:*` | Показывает превью в unfurl. |
| **WhatsApp** | `og:*` | Только маленькая картинка. |
| **Discord** | `og:*` | Полноценное превью. |

## Под каждый тип страницы

### Страница книги
```html
<meta property="og:type" content="book">
<meta property="og:title" content="{Название} — {Автор}: конспект и воркбук | Лаборатория желаний">
<meta property="og:description" content="Краткий конспект «{Название}» {Автор}. Ключевые идеи, цитаты, практические методы. Читайте бесплатно онлайн.">
<meta property="og:image" content="https://lab.com/img/og/{slug}.jpg">
<meta property="book:author" content="{Автор}">
<meta property="book:isbn" content="{ISBN}">
<meta property="book:release_date" content="{ГГГГ}">
```

### Статья блога
```html
<meta property="og:type" content="article">
<meta property="og:title" content="{Заголовок статьи} | Лаборатория желаний">
<meta property="og:description" content="{первые 1-2 предложения статьи}">
<meta property="og:image" content="https://lab.com/img/og/blog/{slug}.jpg">
<meta property="article:published_time" content="{ISO 8601}">
<meta property="article:modified_time" content="{ISO 8601}">
<meta property="article:author" content="{Автор}">
<meta property="article:section" content="Саморазвитие">
```

### Главная
```html
<meta property="og:type" content="website">
<meta property="og:title" content="Лаборатория желаний — конспекты книг по саморазвитию">
<meta property="og:description" content="Конспекты и воркбуки лучших книг по саморазвитию, исполнению желаний, психологии. Читайте кратко, применяйте на практике.">
<meta property="og:image" content="https://lab.com/img/og/home.jpg">
```

### Лендинг эксперта
```html
<meta property="og:type" content="profile">
<meta property="og:title" content="{Имя} — {специализация} | Лаборатория желаний">
<meta property="og:description" content="{Имя} помогает {что делает}. Запишитесь на {услугу}: 30 минут, бесплатно.">
<meta property="og:image" content="https://lab.com/img/og/expert-{slug}.jpg">
<meta property="profile:first_name" content="{Имя}">
<meta property="profile:last_name" content="{Фамилия}">
```

## Требования к OG-картинке

| Параметр | Значение |
|----------|----------|
| Размер | 1200×630 px (стандарт), 1080×1080 (Instagram/TG квадрат), 1080×1920 (сторис) |
| Формат | JPG (лучше сжатие) или PNG (если есть прозрачность) |
| Размер файла | < 200 КБ (лучше < 100 КБ) |
| Формат 2026 | AVIF (если поддерживается), WebP (фолбэк), JPG (универсально) |
| Безопасная зона | Весь текст в центре 1100×570, не ближе 50 px от краёв |
| Шрифты | Используй универсальные (Roboto, PT Sans, Inter) |
| Alt | Должен быть; обычно = og:title |

## Генерация OG-картинки (промпт для дизайнера или DALL-E/Midjourney)
```
Создай превью для соцсетей 1200×630 px в стиле "Лаборатория желаний":
- Фон: тёплый градиент (фиолетовый → розовый)
- Заголовок: "{title}" крупно, по центру
- Подзаголовок: "{subtitle}" мелко
- Логотип "Лаборатория желаний" в правом нижнем углу
- Стиль: минимализм, читаемо, без водяных знаков
```

## Валидация
1. **Facebook Sharing Debugger:** https://developers.facebook.com/tools/debug/
2. **Twitter Card Validator:** https://cards-dev.twitter.com/validator
3. **VK:** https://vk.com/dev/share_details
4. **OpenGraph.xyz:** https://www.opengraph.xyz/ — показывает превью для всех платформ

## Чек-лист внедрения
- [ ] og:type под тип страницы
- [ ] og:title (60-90 символов)
- [ ] og:description (до 200 символов)
- [ ] og:image 1200×630, < 200 КБ
- [ ] og:image:alt
- [ ] og:url = canonical
- [ ] og:locale = ru_RU
- [ ] og:site_name = Лаборатория желаний
- [ ] twitter:card = summary_large_image
- [ ] twitter:title/description/image
- [ ] article:* или book:* (по типу)
- [ ] Валидация через OpenGraph.xyz

## Пример вызова
```
/seo og https://lab.com/library/transerfing
/seo og
# (вставить HTML)
/seo og
Сгенерируй OG-разметку для будущей страницы книги «{название}»
```
