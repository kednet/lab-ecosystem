r"""
Загрузчик SEO-пакета из wish_librarian/output/library/{slug}/seo/

Источник:
  C:\Users\kfigh\wish_librarian\output\library\{slug}\seo\meta.json
  C:\Users\kfigh\wish_librarian\output\library\{slug}\seo\schema.json
  C:\Users\kfigh\wish_librarian\output\library\{slug}\seo\og.md
  C:\Users\kfigh\wish_librarian\output\library\{slug}\seo\faq.md

Используется Astro-страницами /library/[slug] и копирайтером для meta_description.
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

# ── Корень WL output ───────────────────────────────────────
WL_OUTPUT_ROOT = Path(
    r"C:\Users\kfigh\wish_librarian\output\library"
).resolve()


@dataclass
class SeoMeta:
    """Title + Description + slug из seo/meta.json."""
    title: str = ""
    description: str = ""
    slug: str = ""
    keywords: list[str] = field(default_factory=list)
    canonical: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class SeoSchema:
    """JSON-LD блок из seo/schema.json (@graph: Book, BreadcrumbList, FAQPage, Review)."""
    graph: list[dict] = field(default_factory=list)
    raw: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)

    def find(self, type_name: str) -> Optional[dict]:
        """Найти @type в @graph."""
        for node in self.graph:
            if node.get("@type") == type_name:
                return node
        return None


@dataclass
class BookMeta:
    """Базовые метаданные книги из metadata.json (источник правды WL)."""
    title: str = ""
    author: str = ""
    year: int | None = None
    short_description: str = ""
    key_ideas: list[str] = field(default_factory=list)
    quotes: list[dict] = field(default_factory=list)
    chapters: list[dict] = field(default_factory=list)
    isbn: str = ""
    page_count: int | None = None
    source_url: str = ""
    cover_url: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class SeoPackage:
    """Полный SEO-пакет для одной книги."""
    book_slug: str
    book_meta: BookMeta = field(default_factory=BookMeta)
    meta: SeoMeta = field(default_factory=SeoMeta)
    schema: SeoSchema = field(default_factory=SeoSchema)
    og_md: str = ""
    faq_md: str = ""
    keywords_md: str = ""
    seo_report_md: str = ""
    sources: dict = field(default_factory=dict)  # какие файлы найдены

    def to_dict(self) -> dict:
        return {
            "book_slug": self.book_slug,
            "book_meta": self.book_meta.to_dict(),
            "meta": self.meta.to_dict(),
            "schema": self.schema.to_dict(),
            "og_md": self.og_md,
            "faq_md": self.faq_md,
            "keywords_md": self.keywords_md,
            "seo_report_md": self.seo_report_md,
            "sources": self.sources,
        }


# ── Book slug matcher ─────────────────────────────────────
def _find_book_dir(book_slug: str, *, wl_root: Path = WL_OUTPUT_ROOT) -> Optional[Path]:
    """Ищет папку книги в WL output. По slug или по нормализованному имени."""
    if not wl_root.exists():
        return None

    # Прямое совпадение
    candidate = wl_root / book_slug
    if candidate.exists() and candidate.is_dir():
        return candidate

    # Slugified title — папки в WL именуются по-разному
    target = book_slug.lower()
    for sub in wl_root.iterdir():
        if not sub.is_dir():
            continue
        if target in sub.name.lower() or sub.name.lower() in target:
            return sub

    return None


def load_seo_package(
    book_slug: str, *, wl_root: Path = WL_OUTPUT_ROOT
) -> Optional[SeoPackage]:
    """Загрузить весь SEO-пакет по книге."""
    book_dir = _find_book_dir(book_slug, wl_root=wl_root)
    if book_dir is None:
        return None

    seo_dir = book_dir / "seo"
    pkg = SeoPackage(book_slug=book_slug)

    # metadata.json — источник правды WL (всегда есть)
    wl_meta_path = book_dir / "metadata.json"
    if wl_meta_path.exists():
        try:
            m = json.loads(wl_meta_path.read_text(encoding="utf-8"))
            pkg.book_meta = BookMeta(
                title=m.get("title", ""),
                author=m.get("author", ""),
                year=m.get("year"),
                short_description=m.get("short_description", ""),
                key_ideas=m.get("key_ideas", []),
                quotes=m.get("quotes", []),
                chapters=m.get("chapters", []),
                isbn=m.get("isbn", "") or "",
                page_count=m.get("page_count"),
                source_url=m.get("source_url", "") or "",
                cover_url=m.get("cover_url", "") or "",
            )
            pkg.sources["metadata"] = str(wl_meta_path)
        except Exception as e:
            print(f"  ! Failed to parse {wl_meta_path}: {e}", file=sys.stderr)

    # meta.json (опционально)
    meta_path = seo_dir / "meta.json"
    if meta_path.exists():
        try:
            m = json.loads(meta_path.read_text(encoding="utf-8"))
            pkg.meta = SeoMeta(
                title=m.get("title", ""),
                description=m.get("description", ""),
                slug=m.get("slug", book_slug),
                keywords=m.get("keywords", []),
                canonical=m.get("canonical", ""),
            )
            pkg.sources["meta"] = str(meta_path)
        except Exception as e:
            print(f"  ! Failed to parse {meta_path}: {e}", file=sys.stderr)

    # schema.json
    schema_path = seo_dir / "schema.json"
    if schema_path.exists():
        try:
            s = json.loads(schema_path.read_text(encoding="utf-8"))
            graph = s.get("@graph", [])
            pkg.schema = SeoSchema(graph=graph, raw=s)
            pkg.sources["schema"] = str(schema_path)
        except Exception as e:
            print(f"  ! Failed to parse {schema_path}: {e}", file=sys.stderr)

    # og.md
    og_path = seo_dir / "og.md"
    if og_path.exists():
        pkg.og_md = og_path.read_text(encoding="utf-8")
        pkg.sources["og"] = str(og_path)

    # faq.md
    faq_path = seo_dir / "faq.md"
    if faq_path.exists():
        pkg.faq_md = faq_path.read_text(encoding="utf-8")
        pkg.sources["faq"] = str(faq_path)

    # keywords.md
    kw_path = seo_dir / "keywords.md"
    if kw_path.exists():
        pkg.keywords_md = kw_path.read_text(encoding="utf-8")
        pkg.sources["keywords"] = str(kw_path)

    # seo-report.md
    rep_path = seo_dir / "seo-report.md"
    if rep_path.exists():
        pkg.seo_report_md = rep_path.read_text(encoding="utf-8")
        pkg.sources["seo_report"] = str(rep_path)

    return pkg


# ── CLI: smoke test ───────────────────────────────────────
if __name__ == "__main__":
    if not WL_OUTPUT_ROOT.exists():
        print(f"WL output not found: {WL_OUTPUT_ROOT}")
        sys.exit(1)

    book_dirs = [d for d in WL_OUTPUT_ROOT.iterdir() if d.is_dir()]
    print(f"Found {len(book_dirs)} book dirs in WL output")
    print()

    for book_dir in sorted(book_dirs)[:5]:
        slug = book_dir.name
        pkg = load_seo_package(slug)
        if pkg is None:
            print(f"  {slug:60s} — no pkg")
            continue
        print(f"  {slug:60s}")
        print(f"    title: {pkg.meta.title[:60]}")
        print(f"    description: {pkg.meta.description[:80]}")
        print(f"    schema: {[n.get('@type') for n in pkg.schema.graph]}")
        print(f"    sources: {list(pkg.sources.keys())}")
