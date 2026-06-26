"""
state.py — прогресс-трекинг и идемпотентность English Skill v1.0.

Два файла:
- state/progress.json — глобальный прогресс
- state/lessons/<week>_<day>_<type>.json — статус пройденности урока

Конвенция slug = "<week>_<day>_<type>"
type ∈ {intro, grammar, listening, quiz, dialog, review}
"""
import json
from pathlib import Path
from typing import Optional

from _english_common import (
    STATE_DIR, LESSONS_DIR, now_iso, ensure_dirs, get_total_weeks
)


# === Дефолты ===

DEFAULT_PROGRESS = {
    "started_at": None,
    "user_level": "B1",
    "goal": "IT/business English",
    "current_week": 1,
    "current_day": 1,
    "streak_days": 0,
    "last_active_date": None,
    "lessons_done": [],
    "quiz_scores": {},
    "last_active_at": None,
}


# === Progress.json ===

def get_progress_path() -> Path:
    return STATE_DIR / "progress.json"


def load_progress() -> dict:
    """Загружает state/progress.json или возвращает дефолт."""
    ensure_dirs()
    p = get_progress_path()
    if not p.exists():
        return DEFAULT_PROGRESS.copy()
    try:
        with open(p, "r", encoding="utf-8") as f:
            data = json.load(f)
        # Backfill любых отсутствующих ключей дефолтами
        for key, val in DEFAULT_PROGRESS.items():
            data.setdefault(key, val)
        return data
    except (json.JSONDecodeError, OSError):
        return DEFAULT_PROGRESS.copy()


