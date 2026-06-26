r"""
sync_reviews_hub.py
===================

Односторонняя синхронизация данных из expert-reviews-hub/ → lab_site/src/data/.

Зачем:
  Astro build — SSG, нужны статические файлы в момент сборки.
  Reviews Hub хранит .md с frontmatter, нам нужен JSON для `import`.

Источники:
  expert-reviews-hub/experts/{slug}.md       → lab_site/src/data/experts/{slug}.json
  expert-reviews-hub/reviews/{slug}/summary.json → lab_site/src/data/reviews/{slug}.json

Использование:
  python scripts/sync_reviews_hub.py --experts --reviews
  python scripts/sync_reviews_hub.py --experts              # только эксперты
  python scripts/sync_reviews_hub.py --dry-run             # ничего не пишем, только показываем план
  python scripts/sync_reviews_hub.py --verbose
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from datetime import datetime

# ── UTF-8 fix for Windows ─────────────────────────────────
try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

# ── Корень проекта lab_site (родитель этой папки scripts/) ─
SCRIPT_DIR = Path(__file__).resolve().parent
LAB_SITE_ROOT = SCRIPT_DIR.parent

# Добавляем python-service в sys.path для импорта лоадеров
PYTHON_SERVICE = LAB_SITE_ROOT / "python-service"
if str(PYTHON_SERVICE) not in sys.path:
    sys.path.insert(0, str(PYTHON_SERVICE))

# Импорты лоадеров (работают автономно)
from loaders import (  # noqa: E402
    EXPERTS_HUB_ROOT,
    REVIEWS_HUB_ROOT,
    load_all_experts,
    load_index,
    load_all_review_summaries,
    ExpertCard,
    ReviewSummary,
)


# ── Куда пишем в lab_site ─────────────────────────────────
LAB_EXPERTS_DIR = LAB_SITE_ROOT / "src" / "data" / "experts"
LAB_REVIEWS_DIR = LAB_SITE_ROOT / "src" / "data" / "reviews"
LAB_INDEX_EXPERTS = LAB_EXPERTS_DIR / "index.json"
LAB_INDEX_REVIEWS = LAB_REVIEWS_DIR / "index.json"


def now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


# ── Sync experts ──────────────────────────────────────────
def sync_experts(*, dry_run: bool = False, verbose: bool = False) -> dict:
    """Синхронизировать карточки экспертов → lab_site/src/data/experts/."""
    cards: list[ExpertCard] = load_all_experts()
    if not cards:
        print("⚠️  No experts found in Reviews Hub (experts/ is empty)", file=sys.stderr)
        return {"synced": 0, "skipped": 0, "errors": 0}

    synced = 0
    errors = 0
    if not dry_run:
        LAB_EXPERTS_DIR.mkdir(parents=True, exist_ok=True)

    for card in cards:
        try:
            data = card.to_dict()
            if not dry_run:
                out = LAB_EXPERTS_DIR / f"{card.slug}.json"
                out.write_text(
                    json.dumps(data, ensure_ascii=False, indent=2),
                    encoding="utf-8",
                )
            synced += 1
            if verbose:
                print(f"  ✓ {card.slug:30s} | score={card.score:3d} | {card.name}")
        except Exception as e:
            errors += 1
            print(f"  ! Failed to sync {card.slug}: {e}", file=sys.stderr)

    # Index
    index = load_index()
    if not dry_run:
        LAB_INDEX_EXPERTS.write_text(
            json.dumps(index, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    if verbose:
        print(f"  ✓ index.json ({index['total']} experts)")

    return {"synced": synced, "errors": errors, "total": len(cards)}


# ── Sync reviews ──────────────────────────────────────────
def sync_reviews(*, dry_run: bool = False, verbose: bool = False) -> dict:
    """Синхронизировать сводки отзывов → lab_site/src/data/reviews/."""
    summaries: list[ReviewSummary] = load_all_review_summaries()
    if not summaries:
        print("⚠️  No review summaries found in Reviews Hub (reviews/*/summary.json)", file=sys.stderr)
        return {"synced": 0, "skipped": 0, "errors": 0}

    synced = 0
    errors = 0
    if not dry_run:
        LAB_REVIEWS_DIR.mkdir(parents=True, exist_ok=True)

    for s in summaries:
        try:
            data = s.to_dict()
            if not dry_run:
                out = LAB_REVIEWS_DIR / f"{s.book_slug}.json"
                out.write_text(
                    json.dumps(data, ensure_ascii=False, indent=2),
                    encoding="utf-8",
                )
            synced += 1
            if verbose:
                print(f"  ✓ {s.book_slug:40s} | ⭐{s.weighted_average:.2f} | {s.total_reviews:>5d} отзывов")
        except Exception as e:
            errors += 1
            print(f"  ! Failed to sync {s.book_slug}: {e}", file=sys.stderr)

    # Index
    if not dry_run:
        index = {
            "generated_at": now_iso(),
            "total": len(summaries),
            "reviews": [
                {
                    "slug": s.book_slug,
                    "title": s.book_title,
                    "author": s.book_author,
                    "weighted_average": s.weighted_average,
                    "total_reviews": s.total_reviews,
                    "confidence": s.confidence,
                }
                for s in summaries
            ],
        }
        LAB_INDEX_REVIEWS.write_text(
            json.dumps(index, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    if verbose:
        print(f"  ✓ index.json ({len(summaries)} review summaries)")

    return {"synced": synced, "errors": errors, "total": len(summaries)}


# ── Main ──────────────────────────────────────────────────
def main():
    p = argparse.ArgumentParser(
        description="Синхронизация expert-reviews-hub → lab_site/src/data/"
    )
    p.add_argument(
        "--experts", action="store_true",
        help="Синхронизировать карточки экспертов",
    )
    p.add_argument(
        "--reviews", action="store_true",
        help="Синхронизировать сводки отзывов",
    )
    p.add_argument(
        "--all", action="store_true",
        help="Синхронизировать всё (по умолчанию)",
    )
    p.add_argument(
        "--dry-run", action="store_true",
        help="Только показать план, ничего не писать",
    )
    p.add_argument(
        "--verbose", "-v", action="store_true",
        help="Подробный вывод",
    )
    args = p.parse_args()

    # Если ничего не указано — sync всё
    do_experts = args.experts or args.all or (not args.experts and not args.reviews and not args.all)
    do_reviews = args.reviews or args.all or (not args.experts and not args.reviews and not args.all)

    print("=" * 60)
    print(f"  Sync: expert-reviews-hub → lab_site/src/data/")
    print(f"  Mode: {'DRY-RUN' if args.dry_run else 'WRITE'}")
    print(f"  Experts: {do_experts}, Reviews: {do_reviews}")
    print("=" * 60)
    print(f"  Hub root:   {EXPERTS_HUB_ROOT}")
    print(f"  Lab site:   {LAB_SITE_ROOT}")
    print(f"  → experts:  {LAB_EXPERTS_DIR}")
    print(f"  → reviews:  {LAB_REVIEWS_DIR}")
    print()

    results = {}

    if do_experts:
        print("📚 EXPERTS")
        print("-" * 60)
        results["experts"] = sync_experts(dry_run=args.dry_run, verbose=args.verbose)
        print()

    if do_reviews:
        print("⭐ REVIEWS")
        print("-" * 60)
        results["reviews"] = sync_reviews(dry_run=args.dry_run, verbose=args.verbose)
        print()

    # Summary
    print("=" * 60)
    print("  SUMMARY")
    for kind, r in results.items():
        if "errors" in r:
            err = r["errors"]
            synced = r["synced"]
            total = r.get("total", 0)
            icon = "❌" if err > 0 else "✅"
            print(f"  {icon} {kind}: {synced}/{total} synced, {err} errors")
    print("=" * 60)

    if args.dry_run:
        print()
        print("  ⓘ DRY-RUN: nothing was written. Run without --dry-run to apply.")


if __name__ == "__main__":
    main()
