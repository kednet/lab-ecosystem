#!/usr/bin/env python3
"""
cpl_benchmark.py — выгрузка бенчмарков по нише и каналу.

Использование:
    python cpl_benchmark.py --channel ok
    python cpl_benchmark.py --segment b
    python cpl_benchmark.py --all
"""

import argparse
import json


# Бенчмарки из data/benchmarks_ru_2026.md
BENCHMARKS = {
    "ok": {
        "name": "ОК Реклама",
        "cpl_magnet": (40, 120),
        "cpl_subscription": (400, 1000),
        "ctr": (2.0, 5.0),
        "conv_landing": (4.0, 8.0),
        "best_segment": "B, C",
        "budget_min": 5000,
    },
    "dzen_organic": {
        "name": "Дзен (органика)",
        "cpl_magnet": (0, 50),
        "cpl_subscription": (300, 700),
        "ctr": (30.0, 50.0),
        "conv_landing": (4.0, 8.0),
        "best_segment": "B, C",
        "budget_min": 0,
    },
    "dzen_promo": {
        "name": "Дзен (продвижение)",
        "cpl_magnet": (80, 200),
        "cpl_subscription": (400, 1000),
        "ctr": (2.0, 4.0),
        "conv_landing": (4.0, 8.0),
        "best_segment": "B, C",
        "budget_min": 5000,
    },
    "vk": {
        "name": "VK Реклама (new)",
        "cpl_magnet": (80, 250),
        "cpl_subscription": (600, 1500),
        "ctr": (1.0, 3.0),
        "conv_landing": (3.0, 6.0),
        "best_segment": "A, B",
        "budget_min": 5000,
    },
    "tg_micro": {
        "name": "Посевы TG (микро)",
        "cpl_magnet": (30, 100),
        "cpl_subscription": (400, 800),
        "ctr": (1.5, 4.0),
        "conv_landing": (4.0, 10.0),
        "best_segment": "A, B",
        "budget_min": 3000,
    },
    "yandex_search": {
        "name": "Я.Директ (поиск)",
        "cpl_magnet": (200, 500),
        "cpl_subscription": (1200, 2500),
        "ctr": (5.0, 12.0),
        "conv_landing": (5.0, 12.0),
        "best_segment": "A, B",
        "budget_min": 10000,
    },
    "yandex_rsa": {
        "name": "Я.Директ (РСЯ)",
        "cpl_magnet": (60, 180),
        "cpl_subscription": (500, 1200),
        "ctr": (0.8, 1.8),
        "conv_landing": (2.0, 5.0),
        "best_segment": "A, B",
        "budget_min": 5000,
    },
    "avito": {
        "name": "Авито (услуги)",
        "cpl_magnet": (150, 500),
        "cpl_subscription": (800, 2000),
        "ctr": (3.0, 7.0),
        "conv_landing": (4.0, 10.0),
        "best_segment": "B, C",
        "budget_min": 3000,
    },
    "webinar": {
        "name": "Вебинары (GetCourse)",
        "cpl_magnet": (80, 250),
        "cpl_subscription": (1000, 3000),
        "ctr": (0, 0),
        "conv_landing": (15.0, 25.0),
        "best_segment": "B, C",
        "budget_min": 10000,
    },
}


# Бенчмарки по сегментам
SEGMENT_BENCHMARKS = {
    "A": {
        "name": "Сегмент A: 25-34, молодые мамы/карьеристки",
        "share": "25%",
        "priority": 2,
        "best_channels": ["vk", "tg_micro", "yappy", "yandex_search", "dzen_organic"],
        "avg_check": (290, 590),
    },
    "B": {
        "name": "Сегмент B: 35-44, на перекрёстке ⭐",
        "share": "35%",
        "priority": 1,
        "best_channels": ["ok", "dzen_organic", "dzen_promo", "vk", "tg_micro", "yandex_search"],
        "avg_check": (590, 990),
    },
    "C": {
        "name": "Сегмент C: 45-55, опустевшее гнездо",
        "share": "25%",
        "priority": 3,
        "best_channels": ["ok", "dzen_organic", "yandex_search", "avito", "vk"],
        "avg_check": (590, 590),
    },
    "D": {
        "name": "Сегмент D: 55-65, активная пенсия (опц.)",
        "share": "10%",
        "priority": 4,
        "best_channels": ["ok", "dzen_organic", "avito"],
        "avg_check": (290, 290),
    },
}


