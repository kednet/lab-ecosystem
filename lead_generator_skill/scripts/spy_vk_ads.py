#!/usr/bin/env python3
"""
spy_vk_ads.py — поиск креативов конкурентов в VK Ads Library.

ads.vk.com — открытая библиотека, можно парсить без авторизации.
Работает медленно (1 запрос = 3-5 сек) — поэтому по дефолту берём топ-20.

Использование:
    python spy_vk_ads.py --query "психолог онлайн" --limit 20
    python spy_vk_ads.py --query "карта желаний" --days 30 --output vk_ads.csv
"""

import argparse
import csv
import json
import time
import re
import sys
from pathlib import Path


BASE_URL = "https://ads.vk.com"
SEARCH_URL = f"{BASE_URL}/ads"


def _check_deps():
    """Проверяет, что requests и bs4 установлены. Если нет — выдаёт понятную ошибку."""
    missing = []
    try:
        import requests  # noqa: F401
    except ImportError:
        missing.append("requests")
    try:
        from bs4 import BeautifulSoup  # noqa: F401
    except ImportError:
        missing.append("beautifulsoup4")
    if missing:
        print("❌ Не установлены зависимости:", ", ".join(missing))
        print("   Установи одной командой:")
        print("   pip install " + " ".join(missing))
        sys.exit(1)


def search_vk_ads_html(query, limit=20):
    """Парсим HTML-выдачу ads.vk.com. Без API, через requests.
    Возвращает список dict: {title, advertiser, snippet, url}.
    Если 0 результатов — пробуем альтернативные селекторы."""
    _check_deps()
    import requests
    from bs4 import BeautifulSoup

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                      "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept-Language": "ru-RU,ru;q=0.9",
    }

    results = []
    page = 1
    while len(results) < limit and page <= 5:  # макс. 5 страниц
        params = {"q": query, "page": page}

        # Ретрай с экспоненциальным бэкоффом: 2-3 попытки
        response = None
        for attempt in range(3):
            try:
                response = requests.get(SEARCH_URL, params=params, headers=headers, timeout=30)
                response.raise_for_status()
                break
            except Exception as e:
                if attempt < 2:
                    wait = 2 ** attempt
                    print(f"   ⚠️ Ошибка запроса ({e}), повтор через {wait} сек...")
                    time.sleep(wait)
                else:
                    print(f"   ❌ Не удалось получить страницу {page}: {e}")
                    return results

        soup = BeautifulSoup(response.text, "html.parser")

        # Карточки креативов (несколько вариантов селекторов — VK периодически меняет)
        cards = (
            soup.find_all("div", class_=re.compile(r"ad-card|AdCard|ads-item"))
            or soup.find_all("article")
            or soup.find_all("div", class_=re.compile(r"item|card|ad|creative"))
        )

        for card in cards:
            if len(results) >= limit:
                break
            title_el = card.find(["h3", "h4", "span"], class_=re.compile(r"title|ad-title|heading"))
            adv_el = card.find(class_=re.compile(r"advertiser|brand|sponsor|author"))
            link_el = card.find("a", href=True)
            if title_el and link_el:
                results.append({
                    "title": title_el.get_text(strip=True),
                    "advertiser": adv_el.get_text(strip=True) if adv_el else "",
                    "url": link_el["href"] if link_el["href"].startswith("http") else BASE_URL + link_el["href"],
                    "snippet": card.get_text(" | ", strip=True)[:300],
                })

        page += 1
        time.sleep(2)  # вежливая задержка

    return results


def print_report(creatives, query):
    print(f"\n{'='*60}")
    print(f"🔍 VK ADS LIBRARY: «{query}»")
    print(f"{'='*60}\n")
    print(f"Найдено креативов: {len(creatives)}\n")

    if not creatives:
        print("⚠️ Ничего не найдено. Возможные причины:")
        print("   — VK изменил вёрстку (обнови селекторы в скрипте)")
        print("   — Запрос слишком специфичный (попробуй короче)")
        print("   — Включи VPN (иногда ads.vk.com капризничает)\n")
        return

    for i, c in enumerate(creatives, 1):
        print(f"[{i}] {c['advertiser'] or '—'}")
        print(f"    Заголовок: {c['title'][:100]}")
        print(f"    URL: {c['url'][:80]}")
        print(f"    Фрагмент: {c['snippet'][:120]}...")
        print()


def save_csv(creatives, path):
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["title", "advertiser", "url", "snippet"])
        writer.writeheader()
        writer.writerows(creatives)
    print(f"💾 Сохранено: {path} ({len(creatives)} строк)")


def main():
    parser = argparse.ArgumentParser(description="Парсер VK Ads Library")
    parser.add_argument("--query", required=True, help="Поисковый запрос (ниша, конкурент)")
    parser.add_argument("--limit", type=int, default=20, help="Сколько креативов собрать")
    parser.add_argument("--output", help="Путь к CSV-файлу для сохранения")
    parser.add_argument("--json", action="store_true", help="Вывести как JSON")
    args = parser.parse_args()

    creatives = search_vk_ads_html(args.query, args.limit)

    if args.json:
        print(json.dumps(creatives, ensure_ascii=False, indent=2))
    else:
        print_report(creatives, args.query)

    if args.output:
        save_csv(creatives, args.output)


if __name__ == "__main__":
    main()
