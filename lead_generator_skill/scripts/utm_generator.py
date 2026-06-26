#!/usr/bin/env python3
"""
utm_generator.py — генератор UTM-меток по стандарту.

Использование:
    python utm_generator.py --source vk --medium cpm --campaign laboratoriya_q1
    python utm_generator.py --source ok --medium cpm --campaign laboratoriya_january --content creative1
"""

import argparse
from urllib.parse import urlencode


# Стандарт именования
SOURCE_MAPPING = {
    "vk": "vk",
    "ok": "ok",
    "tg": "telegram",
    "yandex": "yandex",
    "dzen": "dzen",
    "yappy": "yappy",
    "avito": "avito",
    "webinar": "webinar",
    "email": "email",
    "blogger": "blogger",
}

MEDIUM_MAPPING = {
    "cpm": "cpm",
    "cpc": "cpc",
    "cpa": "cpa",
    "social": "social",
    "email": "email",
    "messenger": "messenger",
    "referral": "referral",
    "organic": "organic",
}


def generate_utm(source, medium, campaign, content=None, term=None, base_url="https://app.pulab.online"):
    """Генерация UTM-меток."""
    source = SOURCE_MAPPING.get(source, source)
    medium = MEDIUM_MAPPING.get(medium, medium)

    params = {
        "utm_source": source,
        "utm_medium": medium,
        "utm_campaign": campaign,
    }

    if content:
        params["utm_content"] = content
    if term:
        params["utm_term"] = term

    utm = urlencode(params)
    return f"{base_url}?{utm}"


def generate_utm_set(campaign_name, segments=None, creatives=None, base_url="https://app.pulab.online"):
    """
    Генерация набора UTM для всех каналов × сегментов × креативов.

    segments: ["a", "b", "c"]
    creatives: ["emotional", "rational", "anti-marketing"]
    """
    if not segments:
        segments = ["b"]
    if not creatives:
        creatives = ["default"]

    sources_mediums = [
        ("vk", "cpm"),
        ("ok", "cpm"),
        ("tg", "cpa"),
        ("yandex", "cpc"),
        ("dzen", "cpm"),
        ("yappy", "cpm"),
        ("avito", "cpc"),
    ]

    results = []

    for source, medium in sources_mediums:
        for segment in segments:
            for creative in creatives:
                full_campaign = f"{campaign_name}_{segment}"
                content = creative
                term = f"seg_{segment}"

                url = generate_utm(
                    source=source,
                    medium=medium,
                    campaign=full_campaign,
                    content=content,
                    term=term,
                    base_url=base_url,
                )

                results.append({
                    "source": source,
                    "medium": medium,
                    "segment": segment,
                    "creative": creative,
                    "url": url,
                })

    return results


def print_single(url, source, medium, campaign, content=None, term=None):
    print(f"\n🔗 UTM-ССЫЛКА\n")
    print(f"Source:   {source}")
    print(f"Medium:   {medium}")
    print(f"Campaign: {campaign}")
    if content:
        print(f"Content:  {content}")
    if term:
        print(f"Term:     {term}")
    print(f"\nURL: {url}\n")


def print_set(results, campaign_name):
    print(f"\n🔗 НАБОР UTM-ССЫЛОК: кампания «{campaign_name}»\n")
    print(f"{'Source':<10} {'Medium':<8} {'Seg':<5} {'Creative':<20} {'URL'}")
    print(f"{'-'*120}")

    for r in results:
        print(f"{r['source']:<10} {r['medium']:<8} {r['segment']:<5} {r['creative']:<20} {r['url']}")

    print(f"\nВсего ссылок: {len(results)}")


def main():
    parser = argparse.ArgumentParser(description="Генератор UTM-меток")
    parser.add_argument("--source", type=str, help="Источник (vk, ok, tg, yandex, dzen, ...)")
    parser.add_argument("--medium", type=str, default="cpm", help="Тип (cpm, cpc, cpa)")
    parser.add_argument("--campaign", type=str, help="Название кампании")
    parser.add_argument("--content", type=str, help="Контент (креатив)")
    parser.add_argument("--term", type=str, help="Ключевое слово/термин")
    parser.add_argument("--base-url", type=str, default="https://app.pulab.online", help="Базовый URL")
    parser.add_argument("--set", action="store_true", help="Сгенерировать набор для всех каналов")
    parser.add_argument("--segments", type=str, default="a,b,c", help="Сегменты через запятую")
    parser.add_argument("--creatives", type=str, default="emotional,rational,anti-marketing", help="Креативы через запятую")

    args = parser.parse_args()

    if args.set and args.campaign:
        segments = args.segments.split(",")
        creatives = args.creatives.split(",")
        results = generate_utm_set(args.campaign, segments, creatives, args.base_url)
        print_set(results, args.campaign)
    elif args.source and args.campaign:
        url = generate_utm(
            source=args.source,
            medium=args.medium,
            campaign=args.campaign,
            content=args.content,
            term=args.term,
            base_url=args.base_url,
        )
        print_single(url, args.source, args.medium, args.campaign, args.content, args.term)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
