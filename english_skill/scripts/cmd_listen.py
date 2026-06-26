"""
cmd_listen.py — рекомендации аудио для текущей/указанной недели.

Фильтрует sources.yaml по полю `weeks: [N,M]` (содержит ли week_num).
"""
from _english_common import fix_utf8, ensure_dirs, print_header, print_section, load_yaml, DATA_DIR, resolve_week, get_total_weeks


def _filter_for_week(sources: list, week_num: int) -> list:
    """Возвращает источники, рекомендованные для данной недели."""
    out = []
    for s in sources:
        weeks = s.get("weeks", [])
        if week_num in weeks:
            out.append(s)
    return out


def run(args) -> int:
    fix_utf8()
    ensure_dirs()

    week_num = resolve_week(getattr(args, "week", None))
    sources = load_yaml(DATA_DIR / "sources.yaml").get("sources", [])

    matching = _filter_for_week(sources, week_num)

    if not matching:
        print(f"⚠️  Для недели {week_num} нет рекомендованных аудио-источников.")
        print(f"Доступно всего: {len(sources)} источников (см. data/sources.yaml).")
        return 0

    print_header(f"🎧 Аудио для Week {week_num}")
    print(f"Найдено: {len(matching)} источник(ов)")
    print()

    total_min = 0
    for i, s in enumerate(matching, 1):
        print(f"### {i}. {s['title']}")
        print(f"**Источник:** {s.get('source', '—')} | "
              f"**Длительность:** ~{s.get('duration_min', '?')} мин | "
              f"**Уровень:** {s.get('level', 'B1')}")
        print()
        print(f"🔗 **URL:** {s.get('url', '#')}")
        if s.get("transcript_url"):
            print(f"📄 **Transcript:** {s['transcript_url']}")
        print()

        if s.get("summary"):
            print(f"_{s['summary']}_")
            print()

        if s.get("vocab"):
            print("**🎯 Vocab для этого эпизода:**")
            print()
            for v in s["vocab"]:
                print(f"- **{v}**")
            print()

        if s.get("comprehension_questions"):
            print("**❓ Comprehension questions (ответь устно или письменно):**")
            print()
            for j, q in enumerate(s["comprehension_questions"], 1):
                print(f"{j}. *{q['q']}*")
                if q.get("sample_answer"):
                    print(f"   - 💡 Sample: _{q['sample_answer']}_")
            print()

        total_min += s.get("duration_min", 0)
        print("---")
        print()

    print(f"## Итого")
    print()
    print(f"⏱ Общая длительность: ~{total_min} мин (~{round(total_min/60, 1)} ч)")
    print()
    print("## Как заниматься")
    print()
    print("1. **Первое прослушивание** — слушай без субтитров, пойми общий смысл")
    print("2. **Второе прослушивание** — с transcript, выпиши незнакомые слова")
    print("3. **Comprehension questions** — ответь устно (это и есть speaking-практика!)")
    print("4. **Vocab** — добавь 3-5 новых слов в свой список")
    print()
    print(f"📂 Все источники: `data/sources.yaml` (всего {len(sources)}, "
          f"доступно недель: 1-{get_total_weeks()})")
    return 0