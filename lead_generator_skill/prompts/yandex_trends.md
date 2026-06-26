# /lead yandex-trends — ЗАГЛУШКА

> ⚠️ **СТАТУС (13.06.2026): API endpoint не найден. Команда не активна.**

## Почему заглушка

Яндекс Тренды как отдельный сервис **закрыт** в 2025-2026. Функциональность переехала в Wordstat, но:
- `trends.yandex.ru` → 404
- `api.wordstat.yandex.net` → не отвечает (нужен OAuth-токен)
- Endpoint динамики в `wordstat.yandex.ru` не виден в network traffic (рендерится в Highcharts SVG)
- Яндекс подтвердил перенос (см. `yandex.ru/support/trends/`)

## Что есть (бесплатно, работает)

- ✅ `/lead wordstat` — топ-200 фраз с частотностью (`/wordstat/api/getTable`)
- ✅ `/lead wordstat --compare-with <предыдущий_сбор>` — % роста/падения между двумя замерами
- ✅ `/lead spy-trends` — что крутят конкуренты

## Когда активировать `/lead yandex-trends`

### Вариант А: найдём endpoint вручную
1. Залогиниться в `wordstat.yandex.ru`
2. DevTools → Network → XHR
3. Кликнуть вкладку «Динамика»
4. Найти endpoint `getDynamics` или похожий
5. Раскомментировать код в `scripts/yandex_trends.py` → `fetch_history()`

### Вариант Б: подключить Яндекс Директ API
- Документация: `yandex.ru/dev/direct/`
- Endpoint: `/v4/wordstat/leaders` (лидеры) + динамика
- Стоимость: от 300 ₽/мес (минимум для API)
- Раскомментировать код → заменить `NotImplementedError` на реальные вызовы

### Вариант В: оставить как есть
- Использовать `/lead wordstat` 2 раза с паузой в 2-4 недели
- Сравнивать `totalValue` — автоматически вычислит % роста/падения

## Текущая заглушка — как использовать

```bash
# Запустится, но выдаст NotImplementedError
PYTHONIOENCODING=utf-8 python scripts/yandex_trends.py leaders
PYTHONIOENCODING=utf-8 python scripts/yandex_trends.py history --query "медитации онлайн"
```

## Что увидит пользователь сейчас

```
⚠️  Яндекс Тренды — ЗАГЛУШКА (13.06.2026)
   API endpoint не найден. Реальные данные недоступны.

⚠️  yandex_trends.fetch_leaders() — заглушка.
   API endpoint Яндекс Трендов не найден (13.06.2026).
   См. memory/yandex-trends-stub.md → раздел «Когда активировать».
   Альтернатива сейчас: /lead wordstat --compare-with <пред. сбор>
```

## Связано с: [[wordstat-parser-state]] (рабочий парсер Wordstat)
