"""
english.py — orchestrator для English Skill v1.0.

Запуск:
    export PYTHONIOENCODING=utf-8   # Windows 11: обязательно
    cd C:/Users/kfigh/english_skill
    python scripts/english.py <command> [options]

Команды:
    start                Зарегистрировать прогресс
    week                 Управление неделей (show / next / --week=N)
    lesson               Урок дня (grammar + listening + tasks + vocab)
    quiz <tense>         Мини-тест (--check=answers.yaml для проверки)
    listen               Аудио для текущей/указанной недели
    dialog <name>        Ролевой диалог (--answer=file.yaml для самопроверки)
    glossary             IT-глоссарий (--topic=X, --export=csv)
    progress             Статистика
    reset                Сброс (--week=N | --all, --force для не-интерактивного режима)
"""
import sys
import argparse
from pathlib import Path

# Делаем scripts/ доступным для импортов
sys.path.insert(0, str(Path(__file__).parent.resolve()))

import _english_common
from _english_common import fix_utf8, SKILL_ROOT, print_header

COMMANDS = {
    "start":    ("Регистрация прогресса",                "cmd_start"),
    "week":     ("Управление неделей",                   "cmd_week"),
    "lesson":   ("Урок дня",                             "cmd_lesson"),
    "quiz":     ("Мини-тест по времени",                 "cmd_quiz"),
    "listen":   ("Аудирование",                          "cmd_listen"),
    "dialog":   ("Ролевой диалог (speaking practice)",    "cmd_dialog"),
    "glossary": ("IT-глоссарий + CSV экспорт",           "cmd_glossary"),
    "progress": ("Статистика прогресса",                 "cmd_progress"),
    "reset":    ("Сброс прогресса",                      "cmd_reset"),
}


def _build_parser() -> argparse.ArgumentParser:
    """Строит argparse с 9 sub-командами."""
    parser = argparse.ArgumentParser(
        prog="english.py",
        description="English Skill v1.0 — 12-недельный тренажёр IT/business English.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Примеры:
  python scripts/english.py start
  python scripts/english.py week
  python scripts/english.py lesson --day=3
  python scripts/english.py quiz present-simple
  python scripts/english.py quiz present-simple --check=tmp/quiz_answers/present-simple.yaml
  python scripts/english.py listen --week=3
  python scripts/english.py dialog standup
  python scripts/english.py glossary --topic=meetings
  python scripts/english.py glossary --export=csv
  python scripts/english.py progress
  python scripts/english.py reset --week=3
        """,
    )
    subparsers = parser.add_subparsers(dest="command", metavar="<command>")

    # === start ===
    p = subparsers.add_parser("start", help="Зарегистрировать прогресс (инициализация state/progress.json)")
    p.add_argument("--force", action="store_true", help="Переинициализировать (удалит старый прогресс)")

    # === week ===
    p = subparsers.add_parser("week", help="Управление неделей")
    p.add_argument("action", nargs="?", default="show",
                   choices=["show", "next"],
                   help="show (default) — показать текущую; next — переключить на следующую")
    p.add_argument("--week", type=int, help="Переключиться на указанную неделю (force-jump)")
    p.add_argument("--force", action="store_true", help="Не спрашивать подтверждение")

    # === lesson ===
    p = subparsers.add_parser("lesson", help="Урок дня (грамматика + listening + задания)")
    p.add_argument("--day", type=int, help="День недели (1-7), default=current_day")
    p.add_argument("--week", type=int, help="Неделя (1-12), default=current_week")
    p.add_argument("--force", action="store_true", help="Пройти заново (игнорировать идемпотентность)")

    # === quiz ===
    p = subparsers.add_parser("quiz", help="Мини-тест по времени")
    p.add_argument("tense", nargs="?", help="Название времени (present-simple, past-simple, ...)")
    p.add_argument("--check", metavar="FILE", help="Проверить ответы из YAML-файла")
    p.add_argument("--force", action="store_true", help="Пройти заново")

    # === listen ===
    p = subparsers.add_parser("listen", help="Аудирование для недели")
    p.add_argument("--week", type=int, help="Неделя (1-12), default=current_week")

    # === dialog ===
    p = subparsers.add_parser("dialog", help="Ролевой диалог (speaking practice)")
    p.add_argument("name", nargs="?", help="Название диалога (standup, code-review, ...)")
    p.add_argument("--answer", metavar="FILE", help="Показать diff с эталоном (YAML-файл с ответами)")

    # === glossary ===
    p = subparsers.add_parser("glossary", help="IT-глоссарий + поиск слов")
    p.add_argument("--topic", help="Фильтр по группе (meetings, standup, core-dev, ...)")
    p.add_argument("--export", choices=["csv"], help="Экспорт в CSV (для Anki)")
    p.add_argument("--source", choices=["main", "xlsx"], help="Набор: main (80 фраз) или xlsx (244 термина из рабочего словаря)")
    p.add_argument("--word", help="Быстрый перевод одного слова (ищет во всех наборах)")

    # === progress ===
    subparsers.add_parser("progress", help="Статистика прогресса")

    # === reset ===
    p = subparsers.add_parser("reset", help="Сброс прогресса")
    p.add_argument("--week", type=int, help="Сбросить только указанную неделю")
    p.add_argument("--all", action="store_true", help="Сбросить всё (необратимо)")
    p.add_argument("--force", action="store_true", help="Не спрашивать подтверждение")

    return parser


def main() -> int:
    fix_utf8()

    parser = _build_parser()
    args = parser.parse_args()

    # Если нет команды — показать help + сводку
    if not args.command:
        print_header("English Skill v1.0 — IT/business English trainer")
        print(f"📂 Корень скила: {SKILL_ROOT}")
        print()
        print("## Доступные команды")
        print()
        print("| Команда | Описание |")
        print("|---|---|")
        for cmd, (desc, _) in COMMANDS.items():
            print(f"| `{cmd}` | {desc} |")
        print()
        print("Запусти `python scripts/english.py <command> --help` для деталей.")
        print()
        print("🚀 **Первый раз?** Начни с `python scripts/english.py start`")
        return 0

    # Lazy import нужного cmd_*.py
    cmd_name = args.command
    module_name = COMMANDS.get(cmd_name, (None, None))[1]
    if not module_name:
        print(f"❌ Неизвестная команда: {cmd_name}")
        return 1

    try:
        import importlib
        module = importlib.import_module(module_name)
    except ImportError as e:
        print(f"❌ Не удалось импортировать {module_name}: {e}")
        return 1

    return module.run(args)


if __name__ == "__main__":
    sys.exit(main())