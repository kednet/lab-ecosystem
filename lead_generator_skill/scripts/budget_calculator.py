#!/usr/bin/env python3
"""
budget_calculator.py — расчёт бюджета от цели.

Использование:
    python budget_calculator.py --goal 100 --channel ok --avg-check 590
    python budget_calculator.py --goal 50 --avg-check 590 --target-months 3
"""

import argparse
import json
from pathlib import Path


# Бенчмарки из data/benchmarks_ru_2026.md
BENCHMARKS = {
    "ok": {"cpl_subscription": (400, 1000), "name": "ОК Реклама"},
    "dzen_organic": {"cpl_subscription": (300, 700), "name": "Дзен (органика)"},
    "dzen_promo": {"cpl_subscription": (400, 1000), "name": "Дзен (продвижение)"},
    "vk": {"cpl_subscription": (600, 1500), "name": "VK Реклама"},
    "tg_micro": {"cpl_subscription": (400, 800), "name": "Посевы TG (микро)"},
    "tg_medium": {"cpl_subscription": (600, 1200), "name": "Посевы TG (средние)"},
    "tg_large": {"cpl_subscription": (1000, 2500), "name": "Посевы TG (крупные)"},
    "yandex_search": {"cpl_subscription": (1200, 2500), "name": "Я.Директ (поиск)"},
    "yandex_rsa": {"cpl_subscription": (500, 1200), "name": "Я.Директ (РСЯ)"},
    "yappy": {"cpl_subscription": (500, 1500), "name": "Yappy"},
    "avito": {"cpl_subscription": (800, 2000), "name": "Авито"},
    "webinar": {"cpl_subscription": (1000, 3000), "name": "Вебинар"},
}


def calculate_budget(goal, channel, avg_check, target_months=6, ltv_multiplier=None):
    """Расчёт бюджета от цели."""
    if channel not in BENCHMARKS:
        raise ValueError(f"Неизвестный канал: {channel}. Доступные: {list(BENCHMARKS.keys())}")

    benchmark = BENCHMARKS[channel]
    cpl_min, cpl_max = benchmark["cpl_subscription"]
    cpl_avg = (cpl_min + cpl_max) // 2

    # LTV
    ltv = avg_check * target_months
    if ltv_multiplier:
        ltv *= ltv_multiplier

    # Допустимый CAC (1/3 от LTV)
    max_cac = ltv / 3

    # Бюджет
    budget_min = goal * cpl_min
    budget_max = goal * cpl_max
    budget_avg = goal * cpl_avg

    return {
        "channel": benchmark["name"],
        "channel_key": channel,
        "goal": goal,
        "avg_check": avg_check,
        "target_months": target_months,
        "ltv": ltv,
        "max_cac": max_cac,
        "cpl_range": (cpl_min, cpl_max),
        "budget_min": budget_min,
        "budget_max": budget_max,
        "budget_avg": budget_avg,
        "budget_per_month_min": budget_min,
        "budget_per_month_max": budget_max,
        "roi_expected": (ltv * goal) / budget_avg if budget_avg else 0,
    }


def calculate_multi_channel(goal, avg_check, target_months, channels_distribution):
    """
    Расчёт бюджета с разбивкой по каналам.
    channels_distribution: {"ok": 0.35, "dzen_promo": 0.25, ...}
    """
    total_ltv = avg_check * target_months
    max_cac = total_ltv / 3

    result = {
        "total_goal": goal,
        "avg_check": avg_check,
        "target_months": target_months,
        "ltv": total_ltv,
        "max_cac": max_cac,
        "channels": [],
        "total_budget_min": 0,
        "total_budget_max": 0,
        "total_budget_avg": 0,
    }

    for channel, share in channels_distribution.items():
        channel_goal = int(goal * share)
        calc = calculate_budget(channel_goal, channel, avg_check, target_months)
        calc["share"] = share
        calc["channel_goal"] = channel_goal
        result["channels"].append(calc)
        result["total_budget_min"] += calc["budget_min"]
        result["total_budget_max"] += calc["budget_max"]
        result["total_budget_avg"] += calc["budget_avg"]

    if result["total_budget_avg"] > 0:
        result["expected_revenue"] = goal * total_ltv
        result["expected_roi"] = result["expected_revenue"] / result["total_budget_avg"]

    return result


