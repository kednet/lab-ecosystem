#!/usr/bin/env python3
"""
yandex_trends.py — ЗАГЛУШКА: будущий парсер Яндекс Трендов.

⚠️  СТАТУС (13.06.2026): API endpoint не найден.

## Почему заглушка
- `trends.yandex.ru` отдаёт 404 (закрыт как отдельный сервис)
- `api.wordstat.yandex.net` не отвечает (нужен OAuth-токен)
- Динамика истории в Wordstat рендерится в Highcharts SVG, но endpoint для неё
  не виден в network traffic (требует глубокой отладки JS рантайма)
- Яндекс подтвердил, что Тренды переехали в Wordstat (yandex.ru/support/trends/)

## Когда активировать
Когда понадобится динамика по дням/неделям/месяцам:
1. **Вариант А (ручной поиск endpoint):** авторизоваться в Wordstat, DevTools → Network →
   кликнуть вкладку «Динамика» → найти XHR с `getDynamics` или похожим.
2. **Вариант Б (платный API):** подключить Яндекс Директ API (от 300 ₽/мес),
   у него есть `/v4/wordstat/leaders` и динамика.
3. **Вариант В (косвенно через wordstat):** два запуска wordstat с разницей в месяц,
   сравнить totalValue — вычислить % роста/падения.

## Что здесь готово
- ✅ CLI-аргументы (как у wordstat)
- ✅ Структура вывода (JSON/CSV/таблица)
- ✅ Документация использования
- ❌ Реальные HTTP-вызовы (NotImplementedError)

После активации — раскомментировать код в `fetch_leaders()`, `fetch_history()`,
`fetch_phrase_dynamic()` и заменить `NotImplementedError` на реальные вызовы.
"""

import argparse
import csv
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

# ============== ЗАГЛУШКА: реальные endpoints ==============
# Когда найдём — заполнить
TRENDS_BASE_URL = "https://trends.yandex.ru"  # ⚠️ 404 на 13.06.2026
WORDSTAT_API_URL = "https://wordstat.yandex.ru/wordstat/api"  # ✅ работает
DYNAMIC_ENDPOINT = None  # ❌ Не найден
LEADERS_ENDPOINT = None  # ❌ Не найден
PHRASE_HISTORY_ENDPOINT = None  # ❌ Не найден
# =========================================================


def _not_implemented(method_name):
    """Централизованная заглушка."""
    raise NotImplementedError(
        f"⚠️  yandex_trends.{method_name}() — заглушка.\n"
        f"   API endpoint Яндекс Трендов не найден (13.06.2026).\n"
        f"   См. memory/yandex-trends-stub.md → раздел «Когда активировать».\n"
        f"   Альтернатива сейчас: /lead wordstat --compare-with <пред. сбор>"
    )


def fetch_leaders(region="225", lang="ru", limit=20):
    """ЗАГЛУШКА: лидеры роста/падения.

    Когда endpoint найдётся — реализовать здесь.
    Ожидаемый формат возврата:
    [
        {"phrase": "нейросети для бизнеса", "growth_pct": 180, "frequency": 12500},
        ...
    ]
    """
    _not_implemented("fetch_leaders")


def fetch_history(phrase, period="2y", region="225"):
    """ЗАГЛУШКА: динамика по фразе за период.

    Ожидаемый формат возврата:
    [
        {"date": "2025-06-01", "frequency": 12000},
        {"date": "2025-07-01", "frequency": 13500},
        ...
    ]
    """
    _not_implemented("fetch_history")


def fetch_phrase_dynamic(phrase, granularity="monthly"):
    """ЗАГЛУШКА: динамика по фразе (день/неделя/месяц)."""
    _not_implemented("fetch_phrase_dynamic")


# ============== CLI И ВЫВОД (готовы к использованию) ==============

def print_leaders_report(leaders, region="225"):
    print(f"\n{'='*70}")
    print(f"📈 ЯНДЕКС ТРЕНДЫ: Лидеры ({region})")
    print(f"{'='*70}\n")
    print(f"Найдено: {len(leaders)}\n")
    if not leaders:
        print("⚠️ Нет данных")
        return
    print(f"{'#':<3} {'Рост %':<8} {'Частотность':<14} {'Фраза'}")
    print("-" * 80)
    for i, item in enumerate(leaders, 1):
        growth = f"+{item.get('growth_pct', 0):.0f}%" if item.get('growth_pct', 0) > 0 else "—"
        freq = f"{item.get('frequency', 0):,}".replace(",", " ")
        phrase = item.get("phrase", "?")[:50]
        print(f"{i:<3} {growth:<8} {freq:<14} {phrase}")


