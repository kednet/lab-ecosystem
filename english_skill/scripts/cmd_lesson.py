"""
cmd_lesson.py — урок дня (грамматика + listening + mini-tasks + vocab).

Идемпотентность: если урок уже done — сообщает и предлагает --force.
"""
from _english_common import fix_utf8, ensure_dirs, print_header, print_section, print_subsection, resolve_day, get_day_data, get_week_data, load_yaml, DATA_DIR, resolve_week
import state


def _render_lesson(week_num: int, day_num: int) -> str:
    """Рендерит markdown урока."""
    day = get_day_data(week_num, day_num)
    if not day:
        return f"❌ Урок Week {week_num} Day {day_num} не найден."

    week = get_week_data(week_num)
    week_theme = week.get("theme", "") if week else ""

    lines = []
    lines.append(f"# Week {week_num} | Day {day_num}: {day.get('title', '(no title)')}")
    lines.append("")
    lines.append(f"**Тема недели:** {week_theme}")
    lines.append(f"**Тип урока:** `{day.get('type', 'lesson')}`")
    lines.append(f"**Грамматика:** {day.get('grammar_focus', '—')}")
    if day.get("grammar_topic"):
        lines.append(f"**Топик:** {day.get('grammar_topic')}")
    lines.append("")
    lines.append("---")
    lines.append("")

    # Тело урока (может быть многострочным markdown)
    content = day.get("content")
    if content:
        lines.append(content.strip())
        lines.append("")
        lines.append("---")
        lines.append("")

    # Listening
    if day.get("listening"):
        lines.append("## 🎧 Аудирование")
        lines.append("")
        sources = load_yaml(DATA_DIR / "sources.yaml").get("sources", [])
        source_map = {s["id"]: s for s in sources}
        for sid in day["listening"]:
            s = source_map.get(sid)
            if s:
                lines.append(f"### {s['title']}")
                lines.append(f"_({s['source']}, ~{s['duration_min']} мин)_")
                lines.append(f"🔗 {s.get('url', '#')}")
                if s.get("transcript_url"):
                    lines.append(f"📄 Transcript: {s['transcript_url']}")
                if s.get("vocab"):
                    lines.append("")
                    lines.append("**Vocab:** " + ", ".join(s["vocab"]))
                if s.get("comprehension_questions"):
                    lines.append("")
                    lines.append("**Comprehension questions:**")
                    for i, q in enumerate(s["comprehension_questions"], 1):
                        lines.append(f"{i}. *{q['q']}*")
                        if q.get("sample_answer"):
                            lines.append(f"   - Sample: _{q['sample_answer']}_")
                lines.append("")

    # Mini-tasks
    if day.get("task"):
        lines.append("## ✏️ Мини-задания")
        lines.append("")
        lines.append(day["task"])
        lines.append("")

    # Dialog
    if day.get("dialog"):
        lines.append("## 🎭 Ролевой диалог")
        lines.append("")
        lines.append(f"Открой: `python scripts/english.py dialog {day['dialog']}`")
        lines.append("")

    # Quiz
    if day.get("quiz"):
        lines.append("## 📝 Мини-тест")
        lines.append("")
        lines.append(f"Пройди: `python scripts/english.py quiz {day['quiz']}`")
        lines.append("")

    # Vocab дня
    if day.get("vocab"):
        lines.append("## 📚 Vocab дня")
        lines.append("")
        for v in day["vocab"]:
            lines.append(f"- **{v}**")
        lines.append("")

    return "\n".join(lines)


def run(args) -> int:
    fix_utf8()
    ensure_dirs()

    week_num = resolve_week(getattr(args, "week", None))
    day_num = resolve_day(getattr(args, "day", None))

    day = get_day_data(week_num, day_num)
    if not day:
        print(f"❌ Week {week_num} Day {day_num} не найден.")
        return 1

    day_type = day.get("type", "lesson")
    force = getattr(args, "force", False)

    # Идемпотентность
    if state.is_lesson_done(week_num, day_num, day_type) and not force:
        print(f"⏭  Урок {week_num}_{day_num}_{day_type} уже пройден.")
        print("Используй --force чтобы пройти заново.")
        return 0

    # Помечаем как начатый (для аналитики)
    state.start_lesson(week_num, day_num, day_type)

    # Рендерим markdown
    md = _render_lesson(week_num, day_num)
    print(md)

    # Помечаем как done
    state.mark_lesson_done(week_num, day_num, day_type)
    state.update_streak_on_active()
    print()
    print("---")
    print()
    print(f"✅ Урок Week {week_num} Day {day_num} ({day_type}) пройден!")
    print(f"📅 Прогресс сохранён в state/lessons/{week_num}_{day_num}_{day_type}.json")
    print(f"🔥 Текущий streak: {state.load_progress()['streak_days']} дней")
    print()
    print(f"Следующий шаг: `python scripts/english.py lesson --day={day_num + 1}`")
    return 0
