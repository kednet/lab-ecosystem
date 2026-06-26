# Факторы ранжирования Google 2026

## Core Web Vitals (обязательно с 2021)
- **LCP** (Largest Contentful Paint): < 2.5 сек — хорошо, < 4.0 — плохо
- **INP** (Interaction to Next Paint): < 200 мс — хорошо, > 500 — плохо (заменил FID в 2024)
- **CLS** (Cumulative Layout Shift): < 0.1 — хорошо, > 0.25 — плохо

## Page Experience
- **HTTPS**
- **Mobile-friendly**
- **Без навязчивых interstitial** (баннеры, закрывающие контент)
- **Safe browsing** (без вредоносного ПО, фишинга)

## Контент
- **E-E-A-T** (Experience, Expertise, Authoritativeness, Trustworthiness) — критично для YMYL
- **Helpful Content Update** (с марта 2024) — оценивает «полезен ли контент людям»
- **Уникальность** (нет дублей, нет копипаста)
- **Глубина покрытия темы** (топикальная авторитетность)
- **Свежесть** (datePublished, dateModified)
- **Структура** (H1-H6, списки, таблицы)
- **Грамотность**
- **Мультимедиа** (видео, изображения с alt)
- **FAQ / PAA оптимизация** (featured snippet, position 0)
- **Измеримые данные, источники, цитаты** (особенно для YMYL)

## Ссылочные
- **Backlinks** (с авторитетных сайтов — DA/DR)
- **Анкор-лист** (разнообразный, естественный)
- **Без токсичных ссылок** (Disavow)
- **Внутренняя перелинковка** (тематические кластеры)

## Семантика (с 2019 — семантический поиск)
- **BERT** (с 2019) — понимание контекста слов
- **MUM** (с 2021) — мультимодальный, 75 языков, понимание сложных запросов
- **Helpful Content System** — site-wide сигнал качества
- **Topic Authority** — авторитет по теме в целом, а не по странице
- **E-E-A-T** — экспертиза автора

## Структурированные данные (Schema.org)
Поддерживаемые rich snippets:
- Article, NewsArticle
- Book
- FAQPage
- HowTo
- Product, Offer, AggregateRating, Review
- Recipe
- Event
- LocalBusiness
- Person
- Organization
- BreadcrumbList
- VideoObject
- Course
- JobPosting

## Локальные
- **Google Business Profile** (для локального бизнеса)
- **NAP consistency** (Name, Address, Phone — единообразно везде)
- **Отзывы** (количество + качество)
- **Локальные ссылки**

## Анти-факторы (ручные алгоритмические штрафы)
- **Panda** (низкокачественный контент)
- **Penguin** (спамные ссылки)
- **Helpful Content Update** (бесполезный контент)
- **SpamBrain** (спам 2024+)
- **Клоакинг, скрытый текст, дорвеи**
- **Doorway pages** (страницы-ловушки)
- **Sneaky redirects**
- **User-generated spam** (комменты без модерации)

## Уникальные для Google
- **Featured snippets** (Position 0) — отдельная оптимизация
- **Knowledge Graph** (сущности)
- **People Also Ask** (PAA) — отдельная выдача
- **Image Search** (отдельная оптимизация)
- **Video Search** (YouTube интеграция)
- **Discover** (контент для ленты)
- **E-A-T → E-E-A-T** (с 2022 добавили Experience)

## Источники
- https://developers.google.com/search/docs
- https://search.google.com/search-console
- Google Search Central YouTube
- Quality Rater Guidelines (публикуются)
