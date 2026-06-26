#!/usr/bin/env python3
"""
segment_recommender.py — подбор каналов × сегментов на основе цели.

Использование:
    python segment_recommender.py --goal 50 --avg-check 590
    python segment_recommender.py --goal 100 --avg-check 590 --priority conversion
    python segment_recommender.py --segment b --goal 30
"""

import argparse


# Бенчмарки (импорт из cpl_benchmark)
SEGMENTS = {
    "A": {
        "name": "Сегмент A: 25-34, молодые мамы/карьеристки",
        "share": 25,
        "priority": 2,
        "best_channels": ["vk", "tg_micro", "yappy", "yandex_search", "dzen_organic"],
        "cpl_subscription": (600, 1500),
        "avg_check": (290, 590),
        "ltv_months": 4,
    },
    "B": {
        "name": "Сегмент B: 35-44, на перекрёстке ⭐",
        "share": 35,
        "priority": 1,
        "best_channels": ["ok", "dzen_organic", "dzen_promo", "vk", "tg_micro", "yandex_search"],
        "cpl_subscription": (500, 1000),
        "avg_check": (590, 990),
        "ltv_months": 6,
    },
    "C": {
        "name": "Сегмент C: 45-55, опустевшее гнездо",
        "share": 25,
        "priority": 3,
        "best_channels": ["ok", "dzen_organic", "yandex_search", "avito", "vk"],
        "cpl_subscription": (700, 1500),
        "avg_check": (590, 590),
        "ltv_months": 8,
    },
    "D": {
        "name": "Сегмент D: 55-65, активная пенсия",
        "share": 10,
        "priority": 4,
        "best_channels": ["ok", "dzen_organic", "avito"],
        "cpl_subscription": (800, 1500),
        "avg_check": (290, 290),
        "ltv_months": 10,
    },
}


CHANNEL_NAMES = {
    "vk": "VK Реклама",
    "ok": "ОК Реклама",
    "dzen_organic": "Дзен (органика)",
    "dzen_promo": "Дзен (продвижение)",
    "tg_micro": "Посевы TG (микро)",
    "tg_medium": "Посевы TG (средние)",
    "yandex_search": "Я.Директ (поиск)",
    "yandex_rsa": "Я.Директ (РСЯ)",
    "yappy": "Yappy",
    "avito": "Авито",
    "webinar": "Вебинар",
}


def recommend_channels(goal, avg_check, priority="balanced"):
    """Подбор каналов под цель."""
    distribution = {}
    total_weight = 0

    # Расчёт приоритетов
    for seg_key, seg in SEGMENTS.items():
        cpl_min, cpl_max = seg["cpl_subscription"]
        cpl_avg = (cpl_min + cpl_max) / 2

        # Допустимый CAC
        ltv = avg_check * seg["ltv_months"]
        max_cac = ltv / 3

        # Подходит ли сегмент
        if cpl_avg <= max_cac:
            # Подходит — добавляем в распределение
            seg_goal = goal * (seg["share"] / 100)
            distribution[seg_key] = {
                "segment": seg,
                "segment_goal": int(seg_goal),
                "cpl": cpl_avg,
                "ltv": ltv,
                "max_cac": max_cac,
                "budget": int(seg_goal * cpl_avg),
            }
            total_weight += seg["priority"]

    # Нормализация
    if total_weight == 0:
        return None

    # Корректировка по приоритету
    if priority == "conversion":
        # Только лучшие каналы
        for seg_key in list(distribution.keys()):
            if distribution[seg_key]["segment"]["priority"] > 2:
                del distribution[seg_key]
    elif priority == "ltv":
        # Только длинный LTV
        for seg_key in list(distribution.keys()):
            if distribution[seg_key]["segment"]["ltv_months"] < 6:
                del distribution[seg_key]

    return distribution


