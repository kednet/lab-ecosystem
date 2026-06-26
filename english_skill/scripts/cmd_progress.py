"""
cmd_progress.py — статистика прогресса.

Показывает: streak, lessons_done (по неделям), quiz_scores, время с старта.
"""
from _english_common import fix_utf8, ensure_dirs, print_header, print_section, get_total_weeks, get_total_days_in_week
import state


def run(args) -> int:
    fix_utf8()
    ensure_dirs()

    progress = state.load_progress()
    if not progress.get("started_at"):
        print("❌ Прогресс ещё не инициализирован. Запусти `start`.")
        return 1

    print_header("📊 Твой прогресс")
    print()
    print(f"**Старт:** {progress.get('started_at', '—')}")
    print(f"**Уровень:** {progress.get('user_level', 'B1')}")
    print(f"**Цель:** {progress.get('goal', '—')}")
    print(f"**Текущая позиция:** Week {progress['current_week']}, Day {progress['current_day']}")
    print(f"**Streak:** 🔥 {progress['streak_days']} дней подряд")
    print(f"**Последняя активность:** {progress.get('last_active_at', '—')}")
    print()
    print("---")
    print()

    # Уроки по неделям
    lessons_done = progress.get("lessons_done", [])
    print(f"## 📚 Уроки: {len(lessons_done)} пройдено")
    print()

    by_week = {}
    for slug in lessons_done:
        parts = slug.split("_")
        if len(parts) >= 1:
            try:
                w = int(parts[0])
                by_week.setdefault(w, []).append(slug)
            except ValueError:
                continue

    print("| Неделя | Пройдено / Всего | % | Статус |")
    print("|---|---|---|---|")
    for w in range(1, get_total_weeks() + 1):
        total = get_total_days_in_week(w)
        done = len(by_week.get(w, []))
        pct = round(100 * done / total) if total > 0 else 0
        if done == 0:
            status = "⏳"
        elif done < total:
            status = "🟡 в процессе"
        else:
            status = "✅ готово"
        print(f"| {w} | {done}/{total} | {pct}% | {status} |")
    print()

    # Quiz scores
    quiz_scores = progress.get("quiz_scores", {})
    if quiz_scores:
        print("## 📝 Quiz scores")
        print()
        print("| Tense | Score | % |")
        print("|---|---|---|")
        # Все возможные tense
        try:
            from quiz import list_quizzes
            all_tenses = list_quizzes()
            for t in all_tenses:
                score = quiz_scores.get(t)
                if score is not None:
                    # Нужно знать total — грузим квиз
                    try:
                        from quiz import load_quiz
                        total = len(load_quiz(t).get("questions", []))
                        pct = round(100 * score / total) if total > 0 else 0
                    except Exception:
                        total = "?"
                        pct = 0
                    print(f"| `{t}` | {score}/{total} | {pct}% |")
        except Exception:
            # fallback
            for t, s in quiz_scores.items():
                print(f"| `{t}` | {s} | — |")
        print()
    else:
        print("## 📝 Quiz scores")
        print()
        print("_Пока ни одного теста не пройдено. Начни с `quiz present-simple`._")
        print()

    # Recommendations
    print("## 🎯 Следующие шаги")
    print()
    if progress['streak_days'] == 0:
        print("- Пройди сегодняшний урок: `python scripts/english.py lesson`")
    elif progress['streak_days'] < 7:
        print(f"- Держи streak! 🔥 Осталось {7 - progress['streak_days']} дней до разблокировки Week 2.")
    else:
        print("- Можно переходить на следующую неделю: `python scripts/english.py week next`")

    if not quiz_scores:
        print("- Пройди мини-тест: `python scripts/english.py quiz present-simple`")
    elif len(quiz_scores) < 5:
        print("- Расширь покрытие: пройди ещё квизов из разных времён.")

    print()
    print("---")
    print()
    print(f"📂 Полный state: `state/progress.json`")
    print(f"📂 Логи уроков: `state/lessons/` (всего {len(lessons_done)} файлов)")
    return 0