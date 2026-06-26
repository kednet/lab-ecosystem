# Schema.org генератор (JSON-LD)

## Назначение
Генерация структурированной разметки JSON-LD под разные типы страниц: Book, Article, FAQPage, Person, Organization, BreadcrumbList, Review, WebSite, Service/Product.

Зачем: **rich snippets** (расширенные сниппеты) дают:
- Звёздочки рейтинга
- Превью с картинкой
- FAQ прямо в выдаче
- Хлебные крошки
- Author в выдаче

## Базовый шаблон

```html
<script type="application/ld+json">
{
  "@context": "https://schema.org",
  "@type": "...",
  ...
}
</script>
```

**Правила:**
- Валидируй через `scripts/schema-validate.py` или Google Rich Results Test
- Один блок JSON-LD на тип; несколько типов — оборачивай в `@graph`
- Свежие словари: https://schema.org/

## Типы и шаблоны

### 1. Book (для конспекта книги)

```json
{
  "@context": "https://schema.org",
  "@type": "Book",
  "name": "{Название}",
  "alternateName": "{другое название}",
  "bookFormat": "EBook",
  "inLanguage": "ru",
  "isbn": "{ISBN если есть}",
  "author": {
    "@type": "Person",
    "name": "{Автор}"
  },
  "publisher": {
    "@type": "Organization",
    "name": "{Издательство}"
  },
  "datePublished": "{ГГГГ-ММ-ДД}",
  "image": "{URL обложки}",
  "description": "{краткое описание до 200 символов}",
  "genre": ["{жанр1}", "{жанр2}"],
  "numberOfPages": "{N}",
  "aggregateRating": {
    "@type": "AggregateRating",
    "ratingValue": "{4.5}",
    "ratingCount": "{N}",
    "bestRating": "5",
    "worstRating": "1"
  },
  "review": [
    {
      "@type": "Review",
      "author": {"@type": "Person", "name": "{Читатель}"},
      "datePublished": "{ГГГГ-ММ-ДД}",
      "reviewBody": "{текст отзыва}",
      "reviewRating": {"@type": "Rating", "ratingValue": "5"}
    }
  ]
}
```

### 2. Article (для блога)

```json
{
  "@context": "https://schema.org",
  "@type": "Article",
  "headline": "{title до 110 символов}",
  "description": "{description}",
  "image": ["{URL картинки 1200x630}"],
  "datePublished": "{ГГГГ-ММ-ДДTЧЧ:ММ:СС+03:00}",
  "dateModified": "{ГГГГ-ММ-ДДTЧЧ:ММ:СС+03:00}",
  "author": {
    "@type": "Person",
    "name": "{Автор}",
    "url": "{URL профиля}",
    "sameAs": ["{VK}", "{TG}", "{личный сайт}"]
  },
  "publisher": {
    "@type": "Organization",
    "name": "Лаборатория желаний",
    "logo": {
      "@type": "ImageObject",
      "url": "{URL лого}",
      "width": 600,
      "height": 60
    }
  },
  "mainEntityOfPage": {
    "@type": "WebPage",
    "@id": "{canonical URL}"
  },
  "articleSection": "{категория}",
  "keywords": "{теги через запятую}",
  "inLanguage": "ru-RU"
}
```

### 3. FAQPage (для FAQ-блока)

```json
{
  "@context": "https://schema.org",
  "@type": "FAQPage",
  "mainEntity": [
    {
      "@type": "Question",
      "name": "{вопрос 1}",
      "acceptedAnswer": {
        "@type": "Answer",
        "text": "{ответ 1, до 300 символов}"
      }
    },
    {
      "@type": "Question",
      "name": "{вопрос 2}",
      "acceptedAnswer": {
        "@type": "Answer",
        "text": "{ответ 2}"
      }
    }
  ]
}
```

**Правила FAQ:**
- Минимум 3 вопроса
- Ответы короткие, по существу (40-80 слов)
- Тот же текст вопросов/ответов должен быть видимым на странице
- Google берёт ответ из блока JSON-LD

### 4. Person (для страницы автора/эксперта)

```json
{
  "@context": "https://schema.org",
  "@type": "Person",
  "name": "{Имя}",
  "alternateName": "{псевдоним}",
  "description": "{биография}",
  "image": "{URL фото}",
  "jobTitle": "{должность}",
  "worksFor": {
    "@type": "Organization",
    "name": "Лаборатория желаний"
  },
  "url": "{URL профиля}",
  "sameAs": [
    "{URL VK}",
    "{URL Telegram}",
    "{URL YouTube}",
    "{URL личного сайта}"
  ],
  "knowsAbout": [
    "{навык 1}",
    "{навык 2}"
  ],
  "alumniOf": [
    {"@type": "EducationalOrganization", "name": "{ВУЗ}"}
  ]
}
```