def print_recommendation(goal, avg_check, distribution):
    """Печать рекомендации."""
    print(f"\n{'='*60}")
    print(f"🎯 РЕКОМЕНДАЦИЯ ПО КАНАЛАМ ДЛЯ {goal} ПОДПИСОК")
    print(f"{'='*60}\n")

    if not distribution:
        print("❌ Не удалось подобрать каналы. Проверьте параметры.")
        return

    print(f"Средний чек: {avg_check} ₽/мес\n")

    print(f"{'Сегмент':<35} {'Цель':<8} {'Бюджет':<12} {'Каналы'}")
    print(f"{'-'*100}")

    total_budget = 0
    total_goal = 0

    for seg_key, data in distribution.items():
        seg = data["segment"]
        channels = ", ".join([CHANNEL_NAMES.get(c, c) for c in seg["best_channels"][:3]])
        print(f"{seg['name']:<35} {data['segment_goal']:<8} {data['budget']:<12} {channels}")
        total_budget += data["budget"]
        total_goal += data["segment_goal"]

    print(f"{'-'*100}")
    print(f"{'ИТОГО':<35} {total_goal:<8} {total_budget:<12}\n")

    # Ожидаемый ROI
    avg_ltv = sum(d["ltv"] for d in distribution.values()) / len(distribution)
    expected_revenue = total_goal * avg_ltv
    expected_roi = expected_revenue / total_budget if total_budget > 0 else 0
    print(f"💰 Ожидаемая выручка: {expected_revenue:.0f} ₽")
    print(f"📈 Ожидаемый ROI: {expected_roi:.2f}x")


def main():
    parser = argparse.ArgumentParser(description="Рекомендатор каналов по сегментам")
    parser.add_argument("--goal", type=int, required=True, help="Цель (подписки/мес)")
    parser.add_argument("--avg-check", type=int, default=590, help="Средний чек (₽/мес)")
    parser.add_argument("--priority", type=str, default="balanced",
                        choices=["balanced", "conversion", "ltv"],
                        help="Приоритет (balanced, conversion, ltv)")
    parser.add_argument("--segment", type=str, help="Только один сегмент (A, B, C, D)")

    args = parser.parse_args()

    if args.segment:
        # Только один сегмент
        if args.segment not in SEGMENTS:
            print(f"❌ Неизвестный сегмент: {args.segment}")
            return

        seg = SEGMENTS[args.segment]
        seg_goal = args.goal

        print(f"\n🎯 {seg['name']}")
        print(f"{'='*60}\n")
        print(f"Доля: {seg['share']}%")
        print(f"Целевой LTV: {args.avg_check * seg['ltv_months']} ₽")
        print(f"CPL подписки: {seg['cpl_subscription'][0]}-{seg['cpl_subscription'][1]} ₽")
        print(f"Средний чек: {seg['avg_check'][0]}-{seg['avg_check'][1]} ₽/мес\n")
        print(f"Лучшие каналы:")

        cpl_min, cpl_max = seg["cpl_subscription"]
        cpl_avg = (cpl_min + cpl_max) / 2

        for ch in seg["best_channels"]:
            ch_name = CHANNEL_NAMES.get(ch, ch)
            ch_cpl = ""
            if ch == "vk":
                ch_cpl = "600-1500 ₽"
            elif ch == "ok":
                ch_cpl = "400-1000 ₽"
            elif ch == "dzen_organic":
                ch_cpl = "300-700 ₽"
            elif ch == "dzen_promo":
                ch_cpl = "400-1000 ₽"
            elif ch == "tg_micro":
                ch_cpl = "400-800 ₽"
            elif ch == "yandex_search":
                ch_cpl = "1200-2500 ₽"
            elif ch == "yappy":
                ch_cpl = "500-1500 ₽"
            elif ch == "avito":
                ch_cpl = "800-2000 ₽"
            print(f"  - {ch_name} (CPL {ch_cpl})")

        budget_min = seg_goal * cpl_min
        budget_max = seg_goal * cpl_max
        print(f"\nБюджет на {seg_goal} подписок: {budget_min:.0f}-{budget_max:.0f} ₽")
    else:
        distribution = recommend_channels(args.goal, args.avg_check, args.priority)
        print_recommendation(args.goal, args.avg_check, distribution)


if __name__ == "__main__":
    main()
