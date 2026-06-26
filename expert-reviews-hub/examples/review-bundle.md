# Пример bundle.json — Трансерфинг реальности

> Это пример готового bundle.json, собранного из 4 источников.
> Используется как референс для режима `/reviews all` и как вход для `/reviews summarize`.

---

```yaml
# reviews/transerfing-realnosti/bundle.json
book:
  slug: "transerfing-realnosti"
  title: "Трансерфинг реальности"
  author: "Вадим Зеланд"
  year: 2004
  isbn: "978-5-9573-2964-7"
  language: "ru"
  
generated_at: "2026-06-10T14:45:00"
generated_by: "expert-reviews-hub/skill v1.0"

sources:
  - name: "litres"
    weight: 1.5
    count: 234
    avg_rating: 4.8
    url: "https://www.litres.ru/vadim-zeland/transerfing-realnosti/otzyvy/"
    fetched_at: "2026-06-10T14:00:00"
    verified_ratio: 1.0
    note: "100% verified покупатели"
    
  - name: "livelib"
    weight: 1.2
    count: 847
    avg_rating: 4.7
    url: "https://www.livelib.ru/book/1000283027"
    fetched_at: "2026-06-10T14:10:00"
    verified_ratio: 0.0
    note: "LiveLib — без верификации, но крупнейшая база"
    
  - name: "ozon"
    weight: 0.7
    count: 120  # было 166, отфильтровано 46
    avg_rating: 4.5
    url: "https://www.ozon.ru/product/transerfing-realnosti-zeland-123456/"
    fetched_at: "2026-06-10T14:20:00"
    verified_ratio: 0.6
    filtered_out: 46
    filter_reasons:
      no_text: 30
      template: 10
      duplicate: 6
    note: "Ozon — много накруток, фильтруем спам"
    
  - name: "own"
    weight: 1.5
    count: 8
    avg_rating: 5.0
    url: "https://lab.com/library/transerfing-realnosti"
    fetched_at: "2026-06-10T14:30:00"
    verified_ratio: 1.0
    note: "Свои отзывы с лендинга + Telegram-бота"

totals:
  sources_count: 4
  total_reviews: 1209
  weighted_avg: 4.69
  confidence: "high"  # 4 источника, 1209 отзывов, ~25% verified

# Сырые отзывы (для AI-суммаризации)
reviews:
  # === Литрес (топ-3 по лайкам) ===
  - id: "litres_001"
    source: "litres"
    author: "Анна"
    rating: 5
    date: "2024-12-15"
    text: "Эта книга перевернула моё мышление. После неё я перестала бояться перемен и начала действовать. Спасибо автору за такой подход!"
    likes: 145
    verified: true
    
  - id: "litres_002"
    source: "litres"
    author: "Сергей"
    rating: 5
    date: "2024-11-20"
    text: "Прочитал за 2 дня. Начал применять техники — работает. Изменилось отношение к деньгам, времени, людям."
    likes: 98
    verified: true
    
  - id: "litres_003"
    source: "litres"
    author: "Мария"
    rating: 4
    date: "2024-10-15"
    text: "Хорошая книга для мотивации, но много 'воды' и повторений. Нет научного обоснования. Подходит для вдохновения, не для практики."
    likes: 67
    verified: true
    
  # === LiveLib (топ-2) ===
  - id: "livelib_001"
    source: "livelib"
    author: "Иван П."
    rating: 5
    date: "2024-09-01"
    text: "Книга, которая изменила мой взгляд на жизнь. Перечитываю каждый год, нахожу новое."
    verified: false
    
  - id: "livelib_002"
    source: "livelib"
    author: "Екатерина"
    rating: 3
    date: "2024-08-15"
    text: "Слишком эзотерично для меня. Не верю в 'управление реальностью', но читается легко."
    verified: false
    
  # === Ozon (после фильтрации) ===
  - id: "ozon_001"
    source: "ozon"
    author: "Алексей"
    rating: 5
    date: "2024-07-20"
    text: "Книга огонь! Изменила мышление. Покупал маме, теперь читаю сам. Рекомендую всем."
    verified: true
    spam_score: 0.1
    
  # === Свои (с лендинга) ===
  - id: "own_001"
    source: "own"
    author: "Анна К."
    rating: 5
    date: "2026-05-15"
    text: "Конспект помог структурировать идеи. Особенно понравилась глава про слайды и цели. Начала применять — работает!"
    context: "Конспект «Трансерфинг реальности»"
    verified: true
    url: "https://lab.com/library/transerfing-realnosti#review-1"
    
  - id: "own_002"
    source: "own"
    author: "@pulabru_reader"
    rating: 5
    date: "2026-05-10"
    text: "Подробный разбор. Видно, что автор вложился. Единственное — хотелось бы больше примеров из жизни."
    context: "Telegram-бот, конспект"
    verified: true

metadata:
  fetch_strategy: "all"
  excluded_sources: ["author_today"]  # не нашли
  errors: []
  
processing:
  ai_summary_generated: true
  verdict: >
    Книга имеет высокий рейтинг 4.69/5 в основных источниках (Литрес 4.8, LiveLib 4.7).
    Хвалят за практичность и изменение мышления (78% отзывов).
    Критикуют за отсутствие научного обоснования (52%) и эзотеричность (15%).
    Подходит для тех, кто готов к нестандартному подходу и работает над мышлением.
  pros_count: 5
  cons_count: 4
  quotes_count: 5
```

## Как использовать этот bundle

```bash
# 1. Сводная статистика
python scripts/review_stats.py reviews/transerfing-realnosti/

# 2. AI-суммаризация (отдельно)
# Передать bundle.json в AI с промптом review-summarize.md
# → получить markdown-отчёт

# 3. Использовать для SEO
# weighted_avg → schema.org AggregateRating
# verdict → meta description
# top_quotes → блок "Цитаты" на странице книги
```
