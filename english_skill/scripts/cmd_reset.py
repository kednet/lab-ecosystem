"""
cmd_reset.py — сброс прогресса.

Без аргументов: печатает предупреждение и текущее состояние.
С --week=N: сбрасывает только эту неделю.
С --all: сбрасывает всё.
"""
from pathlib import Path

from _english_common import fix_utf8, ensure_dirs, LESSONS_DIR, confirm, get_total_weeks
import state


def run(args) -> int:
    fix_utf8()
    ensure_dirs()

    week = getattr(args, "week", None)
    all_flag = getattr(args, "all", False)
    force = getattr(args, "force", False)

    progress = state.load_progress()
    if not progress.get("started_at"):
        print("❌ Нечего сбрасывать — прогресс ещё не начат.")
        return 0

    if all_flag:
        n_lessons = len(progress.get("lessons_done", []))
        n_quizzes = len(progress.get("quiz_scores", {}))
        print("⚠️  ПОЛНЫЙ СБРОС ПРОГРЕССА")
        print()
        print(f"Будет удалено:")
        print(f"  - {n_lessons} lessons_done")
        print(f"  - {n_quizzes} quiz_scores")
        print(f"  - streak_days ({progress.get('streak_days', 0)})")
        print(f"  - state/progress.json")
        print(f"  - все state/lessons/*.json")
        print()

        if not confirm("Точно сбросить ВСЁ?", force=force):
            print("Отменено.")
            return 0

        state.reset_all()
        print("✅ Прогресс полностью сброшен. Запусти `start` чтобы начать заново.")
        return 0

    if week is not None:
        if week < 1 or week > get_total_weeks():
            print(f"❌ Неделя {week} вне диапазона (1-{get_total_weeks()}).")
            return 1

        lessons_in_week = [l for l in progress.get("lessons_done", []) if l.startswith(f"{week}_")]
        print(f"⚠️  Сброс недели {week}")
        print()
        print(f"Будет удалено {len(lessons_in_week)} lessons:")
        for slug in lessons_in_week:
            print(f"  - {slug}")
        print()

        if not confirm(f"Сбросить неделю {week}?", force=force):
            print("Отменено.")
            return 0

        state.reset_week(week)
        # Если мы были на этой неделе — откатываемся на день 1
        if progress["current_week"] == week:
            state.set_current(week, 1)
            print(f"📅 Ты осталась на неделе {week}, день 1 (так как была на ней).")
        elif progress["current_week"] > week:
            print(f"📅 Текущая неделя {progress['current_week']} — без изменений.")
        print(f"✅ Неделя {week} сброшена.")
        return 0

    # Без аргументов — показать что будет если сбросить
    print("⚠️  reset требует аргумент:")
    print()
    print(f"  --week=N    Сбросить только неделю {progress['current_week']} (например)")
    print(f"  --all       Сбросить ВСЁ (необратимо!)")
    print(f"  --force     Не спрашивать подтверждение")
    print()
    print("Текущий прогресс:")
    print(f"  Неделя: {progress['current_week']}, день: {progress['current_day']}")
    print(f"  Уроков пройдено: {len(progress.get('lessons_done', []))}")
    print(f"  Quiz scores: {len(progress.get('quiz_scores', {}))}")
    print(f"  Streak: {progress.get('streak_days', 0)} дней")
    return 0