def print_channel(channel_key):
    """Печать бенчмарка одного канала."""
    ch = BENCHMARKS[channel_key]
    print(f"\n📺 {ch['name']}")
    print(f"{'='*60}")
    print(f"CPL (магнит):     {ch['cpl_magnet'][0]}-{ch['cpl_magnet'][1]} ₽")
    print(f"CPL (подписка):   {ch['cpl_subscription'][0]}-{ch['cpl_subscription'][1]} ₽")
    print(f"CTR:              {ch['ctr'][0]}-{ch['ctr'][1]}%")
    print(f"Конверсия лендинга: {ch['conv_landing'][0]}-{ch['conv_landing'][1]}%")
    print(f"Лучший сегмент:   {ch['best_segment']}")
    print(f"Мин. бюджет:      {ch['budget_min']} ₽/мес")


def print_segment(seg_key):
    """Печать бенчмарка одного сегмента."""
    seg = SEGMENT_BENCHMARKS[seg_key]
    print(f"\n🎯 {seg['name']}")
    print(f"{'='*60}")
    print(f"Доля:             {seg['share']}")
    print(f"Приоритет:        {seg['priority']}")
    print(f"Средний чек:      {seg['avg_check'][0]}-{seg['avg_check'][1]} ₽/мес")
    print(f"Лучшие каналы:")
    for ch in seg["best_channels"]:
        ch_name = BENCHMARKS[ch]["name"]
        ch_cpl = BENCHMARKS[ch]["cpl_subscription"]
        print(f"  - {ch_name} (CPL {ch_cpl[0]}-{ch_cpl[1]} ₽)")


def main():
    parser = argparse.ArgumentParser(description="Бенчмарки CPL/CTR по каналам и сегментам")
    parser.add_argument("--channel", type=str, help="Канал (ok, vk, dzen_organic, ...)")
    parser.add_argument("--segment", type=str, help="Сегмент (A, B, C, D)")
    parser.add_argument("--all", action="store_true", help="Все каналы и сегменты")
    parser.add_argument("--json", action="store_true", help="Вывод в JSON")

    args = parser.parse_args()

    if args.json:
        if args.channel:
            print(json.dumps({args.channel: BENCHMARKS.get(args.channel, {})}, indent=2, ensure_ascii=False))
        elif args.segment:
            print(json.dumps({args.segment: SEGMENT_BENCHMARKS.get(args.segment, {})}, indent=2, ensure_ascii=False))
        else:
            print(json.dumps({"channels": BENCHMARKS, "segments": SEGMENT_BENCHMARKS}, indent=2, ensure_ascii=False))
        return

    if args.channel:
        if args.channel in BENCHMARKS:
            print_channel(args.channel)
        else:
            print(f"❌ Неизвестный канал: {args.channel}")
            print(f"Доступные: {', '.join(BENCHMARKS.keys())}")
        return

    if args.segment:
        if args.segment in SEGMENT_BENCHMARKS:
            print_segment(args.segment)
        else:
            print(f"❌ Неизвестный сегмент: {args.segment}")
            print(f"Доступные: {', '.join(SEGMENT_BENCHMARKS.keys())}")
        return

    if args.all:
        print("\n📺 ВСЕ КАНАЛЫ")
        print("="*60)
        for key in BENCHMARKS:
            print_channel(key)

        print("\n\n🎯 ВСЕ СЕГМЕНТЫ")
        print("="*60)
        for key in SEGMENT_BENCHMARKS:
            print_segment(key)
        return

    parser.print_help()


if __name__ == "__main__":
    main()
