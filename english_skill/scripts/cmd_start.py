"""
cmd_start.py — инициализация state/progress.json.

Печатает приветствие и план на неделю 1.
"""
from _english_common import fix_utf8, ensure_dirs, print_header, print_section, load_yaml, DATA_DIR
import state


def run(args) -> int:
    fix_utf8()
    ensure_dirs()

    if state.get_progress_path().exists() and not args.force:
        progress = state.load_progress()
        print_header("English Skill — уже зарегистрирован ✓")
        print(f"Текущая неделя: {progress['current_week']}, день: {progress['current_day']}")
        print(f"Streak: 🔥 {progress['streak_days']} дней")
        print(f"Пройдено уроков: {len(progress['lessons_done'])}")
        print()
        print("Используй `--force` чтобы переинициализировать (потеряешь весь прогресс).")
        return 0

    if state.get_progress_path().exists() and args.force:
        print("⚠️  Переинициализация: удаляю старый прогресс...")
        state.reset_all()
        state.get_progress_path().unlink()  # чтобы init_progress создал заново с started_at

    progress = state.init_progress()
    state.update_streak_on_active()

    print_header("🎉 Добро пожаловать в English Skill v1.0!")
    print()
    print("Ты зарегистрирована. Прогресс начат.")
    print()
    print("## Твоя программа на 12 недель")
    print()
    print("| Неделя | Тема | Грамматика |")
    print("|---|---|---|")
    print("| 1 | Present Simple — основа делового английского | present-simple |")
    print("| 2 | Past Simple — истории и кейсы | past-simple |")
    print("| 3 | **Present Perfect vs Past Simple** — главная B1-проблема! | present-perfect-vs-past-simple |")
    print("| 4 | Present Perfect: закрепление (since/for/already/yet) | present-perfect |")
    print("| 5 | Present Continuous — что происходит сейчас | present-continuous |")
    print("| 6 | Future: will vs going to | future-will-going |")
    print("| 7 | Past Continuous — фон для прошлых событий | past-continuous |")
    print("| 8 | Past Perfect — прошлое в прошлом | past-perfect |")
    print("| 9 | 1st Conditional — реальные условия | conditional-1st |")
    print("| 10 | 2nd Conditional — гипотетические ситуации | conditional-2nd |")
    print("| 11 | Passive Voice — фокус на действии | passive-voice |")
    print("| 12 | Reported Speech + финальный обзор | reported-speech |")
    print()
    print("## Что делать сейчас")
    print()
    print("1. Открой урок дня:")
    print("   `python scripts/english.py lesson`")
    print()
    print("2. Пройди мини-тест:")
    print("   `python scripts/english.py quiz present-simple`")
    print()
    print("3. Посмотри IT-глоссарий:")
    print("   `python scripts/english.py glossary --topic=meetings`")
    print()
    print("4. Посмотри прогресс:")
    print("   `python scripts/english.py progress`")
    print()
    print("⏱ Рекомендуемый ритм: 20-25 мин/день, 5-6 дней в неделю.")
    print("🔥 После 7 дней подряд — streak 7 и доступ к Week 2.")
    print()
    print("Удачи! Погнали 💪")
    return 0
