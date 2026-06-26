# URL-slug генератор

## Назначение
Превращение заголовка страницы в SEO-дружественный URL-slug: транслитерация, удаление стоп-слов, обрезка, формат.

## Вход
- Заголовок страницы (на русском или английском)

## Алгоритм

### Шаг 1. Транслитерируй
Используется упрощённая таблица транслитерации (см. `scripts/slugify.py`).
```
а→a, б→b, в→v, г→g, д→d, е→e, ё→e, ж→zh, з→z, и→i, й→i,
к→k, л→l, м→m, н→n, о→o, п→p, р→r, с→s, т→t, у→u, ф→f,
х→h, ц→ts, ч→ch, ш→sh, щ→sch, ъ→'', ы→y, ь→'', э→e, ю→yu, я→ya
```

### Шаг 2. В нижний регистр
```python
text = text.lower()
```

### Шаг 3. Замени спецсимволы и пробелы на дефис
```python
import re
text = re.sub(r'[^a-z0-9]+', '-', text)
```

### Шаг 4. Удали стоп-слова
См. `data/stop-words.md`. Полный список — в `scripts/slugify.py:STOP_WORDS_RU`.

**Правила удаления:**
- Удалять «и», «в», «на», «по» — безопасно
- **НЕ удалять** «как», «не», «без», «с» — могут быть смыслообразующими
- **НЕ удалять** слова короче 3 букв (могут быть ключами)

### Шаг 5. Обрежь до 60 символов по границе слова
```python
if len(slug) > 60:
    slug = slug[:60].rsplit('-', 1)[0]
```

### Шаг 6. Финальная чистка
```python
slug = re.sub(r'-+', '-', slug).strip('-')
```

## Правила хорошего slug

| Правило | Пример ✅ | Пример ❌ |
|---------|-----------|-----------|
| Латиница, нижний регистр | `/transerfing-realnosti/` | `/Трансерфинг/` |
| Дефисы между словами | `/kak-brosit-kurit/` | `/kak_brosit_kurit/`, `/kakbrositkurit/` |
| Без стоп-слов | `/tehnika-ispolneniya-zhelanij/` | `/tehnika-dlya-ispolneniya-zhelanij-v-zhizni/` |
| Главный ключ в начале | `/transerfing-realnosti-konspekt/` | `/konspekt-knigi-transerfing/` |
| 3-60 символов | `/book/` | `/super-dlinnyy-zagolovok-knigi-transerfing-realnosti-vadema-zelanda-konspekt/` |
| Без ID, дат, параметров | `/vadim-zeland/` | `/author-1/`, `/2026-06-10-vadim/` |
| Без категории в URL | `/transerfing-realnosti/` | `/library/books/transerfing-realnosti/` |
| Без транслита русских названий для рус.контента | `/ispolnenie-zhelanij/` | `/ispolnenie-zhelanij-transliterated/` |
| Консистентный (одинаковый формат везде) | `/[author]/[book]/` | разнобой |

## Готовые примеры

| Заголовок | Slug |
|-----------|------|
| Трансерфинг реальности | `transerfing-realnosti` |
| Трансерфинг реальности — Вадим Зеланд | `transerfing-realnosti-vadim-zeland` |
| Как бросить курить навсегда | `kak-brosit-kurit-navsegda` |
| 5 техник исполнения желаний по Трансерфингу | `5-tehnik-ispolneniya-zhelanij-transerfing` |
| Лучшие книги по саморазвитию 2026 | `luchshie-knigi-samorazvitie-2026` |
| Карта желаний: пошаговое руководство | `karta-zhelanij-poshagovoe-rukovodstvo` |
| Воркбук «Исполнение желаний» — скачать PDF | `vorbouk-ispolnenie-zhelanij-skachat-pdf` |
| Отзывы на Трансерфинг реальности | `otzyvy-transerfing-realnosti` |
| Сравнение: Трансерфинг vs Закон притяжения | `sravnenie-transerfing-zakon-tyagoteniya` |

## Автогенерация из заголовка

Используй скрипт:
```bash
python scripts/slugify.py "Трансерфинг реальности — Вадим Зеланд"
# → transerfing-realnosti-vadim-zeland
# Варианты:
#   1. /transerfing-realnosti-vadim-zeland/
#   2. /transerfing-realnosti/
#   3. /transerfing-realnosti-vadim/
```

## Редиректы при смене slug
Если меняешь slug — настрой 301 редирект со старого на новый. Иначе потеряешь позиции и обратные ссылки.

```nginx
# nginx
location /old-slug/ {
    return 301 https://lab.com/new-slug/;
}
```

```apache
# .htaccess
Redirect 301 /old-slug/ https://lab.com/new-slug/
```

## Чек-лист
- [ ] Латиница, нижний регистр
- [ ] Дефисы, не подчёркивания
- [ ] Нет стоп-слов (но с осторожностью)
- [ ] Главный ключ в начале
- [ ] Длина 3-60 символов
- [ ] Консистентен с другими slug
- [ ] 301 редирект настроен при смене

## Пример вызова
```
/seo slug "Трансерфинг реальности — Вадим Зеланд: конспект и воркбук"
/seo slug
# (ввести заголовок)
```
