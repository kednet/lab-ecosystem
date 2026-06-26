r"""
Загрузчик отзывов из expert-reviews-hub/reviews/{book-slug}/summary.json
и опционально bundle.json.

Источник:
  C:\Users\kfigh\expert-reviews-hub\reviews\{slug}\summary.json
  C:\Users\kfigh\expert-reviews-hub\reviews\{slug}\bundle.json

Веса источников (синхронизировано с expert-reviews-hub/data/sources-rating.md).
"""
from __future__ import annotations

import json
import sys
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Optional

# ── UTF-8 fix for Windows ─────────────────────────────────
try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

# ── Корень Reviews Hub ─────────────────────────────────────
REVIEWS_HUB_ROOT = Path(
    r"C:\Users\kfigh\expert-reviews-hub"
).resolve()

# ── Веса источников ────────────────────────────────────────
SOURCE_WEIGHTS: dict[str, float] = {
    "litres": 1.5,
    "own": 1.5,
    "livelib": 1.2,
    "author_today": 1.0,
    "goodreads": 1.0,
    "youtube": 0.9,
    "vk": 0.8,
    "telegram": 0.7,
    "ozon": 0.7,
}


@dataclass
class ReviewSource:
    name: str
    weight: float
    count: int
    avg: float
    verified_ratio: float = 0.0
    url: str = ""


@dataclass
class ReviewSummary:
    """Сводка отзывов по книге."""
    book_slug: str
    book_title: str = ""
    book_author: str = ""
    total_reviews: int = 0
    weighted_average: float = 0.0
    confidence: str = "low"            # high | medium | low
    trust_score: float = 0.0
    sources: list[ReviewSource] = field(default_factory=list)
    pros: list[dict] = field(default_factory=list)         # [{text, mentions, pct, examples}]
    cons: list[dict] = field(default_factory=list)
    top_quotes: list[dict] = field(default_factory=list)   # [{quote, author, source, rating}]
    sentiment_distribution: dict = field(default_factory=dict)
    trends: list[dict] = field(default_factory=list)
    verdict: str = ""
    generated_at: str = ""
    source_path: str = ""

    def to_dict(self) -> dict:
        return {
            "book_slug": self.book_slug,
            "book_title": self.book_title,
            "book_author": self.book_author,
            "total_reviews": self.total_reviews,
            "weighted_average": self.weighted_average,
            "confidence": self.confidence,
            "trust_score": self.trust_score,
            "sources": [asdict(s) for s in self.sources],
            "pros": self.pros,
            "cons": self.cons,
            "top_quotes": self.top_quotes,
            "sentiment_distribution": self.sentiment_distribution,
            "trends": self.trends,
            "verdict": self.verdict,
            "generated_at": self.generated_at,
        }


def _now_iso() -> str:
    from datetime import datetime
    return datetime.now().isoformat(timespec="seconds")


def load_review_summary(
    book_slug: str, *, hub_root: Path = REVIEWS_HUB_ROOT
) -> Optional[ReviewSummary]:
    """Загрузить summary.json по конкретной книге."""
    summary_path = hub_root / "reviews" / book_slug / "summary.json"
    if not summary_path.exists():
        return None

    try:
        data = json.loads(summary_path.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"  ! Failed to parse {summary_path}: {e}", file=sys.stderr)
        return None

    sources: list[ReviewSource] = []
    for s in data.get("sources_breakdown", []):
        sources.append(ReviewSource(
            name=s.get("source", "unknown"),
            weight=float(s.get("weight", 1.0)),
            count=int(s.get("count", 0)),
            avg=float(s.get("avg", 0.0)),
            verified_ratio=float(s.get("verified_ratio", 0.0)),
            url=s.get("url", ""),
        ))

    return ReviewSummary(
        book_slug=book_slug,
        book_title=data.get("book", {}).get("title", ""),
        book_author=data.get("book", {}).get("author", ""),
        total_reviews=int(data.get("total_reviews", 0)),
        weighted_average=float(data.get("weighted_average", 0.0)),
        confidence=data.get("confidence", "low"),
        trust_score=float(data.get("trust_score", 0.0)),
        sources=sources,
        pros=data.get("pros", []),
        cons=data.get("cons", []),
        top_quotes=data.get("top_quotes", []),
        sentiment_distribution=data.get("sentiment_distribution", {}),
        trends=data.get("trends", []),
        verdict=data.get("verdict", ""),
        generated_at=data.get("generated_at") or _now_iso(),
        source_path=str(summary_path),
    )


def load_all_review_summaries(
    *, hub_root: Path = REVIEWS_HUB_ROOT
) -> list[ReviewSummary]:
    """Загрузить все summary.json из reviews/*/."""
    reviews_dir = hub_root / "reviews"
    if not reviews_dir.exists():
        return []

    summaries: list[ReviewSummary] = []
    for sub in sorted(reviews_dir.iterdir()):
        if not sub.is_dir():
            continue
        s = load_review_summary(sub.name, hub_root=hub_root)
        if s is not None:
            summaries.append(s)

    # Сортировка: сначала те, у кого больше отзывов
    summaries.sort(key=lambda s: -s.total_reviews)
    return summaries


# ── CLI: smoke test ───────────────────────────────────────
if __name__ == "__main__":
    summaries = load_all_review_summaries()
    print(f"Loaded {len(summaries)} review summaries:")
    for s in summaries:
        print(f"  {s.book_slug:40s} | ⭐{s.weighted_average:5.2f} | "
              f"{s.total_reviews:>5d} отзывов | {s.confidence:6s} | "
              f"{s.book_title[:30]}")
    print()
    if summaries:
        first = summaries[0]
        import json as _json
        print(f"First summary sample:")
        print(_json.dumps(first.to_dict(), ensure_ascii=False, indent=2)[:1500])
