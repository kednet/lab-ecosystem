# Шаблон bundle отзывов (агрегатор всех источников)

## Назначение
Объединение отзывов из разных источников в единый bundle.json для последующей AI-суммаризации.

## Структура

```yaml
# reviews/{book-slug}/bundle.json
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
  # Каждый источник со своими весами (см. data/sources-rating.md)
  - name: "litres"
    weight: 1.5
    count: 234
    avg_rating: 4.8
    url: "https://www.litres.ru/vadim-zeland/transerfing-realnosti/otzyvy/"
    fetched_at: "2026-06-10T14:00:00"
    verified_ratio: 1.0   # litres — 100% покупатели
    
  - name: "livelib"
    weight: 1.2
    count: 847
    avg_rating: 4.7
    url: "https://www.livelib.ru/book/1000283027"
    fetched_at: "2026-06-10T14:10:00"
    verified_ratio: 0.0  # livelib — без верификации
    
  - name: "ozon"
    weight: 0.7
    count: 166
    avg_rating: 4.5
    url: "https://www.ozon.ru/product/..."
    fetched_at: "2026-06-10T14:20:00"
    verified_ratio: 0.6
    filtered_out: 46
    filter_reasons:
      no_text: 30
      template: 10
      duplicate: 6
      
  - name: "own"
    weight: 1.5
    count: 8
    avg_rating: 5.0
    url: "https://lab.com/library/transerfing-realnosti"
    fetched_at: "2026-06-10T14:30:00"
    verified_ratio: 1.0  # свои = always verified

totals:
  sources_count: 4
  total_reviews: 1255
  weighted_avg: 4.7
  confidence: "high"  # high | medium | low

reviews:
  # Все отзывы с метаданными
  - id: "litres_001"
    source: "litres"
    author: "Анна"
    rating: 5
    date: "2024-12-15"
    text: "Эта книга перевернула моё мышление..."
    pros: "..."
    cons: "..."
    verified: true
    weight: 1.5
    url: "https://www.litres.ru/..."
    
  - id: "livelib_001"
    source: "livelib"
    author: "Иван П."
    rating: 5
    date: "2024-11-20"
    text: "Полностью согласна с автором..."
    verified: false
    weight: 1.2
    url: "https://www.livelib.ru/..."
    
  - id: "own_001"
    source: "own"
    author: "Анна К."
    rating: 5
    date: "2026-05-15"
    text: "Конспект помог разобраться..."
    context: "Конспект «Трансерфинг реальности»"
    verified: true
    weight: 1.5
    url: "https://lab.com/..."

metadata:
  fetch_strategy: "all"
  excluded_sources: []  # например ["author_today"] если не нашли
  errors: []  # ошибки парсинга по источникам
  
processing:
  ai_summary_generated: true
  verdict: "Книга имеет высокий рейтинг..."
  pros_count: 5
  cons_count: 4
  quotes_count: 5
```

## Алгоритм сборки bundle

```python
def build_bundle(book_slug):
    bundle = {
        "book": load_book_meta(book_slug),
        "generated_at": now(),
        "sources": [],
        "reviews": []
    }
    
    # 1. Собрать из каждого источника
    for source in ["litres", "livelib", "ozon", "own"]:
        try:
            data = parse_source(source, book_slug)
            bundle["sources"].append({
                "name": source,
                "weight": SOURCES_WEIGHT[source],
                **data["rating"],
                "url": data["source_url"]
            })
            bundle["reviews"].extend(data["reviews"])
        except Exception as e:
            bundle["metadata"]["errors"].append({
                "source": source,
                "error": str(e)
            })
    
    # 2. Посчитать итоги
    bundle["totals"] = calculate_totals(bundle)
    
    return bundle
```

## Использование

1. **/reviews all {book}** — собрать все источники
2. **/reviews summarize {book}** — AI-суммаризация bundle
3. **/reviews compare {book1} {book2}** — сравнение двух bundle

## Связанные файлы

- `prompts/review-{source}.md` — парсинг каждого источника
- `prompts/review-summarize.md` — AI-анализ bundle
- `data/sources-rating.md` — веса источников
- `scripts/review_stats.py` — расчёт weighted_average