def print_history_report(history, phrase, period="2y"):
    print(f"\n{'='*70}")
    print(f"📈 ДИНАМИКА: «{phrase}» ({period})")
    print(f"{'='*70}\n")
    if not history:
        print("⚠️ Нет данных")
        return
    print(f"Точек: {len(history)}\n")
    if len(history) >= 2:
        first, last = history[0], history[-1]
        change = ((last['frequency'] - first['frequency']) / first['frequency'] * 100) if first['frequency'] else 0
        print(f"📊 Изменение: {first['date']} ({first['frequency']:,}) → {last['date']} ({last['frequency']:,})")
        print(f"   {'+' if change > 0 else ''}{change:.1f}%\n")
    print(f"{'Дата':<14} {'Частотность':<14} {'Δ vs пред.'}")
    print("-" * 50)
    prev = None
    for item in history:
        freq = item['frequency']
        delta = ""
        if prev is not None and prev > 0:
            d = (freq - prev) / prev * 100
            delta = f"{'+' if d > 0 else ''}{d:.1f}%"
        print(f"{item['date']:<14} {freq:<14,} {delta}")
        prev = freq


def save_json(data, path, query, kind="leaders"):
    payload = {
        "source": "yandex_trends (ЗАГЛУШКА)",
        "query": query,
        "kind": kind,
        "collected_at": datetime.now(timezone.utc).isoformat(),
        "note": "Endpoint не найден. Запустите /lead wordstat для актуальных данных.",
        "data": data,
    }
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n💾 JSON: {path}")


def save_csv(data, path, kind="leaders"):
    if kind == "leaders":
        fields = ["phrase", "growth_pct", "frequency", "region"]
    else:
        fields = ["date", "frequency"]
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for item in data:
            writer.writerow({k: item.get(k, "") for k in fields})
    print(f"💾 CSV:  {path}")


def main():
    parser = argparse.ArgumentParser(
        description="Парсер Яндекс Трендов (ЗАГЛУШКА — endpoint не найден)",
    )
    parser.add_argument(
        "mode", choices=["leaders", "history", "phrase"],
        help="Режим: leaders (топ роста/падения), history (вся динамика), phrase (одна фраза)",
    )
    parser.add_argument("--query", "--phrase", help="Фраза (для режимов history/phrase)")
    parser.add_argument("--period", default="2y",
                        help="Период для динамики: 1m, 3m, 6m, 1y, 2y (default 2y)")
    parser.add_argument("--region", default="225",
                        help="Регион (225 = Россия, 213 = Москва, default 225)")
    parser.add_argument("--limit", type=int, default=20, help="Сколько лидеров показать")
    parser.add_argument("--output", help="Путь к CSV")
    parser.add_argument("--json", help="Путь к JSON")
    args = parser.parse_args()

    print(f"\n⚠️  Яндекс Тренды — ЗАГЛУШКА (13.06.2026)")
    print(f"   API endpoint не найден. Реальные данные недоступны.\n")

    if args.mode == "leaders":
        try:
            leaders = fetch_leaders(region=args.region, limit=args.limit)
            print_leaders_report(leaders, args.region)
            if args.json:
                save_json(leaders, args.json, f"leaders_{args.region}", kind="leaders")
        except NotImplementedError as e:
            print(f"\n{e}\n")
            print(f"💡 Альтернатива сейчас: /lead wordstat — собирает топ-200 фраз с частотностью.")

    elif args.mode in ("history", "phrase"):
        if not args.query:
            print("❌ --query обязателен для режимов history/phrase")
            return
        try:
            history = fetch_history(args.query, period=args.period, region=args.region)
            print_history_report(history, args.query, args.period)
            if args.json:
                save_json(history, args.json, args.query, kind="history")
        except NotImplementedError as e:
            print(f"\n{e}\n")
            print(f"💡 Альтернатива сейчас:")
            print(f"   1) /lead wordstat  → цифры по фразе сейчас")
            print(f"   2) Повторить через 2-4 недели → сравнить totalValue")


if __name__ == "__main__":
    main()
