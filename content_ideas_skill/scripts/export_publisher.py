#!/usr/bin/env python3
"""
export_publisher.py — мост в Publisher Skill.

Использование:
  python export_publisher.py --ideas data/ideas-bank.json --target vk
  python export_publisher.py --ids idea-2026-07-01-001,idea-2026-07-01-002 --target vk

Вход:  data/ideas-bank.json
Выход: файлы в формате Publisher в data/generated/publisher-cards/

Статус: v0.1 — заглушка. v0.2 — реальный экспорт.
"""

import argparse
import json
import sys
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any

# Force UTF-8 output on Windows
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass

SKILL_DIR = Path(__file__).parent.parent
DATA_DIR = SKILL_DIR / "data"
IDEAS_BANK = DATA_DIR / "ideas-bank.json"
GENERATED_DIR = DATA_DIR / "generated"
EXPORT_DIR = GENERATED_DIR / "publisher-cards"


def load_ideas_bank() -> List[Dict[str, Any]]:
    if not IDEAS_BANK.exists():
        return []
    return json.loads(IDEAS_BANK.read_text(encoding="utf-8")).get("ideas", [])


def filter_ideas(
    ideas: List[Dict[str, Any]],
    target: str = None,
    ids: List[str] = None,
) -> List[Dict[str, Any]]:
    """Фильтрация идей по target и/или ids."""
    filtered = ideas
    if target:
        filtered = [i for i in filtered if i.get("target") == target]
    if ids:
        ids_set = set(ids)
        filtered = [i for i in filtered if i.get("id") in ids_set]
    return filtered


def build_publisher_card(idea: Dict[str, Any]) -> Dict[str, Any]:
    """Карточка идеи в формате Publisher Skill.

    Файл сохраняется по fingerprint (стабильный ключ для дедупа).
    """
    return {
        "fingerprint": idea.get("fingerprint"),
        "id": idea.get("id"),
        "target": idea.get("target"),
        "version": "1.0",
        "meta": {
            "rubric": idea.get("rubric"),
            "priority": idea.get("priority"),
            "audience": idea.get("audience"),
            "tone": idea.get("tone"),
            "source_type": idea.get("source", {}).get("type"),
            "source_ref": idea.get("source", {}).get("ref"),
            "exported_at": datetime.now().isoformat(),
        },
        "payload": {
            "title": idea.get("title"),
            "hook": idea.get("hook"),
            "key_idea": idea.get("key_idea"),
            "structure_hint": idea.get("structure_hint"),
            "cta": idea.get("cta"),
            "target_metric": idea.get("target_metric"),
            "reasoning": idea.get("reasoning"),
        },
        "notes": idea.get("notes"),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Экспорт идей в Publisher")
    parser.add_argument("--ideas", type=str, default=str(IDEAS_BANK), help="Путь к банку идей")
    parser.add_argument("--ids", type=str, default=None, help="ID идей через запятую (если не задан — все)")
    parser.add_argument("--target", type=str, default=None, choices=["vk", "blog", "telegram"], help="Фильтр по target")
    args = parser.parse_args()

    # Загружаем
    bank_path = Path(args.ideas)
    if not bank_path.exists():
        print(f"[error] {bank_path} не найден")
        return 1
    all_ideas = load_ideas_bank()
    if bank_path != IDEAS_BANK:
        all_ideas = json.loads(bank_path.read_text(encoding="utf-8")).get("ideas", [])

    # Фильтруем
    ids = args.ids.split(",") if args.ids else None
    ideas = filter_ideas(all_ideas, target=args.target, ids=ids)

    if not ideas:
        print(f"[info] Не найдено идей для экспорта (target={args.target}, ids={ids})")
        return 0

    # Экспортируем
    EXPORT_DIR.mkdir(parents=True, exist_ok=True)

    # Удаляем старые карточки с именами по id (от v0.1)
    for old_file in EXPORT_DIR.glob("idea-*.json"):
        old_file.unlink()

    print(f"[export] {len(ideas)} идей → {EXPORT_DIR}")
    for idea in ideas:
        card = build_publisher_card(idea)
        fp = idea.get("fingerprint") or idea.get("id")
        out_path = EXPORT_DIR / f"{fp}.json"
        out_path.write_text(
            json.dumps(card, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        print(f"[export]   {out_path.name}")

    print(f"\n[done] Экспортировано {len(ideas)} карточек (по fingerprint)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
