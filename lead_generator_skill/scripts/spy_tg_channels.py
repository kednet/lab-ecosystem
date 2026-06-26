#!/usr/bin/env python3
"""
spy_tg_channels.py — поиск топовых Telegram-каналов в нише через tgstat.com.

TGStat имеет публичные страницы с фильтрами — парсим HTML.
Без авторизации видим: название, подписчики, ERR, тематику.

Использование:
    python spy_tg_channels.py --query "психология" --limit 15
    python spy_tg_channels.py --query "женский" --min-subs 5000 --output tg_channels.csv
"""

import argparse
import csv
import json
import time
import re
import sys


TGSTAT_URL = "https://tgstat.com"


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


def search_tgstat(query, limit=15, min_subs=1000):
    """Поиск каналов на tgstat.com. Без авторизации видим: название, подписчики, тематику."""
    _check_deps()
    import requests
    from bs4 import BeautifulSoup

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept-Language": "ru-RU,ru;q=0.9",
    }

    url = f"{TGSTAT_URL}/search"
    params = {"q": query}

    # Ретрай: tgstat иногда отдаёт 502/503
    response = None
    for attempt in range(3):
        try:
            response = requests.get(url, params=params, headers=headers, timeout=30)
            response.raise_for_status()
            break
        except Exception as e:
            if attempt < 2:
                wait = 2 ** attempt
                print(f"   ⚠️ Ошибка ({e}), повтор через {wait} сек...")
                time.sleep(wait)
            else:
                print(f"❌ Не удалось получить страницу TGStat: {e}")
                return []

    soup = BeautifulSoup(response.text, "html.parser")

    results = []
    # Карточки каналов (несколько вариантов селекторов — TGStat периодически меняет)
    cards = (
        soup.find_all("div", class_=re.compile(r"channel-card|peer-card|media-card|row"))
        or soup.find_all("a", class_=re.compile(r"channel|peer"))
        or soup.find_all("div", class_=re.compile(r"item"))
    )

    for card in cards:
        if len(results) >= limit:
            break
        name_el = card.find(class_=re.compile(r"channel-title|peer-title|title"))
        subs_el = card.find(class_=re.compile(r"subs|count|members"))
        link_el = card.find("a", href=True)
        desc_el = card.find(class_=re.compile(r"description|about|topic"))

        if name_el and link_el:
            href = link_el.get("href", "")
            subs_text = subs_el.get_text(strip=True) if subs_el else "0"
            subs_num = parse_subs_count(subs_text)

            # Не фильтруем жёстко здесь — выдаём всё, фильтр min_subs применим при лимите
            if subs_num < min_subs:
                continue
            results.append({
                "name": name_el.get_text(strip=True),
                "subscribers": subs_num,
                "subs_text": subs_text,
                "url": TGSTAT_URL + href if href.startswith("/") else href,
                "description": desc_el.get_text(strip=True)[:200] if desc_el else "",
            })

    return results


def parse_subs_count(text):
    """Парсит '12.3K', '1.5M', '450' → int."""
    text = text.upper().replace(" ", "").replace("\xa0", "")
    mult = 1
    if "K" in text:
        mult = 1000
        text = text.replace("K", "")
    elif "M" in text:
        mult = 1_000_000
        text = text.replace("M", "")
    try:
        return int(float(text) * mult)
    except (ValueError, TypeError):
        return 0


def print_report(channels, query):
    print(f"\n{'='*60}")
    print(f"📱 TG-КАНАЛЫ В НИШЕ «{query}»")
    print(f"{'='*60}\n")
    print(f"Найдено: {len(channels)}\n")

    if not channels:
        print("⚠️ Не найдено. Возможные причины:")
        print("   — TGStat изменил вёрстку (обнови селекторы)")
        print("   — Включи VPN (tgstat иногда капризничает в РФ)")
        print("   — Попробуй более общее ключевое слово\n")
        return

    for i, ch in enumerate(channels, 1):
        print(f"[{i}] {ch['name']} — {ch['subs_text']} подписчиков")
        if ch["description"]:
            print(f"    {ch['description'][:120]}")
        print(f"    {ch['url']}")
        print()


def save_csv(channels, path):
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["name", "subscribers", "subs_text", "url", "description"])
        writer.writeheader()
        writer.writerows(channels)
    print(f"💾 Сохранено: {path}")


def main():
    parser = argparse.ArgumentParser(description="Парсер TG-каналов через TGStat")
    parser.add_argument("--query", required=True, help="Ключевое слово ниши")
    parser.add_argument("--limit", type=int, default=15)
    parser.add_argument("--min-subs", type=int, default=1000, help="Мин. подписчиков")
    parser.add_argument("--output", help="Путь к CSV")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    channels = search_tgstat(args.query, args.limit, args.min_subs)

    if args.json:
        print(json.dumps(channels, ensure_ascii=False, indent=2))
    else:
        print_report(channels, args.query)

    if args.output:
        save_csv(channels, args.output)


if __name__ == "__main__":
    main()
