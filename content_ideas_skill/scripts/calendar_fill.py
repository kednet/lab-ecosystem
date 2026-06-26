#!/usr/bin/env python3
"""
calendar_fill.py — сборка контент-плана.

Использование:
  python calendar_fill.py --month 2026-07 --posts-per-week 4 --mix "60%vk,30%blog,10%tg"
  python calendar_fill.py --month 2026-07 --start-date 2026-07-01

Вход:  data/ideas-bank.json + sources/seasonal-calendar.md
Выход: data/generated/<month>-content-plan.md

Правила:
  - Минимум 4 рубрики в месяц
  - Сезонные темы привязаны к датам
  - WL-книги — равномерно
  - После провокации — не провокация
  - Блог — 1-2 раза в неделю, VK — 3-5 раз

Статус: v0.1 — рабочий CLI-скелет с базовой логикой.
"""

import argparse
import json
import sys
from pathlib import Path
from datetime import datetime, timedelta
from typing import List, Dict, Any

# Force UTF-8 output on Windows
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass

SKILL_DIR = Path(__file__).parent.parent
DATA_DIR = SKILL_DIR / "data"
IDEAS_BANK = DATA_DIR / "ideas-bank.json"
GENERATED_DIR = DATA_DIR / "generated"


def load_ideas_bank() -> Dict[str, Any]:
    if not IDEAS_BANK.exists():
        return {"version": "1.0", "ideas": []}
    return json.loads(IDEAS_BANK.read_text(encoding="utf-8"))


def parse_mix(mix_str: str) -> Dict[str, float]:
    """Парсит строку микса '60%vk,30%blog,10%tg' → {'vk': 60, 'blog': 30, 'tg': 10}"""
    result = {}
    for part in mix_str.split(","):
        if "%" not in part:
            continue
        pct, target = part.split("%", 1)
        target = target.strip().lower()
        # Нормализуем tg → telegram
        if target in ("tg", "telegram"):
            target = "telegram"
        elif target in ("vk",):
            target = "vk"
        elif target in ("blog",):
            target = "blog"
        try:
            result[target] = float(pct)
        except ValueError:
            pass
    return result


def generate_calendar_stub(
    month: str,
    posts_per_week: int,
    mix: Dict[str, float],
    ideas: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """v0.1 — заглушка. Генерирует пустую сетку с датами и плейсхолдерами."""
    # Парсим месяц
    year, month_num = map(int, month.split("-"))

    # Сколько недель в месяце (примерно)
    days_in_month = 30  # для простоты
    weeks = days_in_month // 7

    calendar = []
    for week in range(weeks):
        for post_in_week in range(posts_per_week):
            # Пропускаем, если bank пуст
            if not ideas:
                # Генерируем заглушку
                calendar.append({
                    "date": f"{month}-{(week * 7 + post_in_week * 2 + 1):02d}",
                    "weekday": "среда",
                    "target": "vk",
                    "rubric": "[выбрать]",
                    "idea_id": None,
                    "title": "[TBD — выбрать из ideas-bank]",
                    "metric": "комменты",
                })
            else:
                # Берём следующую идею из банка
                idx = week * posts_per_week + post_in_week
                if idx < len(ideas):
                    idea = ideas[idx]
                    calendar.append({
                        "date": f"{month}-{(week * 7 + post_in_week * 2 + 1):02d}",
                        "weekday": "среда",
                        "target": idea.get("target", "vk"),
                        "rubric": idea.get("rubric", "?"),
                        "idea_id": idea.get("id"),
                        "title": idea.get("title", "?"),
                        "metric": idea.get("target_metric", "комменты"),
                    })
    return calendar


def render_calendar_md(month: str, calendar: List[Dict[str, Any]], mix: Dict[str, float]) -> str:
    """Рендер контент-плана в markdown."""
    lines = [
        f"# Контент-план: {month}",
        "",
        f"**Дата создания:** {datetime.now().strftime('%Y-%m-%d')}",
        f"**Микс:** {mix}",
        f"**Постов в неделю:** {len(calendar) // 4}",
        "",
        "---",
        "",
        "## Сетка",
        "",
        "| Дата | День | Target | Рубрика | Идея (id) | Заголовок | Цель |",
        "|---|---|---|---|---|---|---|",
    ]

    for entry in calendar:
        lines.append(
            f"| {entry['date']} | {entry['weekday']} | "
            f"{entry['target']} | {entry['rubric']} | "
            f"`{entry.get('idea_id', '—')}` | {entry['title']} | "
            f"{entry['metric']} |"
        )

    lines.extend([
        "",
        "---",
        "",
        "## Сводка по рубрикам",
        "",
    ])

    by_rubric = {}
    for e in calendar:
        r = e["rubric"]
        by_rubric[r] = by_rubric.get(r, 0) + 1

    for r, c in sorted(by_rubric.items(), key=lambda x: -x[1]):
        lines.append(f"- **{r}**: {c} постов")

    lines.extend([
        "",
        "## Сводка по target",
        "",
    ])

    by_target = {}
    for e in calendar:
        t = e["target"]
        by_target[t] = by_target.get(t, 0) + 1

    for t, c in sorted(by_target.items(), key=lambda x: -x[1]):
        lines.append(f"- **{t}**: {c} постов")

    lines.extend([
        "",
        "---",
        "",
        "## TODO",
        "",
        "- [ ] Проверить покрытие рубрик (минимум 4 разных в месяц)",
        "- [ ] Привязать сезонные темы к датам",
        "- [ ] Проверить, чтобы не было двух провокаций подряд",
        "- [ ] Согласовать с владелицей ЛЖ",
        "- [ ] Передать в `export_publisher.py`",
        "",
    ])

    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Сборка контент-плана")
    parser.add_argument("--month", type=str, required=True, help="Месяц (например, 2026-07)")
    parser.add_argument("--posts-per-week", type=int, default=4, help="Постов в неделю (default: 4)")
    parser.add_argument("--mix", type=str, default="70%vk,30%blog", help="Микс по площадкам")
    args = parser.parse_args()

    print(f"[calendar] Месяц: {args.month}")
    print(f"[calendar] Постов в неделю: {args.posts_per_week}")
    print(f"[calendar] Микс: {args.mix}")

    mix = parse_mix(args.mix)
    bank = load_ideas_bank()
    ideas = bank.get("ideas", [])

    print(f"[calendar] Идей в банке: {len(ideas)}")

    calendar = generate_calendar_stub(
        month=args.month,
        posts_per_week=args.posts_per_week,
        mix=mix,
        ideas=ideas,
    )

    # Сохраняем
    GENERATED_DIR.mkdir(parents=True, exist_ok=True)
    out_path = GENERATED_DIR / f"{args.month}-content-plan.md"
    md = render_calendar_md(args.month, calendar, mix)
    out_path.write_text(md, encoding="utf-8")
    print(f"[save] → {out_path}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