### 5. Organization (для главной)

```json
{
  "@context": "https://schema.org",
  "@type": "Organization",
  "@id": "{URL главной}#organization",
  "name": "Лаборатория желаний",
  "alternateName": "pulabru",
  "url": "https://lab.com",
  "logo": {
    "@type": "ImageObject",
    "url": "https://lab.com/logo.png",
    "width": 600,
    "height": 60
  },
  "description": "{описание}",
  "foundingDate": "{ГГГГ-ММ-ДД}",
  "founder": {
    "@type": "Person",
    "name": "{Основатель}"
  },
  "contactPoint": {
    "@type": "ContactPoint",
    "telephone": "{+7...}",
    "contactType": "customer service",
    "email": "{email}",
    "availableLanguage": ["Russian"]
  },
  "address": {
    "@type": "PostalAddress",
    "streetAddress": "{улица}",
    "addressLocality": "{город}",
    "postalCode": "{индекс}",
    "addressCountry": "RU"
  },
  "sameAs": [
    "https://vk.com/pulabru",
    "https://t.me/pulabru"
  ]
}
```

### 6. BreadcrumbList (хлебные крошки)

```json
{
  "@context": "https://schema.org",
  "@type": "BreadcrumbList",
  "itemListElement": [
    {
      "@type": "ListItem",
      "position": 1,
      "name": "Главная",
      "item": "https://lab.com/"
    },
    {
      "@type": "ListItem",
      "position": 2,
      "name": "Библиотека",
      "item": "https://lab.com/library/"
    },
    {
      "@type": "ListItem",
      "position": 3,
      "name": "{Название книги}"
    }
  ]
}
```

### 7. Review (отзыв)

```json
{
  "@context": "https://schema.org",
  "@type": "Review",
  "author": {
    "@type": "Person",
    "name": "{Имя читателя}"
  },
  "datePublished": "{ГГГГ-ММ-ДД}",
  "reviewBody": "{текст отзыва}",
  "reviewRating": {
    "@type": "Rating",
    "ratingValue": "{1-5}",
    "bestRating": "5",
    "worstRating": "1"
  },
  "itemReviewed": {
    "@type": "Book",
    "name": "{Название}"
  }
}
```

### 8. WebSite (с SearchAction для главной)

```json
{
  "@context": "https://schema.org",
  "@type": "WebSite",
  "@id": "https://lab.com/#website",
  "url": "https://lab.com/",
  "name": "Лаборатория желаний",
  "description": "...",
  "inLanguage": "ru-RU",
  "publisher": {"@id": "https://lab.com/#organization"},
  "potentialAction": {
    "@type": "SearchAction",
    "target": {
      "@type": "EntryPoint",
      "urlTemplate": "https://lab.com/search?q={search_term_string}"
    },
    "query-input": "required name=search_term_string"
  }
}
```

### 9. Service (для лендинга услуги/коуча)

```json
{
  "@context": "https://schema.org",
  "@type": "Service",
  "serviceType": "{тип услуги}",
  "name": "{название}",
  "description": "{описание}",
  "provider": {
    "@type": "Person",
    "name": "{Имя}"
  },
  "areaServed": {
    "@type": "Country",
    "name": "Россия"
  },
  "offers": {
    "@type": "Offer",
    "price": "{цена}",
    "priceCurrency": "RUB",
    "availability": "https://schema.org/InStock",
    "url": "{URL покупки}"
  },
  "aggregateRating": {
    "@type": "AggregateRating",
    "ratingValue": "4.9",
    "ratingCount": "47"
  }
}
```

## Композиция: несколько типов на одной странице

Используй `@graph`:

```json
{
  "@context": "https://schema.org",
  "@graph": [
    { /* Book */ },
    { /* BreadcrumbList */ },
    { /* FAQPage */ },
    { /* Review 1 */ },
    { /* Review 2 */ }
  ]
}
```

**Рекомендации по композиции для страницы книги:**
1. Book (обязательно)
2. BreadcrumbList
3. FAQPage (если есть FAQ)
4. AggregateRating + 1-3 Review (если есть отзывы)

**Рекомендации для блога:**
1. Article
2. BreadcrumbList
3. Person (автор) — если статья авторская
4. FAQPage (если есть FAQ)

## Валидация

1. Локально: `python scripts/schema-validate.py {html-файл}`
2. Онлайн: https://search.google.com/test/rich-results
3. Онлайн: https://validator.schema.org/

## Пример вызова
```
/seo schema Book
# → выдаст шаблон + попросит заполнить поля
/seo schema https://lab.com/library/transerfing
# → загрузит HTML, определит тип, сгенерирует JSON-LD
/seo schema
# (вставить HTML)
/seo schema FAQ
# → для блока FAQ
```

См. `templates/schema/*.json` — готовые файлы, копируй и заполняй.