def print_report(result):
    """Печать отчёта."""
    if "channels" in result:
        # Мультиканальный
        print(f"\n{'='*60}")
        print(f"📊 МУЛЬТИКАНАЛЬНЫЙ РАСЧЁТ БЮДЖЕТА")
        print(f"{'='*60}\n")
        print(f"Цель: {result['total_goal']} подписок")
        print(f"Средний чек: {result['avg_check']} ₽/мес")
        print(f"Целевой срок подписки: {result['target_months']} мес")
        print(f"LTV клиента: {result['ltv']:.0f} ₽")
        print(f"Допустимый CAC: {result['max_cac']:.0f} ₽\n")
        print(f"{'Канал':<25} {'Доля':<8} {'Цель':<8} {'CPL':<15} {'Бюджет':<15}")
        print(f"{'-'*70}")

        for ch in result["channels"]:
            print(f"{ch['channel']:<25} {ch['share']*100:.0f}%     {ch['channel_goal']:<8} "
                  f"{ch['cpl_range'][0]}-{ch['cpl_range'][1]} ₽  "
                  f"{ch['budget_min']:.0f}-{ch['budget_max']:.0f} ₽")

        print(f"{'-'*70}")
        print(f"{'ИТОГО':<25} {'':<8} {result['total_goal']:<8} {'':<15} "
              f"{result['total_budget_min']:.0f}-{result['total_budget_max']:.0f} ₽\n")
        if 'expected_roi' in result:
            print(f"💰 Ожидаемая выручка: {result['expected_revenue']:.0f} ₽")
            print(f"📈 Ожидаемый ROI: {result['expected_roi']:.2f}x")
    else:
        # Один канал
        print(f"\n{'='*60}")
        print(f"📊 РАСЧЁТ БЮДЖЕТА ДЛЯ КАНАЛА: {result['channel']}")
        print(f"{'='*60}\n")
        print(f"Цель: {result['goal']} подписок")
        print(f"Средний чек: {result['avg_check']} ₽/мес")
        print(f"Целевой срок: {result['target_months']} мес")
        print(f"LTV клиента: {result['ltv']:.0f} ₽")
        print(f"Допустимый CAC: {result['max_cac']:.0f} ₽\n")
        print(f"CPL подписки: {result['cpl_range'][0]}-{result['cpl_range'][1]} ₽")
        print(f"Бюджет (мин): {result['budget_min']:.0f} ₽")
        print(f"Бюджет (макс): {result['budget_max']:.0f} ₽")
        print(f"Бюджет (средний): {result['budget_avg']:.0f} ₽")
        print(f"Ожидаемый ROI: {result['roi_expected']:.2f}x")


def main():
    parser = argparse.ArgumentParser(description="Калькулятор бюджета от цели")
    parser.add_argument("--goal", type=int, help="Цель (кол-во подписок)")
    parser.add_argument("--channel", type=str, help="Канал (ok, vk, dzen_promo, ...)")
    parser.add_argument("--avg-check", type=int, default=590, help="Средний чек (₽/мес)")
    parser.add_argument("--target-months", type=int, default=6, help="Целевой срок подписки (мес)")
    parser.add_argument("--multi", type=str, help="JSON с распределением каналов")
    parser.add_argument("--json", action="store_true", help="Вывод в JSON")

    args = parser.parse_args()

    if args.multi:
        # Мультиканальный режим
        try:
            channels_distribution = json.loads(args.multi)
        except json.JSONDecodeError:
            print("Ошибка: --multi должен быть валидным JSON")
            return

        result = calculate_multi_channel(args.goal, args.avg_check, args.target_months, channels_distribution)
    elif args.goal and args.channel:
        # Один канал
        result = calculate_budget(args.goal, args.channel, args.avg_check, args.target_months)
    else:
        parser.print_help()
        return

    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        print_report(result)


if __name__ == "__main__":
    main()
