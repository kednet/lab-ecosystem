# affiliate_links — AdvCake → Литрес

Генератор партнёрских URL для книг на litres.ru через CPA-сеть AdvCake.

## Что это даёт

- **Единый шаблон URL** с UTM-метками (`utm_source=advcake&utm_medium=cpa&utm_campaign=affiliate&utm_content=<HASH>`) + маркер рекламы `erid=...`
- **subid** для разделения трафика по каналам (`vk_post_42_2026-06-25_alhimik`)
- **Локальный кеш** в `cache/advcake_urls.json`, чтобы не пересобирать URL при каждом запросе
- **Проверка статуса erid** через ОРД VK API (если задан `ORD_BEARER_TOKEN`)

## Где взять параметры

| Переменная         | Где взти                                                  |
|--------------------|-----------------------------------------------------------|
| `ADVCAKE_HASH`     | ЛК AdvCake → "Мои источники" → ID ссылки (вида `c280b701`) |
| `ADVCAKE_ERID`     | ЛК ОРД (ord.vk.com) → erid креатива                       |
| `ADVCAKE_BASE_URL` | `https://www.litres.ru` (по умолчанию)                    |
| `ORD_BEARER_TOKEN` | ЛК ОРД → Настройки → API-ключи (опционально)             |

Скопируй `.env.example` → `.env` и заполни.

## Быстрый старт

```bash
# Генерация URL в одну команду
python -m affiliate_links.advcake /book/paulo-koelo/alhimik-122351/

# С subid (для разделения трафика)
python -m affiliate_links.advcake /book/paulo-koelo/alhimik-122351/ \
    --channel vk --post-id 42 --slug alhimik-koeluo

# Положить в кеш
python -m affiliate_links.advcake /book/paulo-koelo/alhimik-122351/ \
    --slug alhimik-koeluo --save-cache

# Проверить erid
python -m affiliate_links.verify_erid
python -m affiliate_links.verify_erid 2VfnxyNkZrY --json
```

## Использование из Python

```python
from affiliate_links.advcake import build_litres_url, make_book_affiliate

# Простая ссылка
url = build_litres_url("/book/paulo-koelo/alhimik-122351/")
# → https://www.litres.ru/book/paulo-koelo/alhimik-122351/?utm_source=advcake&...

# С subid
url = build_litres_url(
    "/book/paulo-koelo/alhimik-122351/",
    subid="vk_post_42_alhimik",
)

# Удобный wrapper для соцсетей
url = build_litres_url_with_label(
    "/book/paulo-koelo/alhimik-122351/",
    channel="vk", post_id=42, slug="alhimik-koeluo", date="2026-06-25",
)

# Полный объект (для JSON в books.json)
aff = make_book_affiliate(
    slug="alhimik-koeluo",
    book_path="/book/paulo-koelo/alhimik-122351/",
    subid="vk_post_42_alhimik",
)
print(aff.advcake_url)
print(aff.to_dict())
```

## Интеграция с lab_site

В `src/data/books.json` для каждой книги добавляется:

```json
{
  "slug": "alhimik-koeluo",
  "title": "Алхимик",
  "affiliate": {
    "litres_url": "https://www.litres.ru/book/paulo-koelo/alhimik-122351/",
    "advcake_url": "https://www.litres.ru/book/paulo-koelo/alhimik-122351/?utm_source=advcake&...",
    "erid": "2VfnxyNkZrY",
    "advcake_hash": "c280b701",
    "updated_at": "2026-06-25T..."
  }
}
```

Скрипт backfill — в планах, но URL на litres.ru для каждой книги надо
найти руками (или парсером из expert-reviews-hub).

## Маркировка рекламы (14.3 КоАП)

Каждая ссылка **обязана** сопровождаться плашкой вида:

> Реклама. ООО ЛИТРЕС, ИНН 7719571260, erid: 2VfnxyNkZrY

Это требование ФЗ «О рекламе». В lab_site/\[slug\].astro плашка
рендерится автоматически, если у книги есть `affiliate.erid`.

`verify_erid.py` помогает убедиться, что erid действующий — иначе
плашка бесполезна и грозит штраф до 500 000 ₽.

## Файлы

```
affiliate_links/
├── __init__.py              # публичный API
├── advcake.py               # генератор URL + кеш
├── verify_erid.py           # проверка статуса erid через ОРД VK
├── .env.example             # шаблон переменных окружения
└── README.md                # этот файл
```