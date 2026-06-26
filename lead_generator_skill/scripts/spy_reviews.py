#!/usr/bin/env python3
"""
spy_reviews.py — парсер отзывов с otzovik.com и irecommend.ru.

Ищем боли клиентов, триггеры, частые возражения.
Идея: ввести название продукта/конкурента, получить 20-30 отзывов и частотный словарь болей.

Использование:
    python spy_reviews.py --query "карта желаний" --site otzovik --limit 20
    python spy_reviews.py --query "psiholib" --site irecommend --output reviews.csv
"""

import argparse
import csv
import json
import re
import time
import sys
from collections import Counter
from urllib.parse import quote


SITES = {
    "otzovik": "https://otzovik.com",
    "irecommend": "https://irecommend.ru",
}


def _check_deps():
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


def fetch_otzovik(query, limit=20):
    """Парсер otzovik.com — поиск по товару. Без API, через requests."""
    _check_deps()
    import requests
    from bs4 import BeautifulSoup

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept-Language": "ru-RU,ru;q=0.9",
    }

    base = SITES["otzovik"]
    search_url = f"{base}/search/"
    results = []

    # Поиск
    response = None
    for attempt in range(3):
        try:
            response = requests.get(search_url, params={"text": query}, headers=headers, timeout=30)
            response.raise_for_status()
            break
        except Exception as e:
            if attempt < 2:
                wait = 2 ** attempt
                print(f"   ⚠️ Ошибка поиска ({e}), повтор через {wait} сек...")
                time.sleep(wait)
            else:
                print(f"❌ Не удалось получить выдачу: {e}")
                return []

    soup = BeautifulSoup(response.text, "html.parser")

    # Ссылки на отзывы
    review_links = soup.find_all("a", href=re.compile(r"/review[s]?/\d+"))
    review_urls = []
    seen = set()
    for a in review_links:
        href = a["href"]
        full = base + href if href.startswith("/") else href
        if full not in seen:
            seen.add(full)
            review_urls.append(full)

    for url in review_urls[:limit]:
        # Ретрай для каждого отзыва
        for attempt in range(2):
            try:
                r = requests.get(url, headers=headers, timeout=20)
                r.raise_for_status()
                break
            except Exception as e:
                if attempt == 0:
                    print(f"   ⚠️ Ошибка загрузки отзыва ({e}), повтор...")
                    time.sleep(2)
                else:
                    print(f"   ⚠️ Пропускаю отзыв: {e}")
                    r = None
                    break
        if r is None:
            continue

        soup = BeautifulSoup(r.text, "html.parser")

        # Заголовок отзыва
        title_el = soup.find(["h1", "h2"], class_=re.compile(r"review-title|product-name|review-header"))
        title = title_el.get_text(strip=True) if title_el else ""

        # Текст отзыва
        body_el = soup.find("div", class_=re.compile(r"review-body|review-text|description|review-content"))
        body = body_el.get_text(" ", strip=True) if body_el else ""

        # Плюсы/минусы
        pros_el = soup.find(class_=re.compile(r"pros|plus|good|positive"))
        cons_el = soup.find(class_=re.compile(r"cons|minus|bad|negative"))
        pros = pros_el.get_text(" ", strip=True) if pros_el else ""
        cons = cons_el.get_text(" ", strip=True) if cons_el else ""

        results.append({
            "url": url,
            "title": title,
            "body": body[:500],
            "pros": pros[:200],
            "cons": cons[:200],
        })

        time.sleep(1.5)  # вежливая задержка

    return results


def extract_pains(reviews):
    """Извлекаем частотные боли из минусов и негативных слов."""
    pain_markers = [
        "не работает", "не помог", "разочарован", "зря потратил", "деньги на ветер",
        "обман", "развод", "не верю", "пустышка", "ерунда", "бесполезно",
        "дорого", "слишком дорого", "не стоит", "жалею", "не рекомендую",
        "не понравилось", "не интересно", "скучно", "вода", "много воды",
        "не получила", "не получил", "не помогло", "никакого эффекта", "ноль",
        "плохо", "ужасно", "кошмар", "худший", "не покупайте", "уходите",
    ]

    counter = Counter()
    for r in reviews:
        text = (r.get("cons", "") + " " + r.get("body", "")).lower()
        for marker in pain_markers:
            if marker in text:
                counter[marker] += 1

    return counter.most_common(10)


def print_report(reviews, query, site):
    print(f"\n{'='*60}")
    print(f"💬 ОТЗЫВЫ С {site.upper()}: «{query}»")
    print(f"{'='*60}\n")
    print(f"Собрано отзывов: {len(reviews)}\n")

    if not reviews:
        print("⚠️ Не найдено. Возможные причины:")
        print("   — Otzovik изменил вёрстку (обнови селекторы)")
        print("   — Запрос слишком редкий (попробуй имя бренда конкурента)")
        print("   — Включи VPN (otzovik иногда капризничает)\n")
        return

    for i, r in enumerate(reviews, 1):
        print(f"[{i}] {r['title'][:80]}")
        if r["pros"]:
            print(f"    ➕ {r['pros'][:120]}")
        if r["cons"]:
            print(f"    ➖ {r['cons'][:120]}")
        print()

    pains = extract_pains(reviews)
    if pains:
        print(f"\n{'='*60}")
        print(f"🔥 ТОП-10 БОЛЕЙ (частотность):")
        print(f"{'='*60}\n")
        for pain, count in pains:
            print(f"  {count:3}×  {pain}")


def save_csv(reviews, path):
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["title", "body", "pros", "cons", "url"])
        writer.writeheader()
        writer.writerows(reviews)
    print(f"\n💾 Сохранено: {path}")


def main():
    parser = argparse.ArgumentParser(description="Парсер отзывов с otzovik/irecommend")
    parser.add_argument("--query", required=True, help="Продукт / тема / конкурент")
    parser.add_argument("--site", choices=["otzovik", "irecommend"], default="otzovik")
    parser.add_argument("--limit", type=int, default=20)
    parser.add_argument("--output", help="Путь к CSV")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    if args.site == "otzovik":
        reviews = fetch_otzovik(args.query, args.limit)
    else:
        print(f"⚠️ Парсер irecommend в разработке. Используй --site otzovik")
        reviews = []

    if args.json:
        print(json.dumps(reviews, ensure_ascii=False, indent=2))
    else:
        print_report(reviews, args.query, args.site)

    if args.output:
        save_csv(reviews, args.output)


if __name__ == "__main__":
    main()
