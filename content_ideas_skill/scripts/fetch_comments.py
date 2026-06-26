#!/usr/bin/env python3
"""
fetch_comments.py — парсер комментариев VK к топовым постам.

Использование:
  python fetch_comments.py --group competitor-1 --top-posts 20
  python fetch_comments.py --group pulabru --top-posts 50 --output data/competitors/pulabru/comments.json

Статус: v0.1 — заглушка.
v0.2 — реальный VK API:
  1. Сначала fetch_vk_posts.py → получаем посты
  2. Сортируем по ER, берём топ-N
  3. Для каждого поста: GET wall.getComments
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
COMPETITORS_DIR = DATA_DIR / "competitors"


def fetch_comments_stub(group: str, top_posts: int) -> List[Dict[str, Any]]:
    """v0.1 — заглушка."""
    print(f"[stub] fetch_comments({group}, top_posts={top_posts})")
    print("[stub] В v0.1 — возвращаем заглушку.")
    return []


def save_comments(group: str, comments: List[Dict[str, Any]], output: Path) -> None:
    """Сохранить комменты в JSON."""
    output.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "version": "1.0",
        "group": group,
        "fetched": datetime.now().isoformat(),
        "count": len(comments),
        "comments": comments,
    }
    output.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"[save] {len(comments)} комментов → {output}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Парсер комментариев VK")
    parser.add_argument("--group", type=str, required=True)
    parser.add_argument("--top-posts", type=int, default=20, help="К скольким топовым постам тянуть комменты (default: 20)")
    parser.add_argument("--output", type=str, default=None)

    args = parser.parse_args()

    if args.output:
        output = Path(args.output)
    else:
        output = COMPETITORS_DIR / args.group / "comments.json"

    comments = fetch_comments_stub(args.group, args.top_posts)

    if comments:
        save_comments(args.group, comments, output)
    else:
        print(f"[info] Комментов не получено. Файл {output} не создан.")

    return 0


if __name__ == "__main__":
    sys.exit(main())
