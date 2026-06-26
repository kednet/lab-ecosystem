#!/usr/bin/env python3
"""
calc_unit_econ.py — расчёт unit-экономики для подписочной модели.

Использование:
    python calc_unit_econ.py --avg-check 590 --months 6 --margin 0.7 --cac 900
    python calc_unit_econ.py --interactive
"""

import argparse
import json


def calculate_unit_econ(avg_check, months, margin, cac, churn_rate=5.0):
    """
    Расчёт unit-экономики подписочной модели.

    avg_check: средний чек (₽/мес)
    months: средний срок подписки (мес)
    margin: маржинальность (0.0-1.0)
    cac: стоимость привлечения клиента (₽)
    churn_rate: месячный отток (%)
    """
    ltv_gross = avg_check * months
    ltv_net = ltv_gross * margin

    # С учётом оттока
    months_with_churn = 0
    cumulative_revenue = 0
    for m in range(1, int(months) + 1):
        retention = (1 - churn_rate / 100) ** (m - 1)
        monthly_revenue = avg_check * margin * retention
        cumulative_revenue += monthly_revenue
        months_with_churn = m

    ltv_with_churn = cumulative_revenue

    # ROI
    roi = (ltv_with_churn - cac) / cac if cac > 0 else 0
    payback_months = cac / (avg_check * margin) if (avg_check * margin) > 0 else 0

    # Допустимый CAC
    max_cac = ltv_with_churn / 3
    min_cac = ltv_with_churn / 5

    return {
        "avg_check": avg_check,
        "months_target": months,
        "margin": margin,
        "cac": cac,
        "churn_rate": churn_rate,
        "ltv_gross": ltv_gross,
        "ltv_net": ltv_net,
        "ltv_with_churn": ltv_with_churn,
        "roi": roi,
        "payback_months": payback_months,
        "max_cac": max_cac,
        "min_cac": min_cac,
        "is_profitable": roi > 0,
        "is_healthy": roi > 0.5,
    }


def print_report(result):
    """Печать отчёта."""
    print(f"\n{'='*60}")
    print(f"💰 UNIT-ЭКОНОМИКА")
    print(f"{'='*60}\n")

    print(f"Средний чек:           {result['avg_check']} ₽/мес")
    print(f"Целевой срок:          {result['months_target']} мес")
    print(f"Маржинальность:        {result['margin']*100:.0f}%")
    print(f"Месячный отток:        {result['churn_rate']:.1f}%")
    print(f"Стоимость привлечения: {result['cac']} ₽\n")

    print(f"{'Метрика':<30} {'Значение':<15}")
    print(f"{'-'*45}")
    print(f"{'LTV (gross)':<30} {result['ltv_gross']:.0f} ₽")
    print(f"{'LTV (net, с маржой)':<30} {result['ltv_net']:.0f} ₽")
    print(f"{'LTV (с учётом оттока)':<30} {result['ltv_with_churn']:.0f} ₽")
    print(f"{'ROI':<30} {result['roi']*100:.1f}%")
    print(f"{'Окупаемость':<30} {result['payback_months']:.1f} мес")
    print(f"{'Макс. CAC (соотношение 3:1)':<30} {result['max_cac']:.0f} ₽")
    print(f"{'Мин. CAC (соотношение 5:1)':<30} {result['min_cac']:.0f} ₽\n")

    if result["is_healthy"]:
        print("✅ ЗДОРОВАЯ ЭКОНОМИКА: ROI > 50%")
    elif result["is_profitable"]:
        print("⚠️ НА ГРАНИ: ROI > 0%, но < 50%")
    else:
        print("❌ УБЫТОЧНО: ROI < 0%")

    if result["cac"] > result["max_cac"]:
        print(f"\n🚨 ВНИМАНИЕ: ваш CAC ({result['cac']} ₽) выше допустимого ({result['max_cac']:.0f} ₽)")
        print(f"   Нужно либо снизить CAC, либо увеличить LTV")
    elif result["cac"] < result["min_cac"]:
        print(f"\n💡 ВОЗМОЖНОСТЬ: ваш CAC ({result['cac']} ₽) ниже минимума ({result['min_cac']:.0f} ₽)")
        print(f"   Можно масштабировать рекламу")


def main():
    parser = argparse.ArgumentParser(description="Калькулятор unit-экономики")
    parser.add_argument("--avg-check", type=float, default=590, help="Средний чек (₽/мес)")
    parser.add_argument("--months", type=float, default=6, help="Средний срок подписки (мес)")
    parser.add_argument("--margin", type=float, default=0.7, help="Маржинальность (0.0-1.0)")
    parser.add_argument("--cac", type=float, default=900, help="Стоимость привлечения (₽)")
    parser.add_argument("--churn", type=float, default=5.0, help="Месячный отток (%)")
    parser.add_argument("--json", action="store_true", help="Вывод в JSON")

    args = parser.parse_args()

    result = calculate_unit_econ(
        avg_check=args.avg_check,
        months=args.months,
        margin=args.margin,
        cac=args.cac,
        churn_rate=args.churn,
    )

    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        print_report(result)


if __name__ == "__main__":
    main()
