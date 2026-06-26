"""
_english_common.py — общие утилиты English Skill v1.0.

- UTF-8 fix для Windows 11 (cp1252)
- Paths (auto-detect SKILL_ROOT)
- now_iso() — UTC timestamp
- week_resolver() — какой номер недели использовать
- load_yaml() — обёртка над yaml.safe_load с fallback

Используется во всех cmd_*.py.
"""
import sys
import os
import io
import yaml
from datetime import datetime, timezone
from pathlib import Path


# === UTF-8 fix (Windows 11 cp1252 → utf-8) ===

def fix_utf8():
    """Перенастраивает stdout на UTF-8. Вызывать первой строкой в каждом скрипте."""
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except (AttributeError, ValueError):
        # Python < 3.7 или уже настроено
        pass


# === Paths ===

def get_skill_root() -> Path:
    """Возвращает корень скила. Auto-detect: идёт вверх от scripts/_english_common.py."""
    return Path(__file__).parent.parent.resolve()


SKILL_ROOT = get_skill_root()
DATA_DIR = SKILL_ROOT / "data"
DIALOGS_DIR = DATA_DIR / "dialogs"
QUIZZES_DIR = DATA_DIR / "quizzes"
SCRIPTS_DIR = SKILL_ROOT / "scripts"
STATE_DIR = SKILL_ROOT / "state"
LESSONS_DIR = STATE_DIR / "lessons"
TEMPLATES_DIR = SKILL_ROOT / "templates"
REFERENCES_DIR = SKILL_ROOT / "references"
TMP_DIR = SKILL_ROOT / "tmp"
LOGS_DIR = SKILL_ROOT / "logs"


def ensure_dirs():
    """Создаёт runtime-папки если их нет."""
    for d in [STATE_DIR, LESSONS_DIR, TMP_DIR, LOGS_DIR]:
        d.mkdir(parents=True, exist_ok=True)


# === Time ===

def now_iso() -> str:
    """Возвращает текущее UTC время в ISO 8601 формате."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# === YAML loader ===

def load_yaml(path: Path) -> dict:
    """Безопасная загрузка YAML с понятной ошибкой."""
    if not path.exists():
        raise FileNotFoundError(f"YAML файл не найден: {path}")
    try:
        with open(path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f)
    except yaml.YAMLError as e:
        raise ValueError(f"Ошибка парсинга YAML {path}: {e}")


def load_yaml_optional(path: Path) -> dict | None:
    """Загружает YAML или возвращает None если файл отсутствует."""
    if not path.exists():
        return None
    return load_yaml(path)


# === Week resolver ===

def get_current_week() -> int:
    """Возвращает текущую неделю из state/progress.json. По умолчанию 1."""
    progress_path = STATE_DIR / "progress.json"
    if not progress_path.exists():
        return 1
    import json
    try:
        with open(progress_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return int(data.get("current_week", 1))
    except (json.JSONDecodeError, ValueError, KeyError):
        return 1


def get_current_day() -> int:
    """Возвращает текущий день из state/progress.json. По умолчанию 1."""
    progress_path = STATE_DIR / "progress.json"
    if not progress_path.exists():
        return 1
    import json
    try:
        with open(progress_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return int(data.get("current_day", 1))
    except (json.JSONDecodeError, ValueError, KeyError):
        return 1


def resolve_week(args_week: int | None) -> int:
    """Определяет неделю: из --week флага, иначе current_week."""
    if args_week is not None:
        return args_week
    return get_current_week()


def resolve_day(args_day: int | None) -> int:
    """Определяет день: из --day флага, иначе current_day."""
    if args_day is not None:
        return args_day
    return get_current_day()


# === Curriculum helpers ===

def get_curriculum() -> dict:
    """Загружает curriculum.yaml."""
    return load_yaml(DATA_DIR / "curriculum.yaml")


def get_week_data(week_num: int) -> dict | None:
    """Возвращает данные указанной недели из curriculum.yaml."""
    curriculum = get_curriculum()
    for week in curriculum.get("weeks", []):
        if week.get("week") == week_num:
            return week
    return None


def get_day_data(week_num: int, day_num: int) -> dict | None:
    """Возвращает данные конкретного дня в указанной неделе."""
    week = get_week_data(week_num)
    if not week:
        return None
    for day in week.get("days", []):
        if day.get("day") == day_num:
            return day
    return None


def get_total_weeks() -> int:
    """Возвращает общее количество недель в курикулуме."""
    curriculum = get_curriculum()
    return len(curriculum.get("weeks", []))


def get_total_days_in_week(week_num: int) -> int:
    """Возвращает количество дней в неделе (обычно 7)."""
    week = get_week_data(week_num)
    if not week:
        return 0
    return len(week.get("days", []))


# === Output helpers ===

def print_header(text: str, char: str = "="):
    """Печатает заголовок с подчёркиванием."""
    print()
    print(text)
    print(char * len(text))


def print_section(text: str):
    """Печатает секцию."""
    print()
    print(f"## {text}")


def print_subsection(text: str):
    print(f"\n### {text}")


def confirm(prompt: str, force: bool = False) -> bool:
    """Спрашивает подтверждение. Если force=True — пропускает вопрос."""
    if force:
        return True
    try:
        answer = input(f"{prompt} [y/N]: ").strip().lower()
    except EOFError:
        return False
    return answer in ("y", "yes", "д", "да")


if __name__ == "__main__":
    # Smoke-test
    fix_utf8()
    ensure_dirs()
    print(f"SKILL_ROOT: {SKILL_ROOT}")
    print(f"DATA_DIR: {DATA_DIR}")
    print(f"STATE_DIR: {STATE_DIR}")
    print(f"now_iso: {now_iso()}")
    print(f"current_week: {get_current_week()}")
    print(f"total_weeks: {get_total_weeks()}")
