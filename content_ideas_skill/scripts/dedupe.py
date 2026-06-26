#!/usr/bin/env python3
"""
dedupe.py — управление историей идей (дедуп + статистика).

Использование:
  python dedupe.py --show-stats        # показать статистику history.json
  python dedupe.py --archive-old       # архивировать старые (> 6 мес)
  python dedupe.py --check-fp "abc123" # проверить fingerprint
  python dedupe.py --prune-duplicates  # убрать дубли по fingerprint

Статус: v0.1 — рабочий скрипт для статистики и архивации.
"""

import argparse
import json
import sys
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, Any, List

# Force UTF-8 output on Windows
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass

SKILL_DIR = Path(__file__).parent.parent
DATA_DIR = SKILL_DIR / "data"
HISTORY_FILE = DATA_DIR / "history.json"


def load_history() -> Dict[str, Any]:
    if not HISTORY_FILE.exists():
        return {"version": "1.0", "created": datetime.now().isoformat(), "ideas": []}
    return json.loads(HISTORY_FILE.read_text(encoding="utf-8"))


def save_history(history: Dict[str, Any]) -> None:
    HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True)
    HISTORY_FILE.write_text(
        json.dumps(history, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def show_stats(history: Dict[str, Any]) -> None:
    """Показать статистику."""
    ideas = history.get("ideas", [])
    print(f"=== Статистика history.json ===")
    print(f"Всего идей: {len(ideas)}")
    print(f"Версия: {history.get('version', '?')}")
    print(f"Создан: {history.get('created', '?')}")

    if ideas:
        # По рубрикам
        by_rubric = {}
        for idea in ideas:
            r = idea.get("rubric", "?")
            by_rubric[r] = by_rubric.get(r, 0) + 1
        print(f"\nПо рубрикам:")
        for r, c in sorted(by_rubric.items(), key=lambda x: -x[1]):
            print(f"  {r}: {c}")

        # По source.type
        by_source = {}
        for idea in ideas:
            s = idea.get("source_type", idea.get("source", {}).get("type", "?"))
            by_source[s] = by_source.get(s, 0) + 1
        print(f"\nПо источникам:")
        for s, c in sorted(by_source.items(), key=lambda x: -x[1]):
            print(f"  {s}: {c}")

        # По target
        by_target = {}
        for idea in ideas:
            t = idea.get("target", "?")
            by_target[t] = by_target.get(t, 0) + 1
        print(f"\nПо площадкам:")
        for t, c in sorted(by_target.items(), key=lambda x: -x[1]):
            print(f"  {t}: {c}")


def archive_old(history: Dict[str, Any], days: int = 180) -> None:
    """Архивировать идеи старше N дней."""
    ideas = history.get("ideas", [])
    threshold = datetime.now() - timedelta(days=days)

    fresh = []
    archived = []
    for idea in ideas:
        created = idea.get("created", "")
        try:
            created_dt = datetime.fromisoformat(created)
        except (ValueError, TypeError):
            fresh.append(idea)  # оставляем, если не парсится
            continue
        if created_dt < threshold:
            archived.append(idea)
        else:
            fresh.append(idea)

    if archived:
        # Сохраняем архив
        archive_path = DATA_DIR / "history-archive.json"
        archive_data = {
            "version": "1.0",
            "archived_at": datetime.now().isoformat(),
            "ideas": archived,
        }
        archive_path.write_text(
            json.dumps(archive_data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        print(f"[archive] {len(archived)} идей → {archive_path}")

        # Обновляем history
        history["ideas"] = fresh
        save_history(history)
        print(f"[archive] В history.json осталось {len(fresh)} идей")
    else:
        print(f"[archive] Нет идей старше {days} дней")


def check_fingerprint(history: Dict[str, Any], fp: str) -> None:
    """Проверить, есть ли fingerprint в истории."""
    for idea in history.get("ideas", []):
        if idea.get("fingerprint") == fp:
            print(f"[FOUND] {idea['id']} ({idea.get('created', '?')}): {idea.get('title', '?')}")
            return
    print(f"[OK] Fingerprint {fp} не найден в истории — уникален")


def prune_duplicates(history: Dict[str, Any]) -> None:
    """Убрать дубли по fingerprint (оставить самый свежий)."""
    ideas = history.get("ideas", [])
    by_fp = {}
    for idea in ideas:
        fp = idea.get("fingerprint")
        if not fp:
            continue
        existing = by_fp.get(fp)
        if not existing:
            by_fp[fp] = idea
        else:
            # Сравниваем created
            try:
                new_dt = datetime.fromisoformat(idea.get("created", ""))
                old_dt = datetime.fromisoformat(existing.get("created", ""))
                if new_dt > old_dt:
                    by_fp[fp] = idea
            except (ValueError, TypeError):
                pass

    pruned = list(by_fp.values()) + [i for i in ideas if not i.get("fingerprint")]
    removed = len(ideas) - len(pruned)

    if removed > 0:
        history["ideas"] = pruned
        save_history(history)
        print(f"[prune] Удалено {removed} дублей. Осталось {len(pruned)} идей")
    else:
        print(f"[prune] Дублей не найдено")


def main() -> int:
    parser = argparse.ArgumentParser(description="Управление историей идей")
    parser.add_argument("--show-stats", action="store_true", help="Показать статистику")
    parser.add_argument("--archive-old", action="store_true", help="Архивировать старые")
    parser.add_argument("--archive-days", type=int, default=180, help="Сколько дней хранить в history.json (default: 180)")
    parser.add_argument("--check-fp", type=str, default=None, help="Проверить fingerprint")
    parser.add_argument("--prune-duplicates", action="store_true", help="Убрать дубли")
    args = parser.parse_args()

    history = load_history()

    if args.show_stats:
        show_stats(history)
    elif args.archive_old:
        archive_old(history, args.archive_days)
    elif args.check_fp:
        check_fingerprint(history, args.check_fp)
    elif args.prune_duplicates:
        prune_duplicates(history)
    else:
        parser.print_help()

    return 0


if __name__ == "__main__":
    sys.exit(main())
