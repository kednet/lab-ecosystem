#!/usr/bin/env python3
"""
compliance_check.py — проверка креатива на стоп-слова ФАС и compliance-риски.

Использование:
    python compliance_check.py "Текст креатива..."
    python compliance_check.py --file creative.txt
    python compliance_check.py --stdin
"""

import argparse
import re
import sys


# Стоп-слова и паттерны ФАС
STOP_WORDS_FAS = {
    "100%": "Обещание 100% результата (запрещено ФАС)",
    "гарантированно": "Гарантия результата (запрещено ФАС)",
    "гарантирован": "Гарантия результата (запрещено ФАС)",
    "гарантия": "Гарантия результата (запрещено ФАС)",
    "точно поможет": "Обещание результата (запрещено ФАС)",
    "обязательно сбудется": "Обещание результата (запрещено ФАС)",
    "мгновенный результат": "Обещание быстрого результата (запрещено ФАС)",
    "за 1 день": "Обещание быстрого результата (запрещено ФАС)",
    "навсегда": "Абсолютное обещание (запрещено ФАС)",
    "навсегда избавиться": "Абсолютное обещание (запрещено ФАС)",
    "вылечит": "Медицинское обещание (запрещено в нише психологии)",
    "излечение": "Медицинское обещание (запрещено в нише психологии)",
    "лечение": "Медицинский термин (запрещено в нише психологии)",
    "терапия": "Медицинский термин (запрещено в нише психологии)",
    "лучший в России": "Преувеличение (запрещено ФАС)",
    "единственный метод": "Преувеличение (запрещено ФАС)",
    "без риска": "Вводит в заблуждение (запрещено ФАС)",
    "заработай миллион": "Обещание дохода (запрещено ФАС)",
    "доход от": "Обещание дохода (запрещено ФАС)",
    "пассивный доход": "Обещание дохода (запрещено ФАС)",
}


# Обязательные элементы для ниши «психология/саморазвитие»
REQUIRED_DISCLAIMERS = {
    "информационный характер": "Рекомендуется для ниши психологии/саморазвития",
    "результат индивидуален": "Рекомендуется для ниши психологии/саморазвития",
    "не является медицинской": "Рекомендуется для ниши психологии/саморазвития",
    "не является психотерапевтической": "Рекомендуется для ниши психологии/саморазвития",
}


# Обязательные элементы для рекламы
REQUIRED_AD_MARKING = {
    "Реклама": "Требуется пометка 'Реклама' (закон 347-ФЗ)",
    "ИНН": "Требуется ИНН рекламодателя",
    "ERID": "Требуется токен ERID (маркировка рекламы)",
}


def check_compliance(text, is_paid_ad=False, is_psychology_niche=False):
    """Проверка текста на compliance."""
    issues = []
    warnings = []
    recommendations = []

    text_lower = text.lower()

    # 1. Проверка стоп-слов ФАС
    for word, reason in STOP_WORDS_FAS.items():
        if word.lower() in text_lower:
            issues.append(f"❌ СТОП-СЛОВО: «{word}» — {reason}")

    # 2. Проверка обязательных дисклеймеров (для ниши психологии)
    if is_psychology_niche:
        for phrase, reason in REQUIRED_DISCLAIMERS.items():
            if phrase.lower() not in text_lower:
                warnings.append(f"⚠️ ДИСКЛЕЙМЕР: отсутствует «{phrase}» — {reason}")

    # 3. Проверка маркировки (для платной рекламы)
    if is_paid_ad:
        for marker, reason in REQUIRED_AD_MARKING.items():
            if marker.lower() not in text_lower:
                issues.append(f"❌ МАРКИРОВКА: отсутствует «{marker}» — {reason}")

    # 4. Дополнительные рекомендации
    if "бесплатно" in text_lower and "без подписки" not in text_lower:
        recommendations.append("💡 Рекомендация: добавьте «без подписки, без оплаты» — усилит доверие")

    if "скачай" not in text_lower and "получи" not in text_lower and "узнай" not in text_lower:
        recommendations.append("💡 Рекомендация: добавьте глагол действия (скачай, получи, узнай)")

    return {
        "issues": issues,
        "warnings": warnings,
        "recommendations": recommendations,
        "score": max(0, 100 - len(issues) * 20 - len(warnings) * 5),
    }


def print_report(text, result):
    """Печать отчёта."""
    print(f"\n{'='*60}")
    print(f"📋 COMPLIANCE CHECK")
    print(f"{'='*60}\n")
    print(f"Длина текста: {len(text)} знаков")
    print(f"Скоринг: {result['score']}/100\n")

    if result["score"] >= 80:
        print("✅ ОТЛИЧНО: креатив проходит compliance")
    elif result["score"] >= 60:
        print("⚠️ ХОРОШО: есть небольшие замечания")
    elif result["score"] >= 40:
        print("❌ ПЛОХО: нужно исправить")
    else:
        print("🚨 КРИТИЧНО: нельзя запускать")

    if result["issues"]:
        print(f"\n🚨 КРИТИЧЕСКИЕ ПРОБЛЕМЫ ({len(result['issues'])}):")
        for issue in result["issues"]:
            print(f"  {issue}")

    if result["warnings"]:
        print(f"\n⚠️ ПРЕДУПРЕЖДЕНИЯ ({len(result['warnings'])}):")
        for warning in result["warnings"]:
            print(f"  {warning}")

    if result["recommendations"]:
        print(f"\n💡 РЕКОМЕНДАЦИИ ({len(result['recommendations'])}):")
        for rec in result["recommendations"]:
            print(f"  {rec}")

    if not (result["issues"] or result["warnings"] or result["recommendations"]):
        print("\n✅ Всё отлично! Креатив готов к запуску.")


def main():
    parser = argparse.ArgumentParser(description="Проверка креатива на compliance")
    parser.add_argument("text", nargs="?", help="Текст креатива")
    parser.add_argument("--file", type=str, help="Путь к файлу с текстом")
    parser.add_argument("--stdin", action="store_true", help="Читать из stdin")
    parser.add_argument("--paid-ad", action="store_true", help="Это платная реклама (нужна маркировка)")
    parser.add_argument("--psychology", action="store_true", help="Ниша психологии/саморазвития")
    parser.add_argument("--json", action="store_true", help="Вывод в JSON")

    args = parser.parse_args()

    # Получить текст
    if args.file:
        try:
            with open(args.file, "r", encoding="utf-8") as f:
                text = f.read()
        except FileNotFoundError:
            print(f"❌ Файл не найден: {args.file}")
            sys.exit(1)
    elif args.stdin:
        text = sys.stdin.read()
    elif args.text:
        text = args.text
    else:
        parser.print_help()
        sys.exit(1)

    result = check_compliance(text, is_paid_ad=args.paid_ad, is_psychology_niche=args.psychology)

    if args.json:
        import json
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print_report(text, result)

    # Exit code
    if result["issues"]:
        sys.exit(1)
    else:
        sys.exit(0)


if __name__ == "__main__":
    main()
