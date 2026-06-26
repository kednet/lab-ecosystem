#!/usr/bin/env python3
"""
analyze_engagement.py — метрики постов (ER, охваты, темы).

Использование:
  python analyze_engagement.py --group competitor-1
  python analyze_engagement.py --group pulabru

Вход:  data/competitors/<group>/posts.json
Выход: data/competitors/<group>/metrics.json

Метрики:
  - ER (engagement rate) поста
  - Средний ER паблика
  - Топ-10 постов по ER
  - Распределение по дням недели / часам
  - Рубрикатор (по кластерам тем)

Статус: v0.1 — заглушка.
v0.2 — реальный расчёт.
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


def load_posts(group: str) -> List[Dict[str, Any]]:
    """Загрузить посты из data/competitors/<group>/posts.json."""
    path = COMPETITORS_DIR / group / "posts.json"
    if not path.exists():
        print(f"[error] {path} не найден. Сначала запустите fetch_vk_posts.py")
        return []
    data = json.loads(path.read_text(encoding="utf-8"))
    return data.get("posts", [])


def calc_er(post: Dict[str, Any]) -> float:
    """Engagement rate = (лайки + комменты + репосты) / просмотры × 100%."""
    views = post.get("views", 0)
    if views == 0:
        return 0.0
    likes = post.get("likes", 0)
    comments = post.get("comments", 0)
    reposts = post.get("reposts", 0)
    return (likes + comments + reposts) / views * 100


def analyze_stub(posts: List[Dict[str, Any]]) -> Dict[str, Any]:
    """v0.1 — заглушка. v0.2 — реальный расчёт."""
    if not posts:
        return {
            "version": "1.0",
            "post_count": 0,
            "avg_er": 0.0,
            "top_posts": [],
            "best_day": None,
            "best_hour": None,
        }
    return {
        "version": "1.0",
        "post_count": len(posts),
        "avg_er": 0.0,
        "top_posts": [],
        "best_day": None,
        "best_hour": None,
        "note": "v0.1 — заглушка",
    }


def save_metrics(group: str, metrics: Dict[str, Any]) -> None:
    """Сохранить метрики."""
    out_path = COMPETITORS_DIR / group / "metrics.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    metrics["generated"] = datetime.now().isoformat()
    out_path.write_text(
        json.dumps(metrics, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"[save] → {out_path}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Анализ метрик постов")
    parser.add_argument("--group", type=str, required=True)
    args = parser.parse_args()

    posts = load_posts(args.group)
    if not posts:
        return 1

    print(f"[analyze] {args.group}: {len(posts)} постов")

    metrics = analyze_stub(posts)
    save_metrics(args.group, metrics)

    print(f"[analyze] Средний ER: {metrics.get('avg_er', 0):.2f}%")
    print(f"[analyze] Топ-постов: {len(metrics.get('top_posts', []))}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