def save_progress(data: dict) -> None:
    """Сохраняет state/progress.json."""
    ensure_dirs()
    p = get_progress_path()
    with open(p, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def init_progress(force: bool = False) -> dict:
    """Инициализирует progress.json с дефолтами.

    force=True — перезаписывает существующий файл (используется при --force start).
    """
    if get_progress_path().exists() and not force:
        return load_progress()
    data = DEFAULT_PROGRESS.copy()
    data["started_at"] = now_iso()
    data["last_active_at"] = now_iso()
    save_progress(data)
    return data


# === Lessons (идемпотентность уроков) ===

def lesson_slug(week: int, day: int, type_: str) -> str:
    """Генерирует slug урока: '<week>_<day>_<type>'."""
    return f"{week}_{day}_{type_}"


def get_lesson_path(week: int, day: int, type_: str) -> Path:
    """Возвращает путь к state/lessons/<slug>.json."""
    return LESSONS_DIR / f"{lesson_slug(week, day, type_)}.json"


def load_lesson(week: int, day: int, type_: str) -> Optional[dict]:
    """Загружает статус урока или возвращает None."""
    p = get_lesson_path(week, day, type_)
    if not p.exists():
        return None
    try:
        with open(p, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return None


def is_lesson_done(week: int, day: int, type_: str) -> bool:
    """Проверяет, пройден ли урок."""
    lesson = load_lesson(week, day, type_)
    if not lesson:
        return False
    return lesson.get("status") == "done"


def mark_lesson_done(week: int, day: int, type_: str) -> dict:
    """Помечает урок как пройденный. Идемпотентно (если уже done — return без записи)."""
    ensure_dirs()
    p = get_lesson_path(week, day, type_)
    existing = load_lesson(week, day, type_)
    if existing and existing.get("status") == "done":
        return existing  # уже сделано
    lesson = {
        "week": week,
        "day": day,
        "type": type_,
        "status": "done",
        "started_at": existing.get("started_at") if existing else now_iso(),
        "done_at": now_iso(),
    }
    with open(p, "w", encoding="utf-8") as f:
        json.dump(lesson, f, ensure_ascii=False, indent=2)

    # Обновляем progress.json
    progress = load_progress()
    slug = lesson_slug(week, day, type_)
    if slug not in progress["lessons_done"]:
        progress["lessons_done"].append(slug)
    progress["last_active_at"] = now_iso()
    save_progress(progress)
    return lesson


def start_lesson(week: int, day: int, type_: str) -> dict:
    """Отмечает начало урока (без финального done)."""
    ensure_dirs()
    p = get_lesson_path(week, day, type_)
    existing = load_lesson(week, day, type_)
    if existing:
        return existing
    lesson = {
        "week": week,
        "day": day,
        "type": type_,
        "status": "pending",
        "started_at": now_iso(),
        "done_at": None,
    }
    with open(p, "w", encoding="utf-8") as f:
        json.dump(lesson, f, ensure_ascii=False, indent=2)
    return lesson


# === Streak ===

def update_streak_on_active() -> int:
    """Обновляет streak при активности. Возвращает новое значение."""
    progress = load_progress()
    today = now_iso()[:10]  # YYYY-MM-DD
    last = progress.get("last_active_date")
    if last == today:
        # уже активны сегодня — ничего не меняем
        return progress["streak_days"]
    if last is None:
        # первый день
        progress["streak_days"] = 1
    else:
        # проверим, вчера ли был последний активный день
        from datetime import date, timedelta
        try:
            last_date = date.fromisoformat(last)
            today_date = date.fromisoformat(today)
            delta = (today_date - last_date).days
            if delta == 1:
                # вчера → streak +1
                progress["streak_days"] = progress.get("streak_days", 0) + 1
            elif delta > 1:
                # пропустили день → сброс
                progress["streak_days"] = 1
            # delta == 0 обработан выше
        except ValueError:
            progress["streak_days"] = 1
    progress["last_active_date"] = today
    save_progress(progress)
    return progress["streak_days"]


# === Quiz scores ===

def set_quiz_score(tense: str, score: int) -> None:
    """Сохраняет score мини-теста в progress.json."""
    progress = load_progress()
    scores = progress.get("quiz_scores", {})
    scores[tense] = int(score)
    progress["quiz_scores"] = scores
    progress["last_active_at"] = now_iso()
    save_progress(progress)


def get_quiz_score(tense: str) -> Optional[int]:
    """Возвращает последний score для теста или None."""
    progress = load_progress()
    return progress.get("quiz_scores", {}).get(tense)


# === Current week/day ===

def set_current(week: int, day: int) -> None:
    """Обновляет current_week и current_day в progress.json."""
    progress = load_progress()
    progress["current_week"] = int(week)
    progress["current_day"] = int(day)
    progress["last_active_at"] = now_iso()
    save_progress(progress)


def get_current() -> tuple[int, int]:
    """Возвращает (current_week, current_day)."""
    progress = load_progress()
    return progress.get("current_week", 1), progress.get("current_day", 1)


# === Reset ===

def reset_week(week: int) -> int:
    """Сбрасывает все уроки указанной недели. Возвращает количество удалённых."""
    ensure_dirs()
    count = 0
    pattern = f"{week}_"
    for f in LESSONS_DIR.glob(f"{pattern}*.json"):
        f.unlink()
        count += 1
    # Удаляем из progress.json
    progress = load_progress()
    progress["lessons_done"] = [
        s for s in progress.get("lessons_done", []) if not s.startswith(f"{week}_")
    ]
    save_progress(progress)
    return count


def reset_all() -> int:
    """Полный сброс: удаляет все state/lessons/* и обнуляет progress.json."""
    ensure_dirs()
    count = 0
    for f in LESSONS_DIR.glob("*.json"):
        f.unlink()
        count += 1
    save_progress(DEFAULT_PROGRESS.copy())
    return count


# === Smoke test ===

if __name__ == "__main__":
    print("state.py — smoke test")
    print(f"DEFAULT_PROGRESS: {DEFAULT_PROGRESS}")
    print(f"sample lesson_slug(3, 4, 'grammar'): {lesson_slug(3, 4, 'grammar')}")
    print(f"get_current(): {get_current()}")
