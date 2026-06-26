"""
cmd_week.py — управление неделей (show / next / --week=N).
"""
from _english_common import fix_utf8, ensure_dirs, print_header, print_section, get_week_data, get_total_weeks, get_total_days_in_week, confirm
import state


def _show_week(week_num: int) -> None:
    """Печатает содержимое указанной недели."""
    week = get_week_data(week_num)
    if not week:
        print(f"❌ Неделя {week_num} не найдена (всего {get_total_weeks()}).")
        return

    progress = state.load_progress()
    lessons_in_week = [l for l in progress.get("lessons_done", []) if l.startswith(f"{week_num}_")]
    is_current = progress["current_week"] == week_num

    print_header(f"Week {week_num}: {week.get('theme', '(no theme)')}")
    if is_current:
        print("⭐ ТЕКУЩАЯ НЕДЕЛЯ")
    print(f"Grammar focus: {week.get('grammar_focus', '—')}")
    if week.get("block"):
        print(f"Block: {week['block']}")
    if week.get("why"):
        print()
        print(f"💡 Почему: {week['why']}")
    print()
    print(f"📅 Дней: {get_total_days_in_week(week_num)} | "
          f"Пройдено: {len(lessons_in_week)}/{get_total_days_in_week(week_num)}")
    print()
    print("## Расписание")
    print()
    print("| День | Тип | Тема | Статус |")
    print("|---|---|---|---|")
    for day in week.get("days", []):
        day_num = day.get("day")
        slug = f"{week_num}_{day_num}_{day.get('type')}"
        status = "✅" if slug in lessons_in_week else "⏳"
        print(f"| {day_num} | `{day.get('type')}` | {day.get('title', '')} | {status} |")


def run(args) -> int:
    fix_utf8()
    ensure_dirs()

    action = getattr(args, "action", "show")
    explicit_week = getattr(args, "week", None)

    progress = state.load_progress()
    current_week = progress["current_week"]

    # --week=N: принудительный прыжок
    if explicit_week is not None:
        if explicit_week < 1 or explicit_week > get_total_weeks():
            print(f"❌ Неделя {explicit_week} вне диапазона (1-{get_total_weeks()}).")
            return 1
        _show_week(explicit_week)
        print()
        confirm_phrase = f"Переключиться на неделю {explicit_week}? (current={current_week})"
        if confirm(confirm_phrase, force=getattr(args, "force", False)):
            state.set_current(explicit_week, 1)
            print(f"✅ Текущая неделя: {explicit_week}")
        else:
            print("Отменено.")
        return 0

    # next: переключение на следующую (с проверкой)
    if action == "next":
        next_week = current_week + 1
        if next_week > get_total_weeks():
            print("🎉 Ты уже на последней неделе!")
            return 0

        # Проверяем, все ли 7 дней пройдены
        week = get_week_data(current_week)
        all_days = [d["day"] for d in week.get("days", [])]
        done_days = set()
        for slug in progress.get("lessons_done", []):
            parts = slug.split("_")
            if len(parts) == 3 and int(parts[0]) == current_week:
                done_days.add(int(parts[1]))

        missing = [d for d in all_days if d not in done_days]
        if missing:
            print(f"❌ Не все дни недели {current_week} пройдены.")
            print(f"Остались: {missing}")
            print(f"Сначала пройди их, потом `week next`.")
            return 1

        state.set_current(next_week, 1)
        print(f"✅ Переключились на неделю {next_week}!")
        print()
        _show_week(next_week)
        return 0

    # show (default)
    _show_week(current_week)
    return 0
