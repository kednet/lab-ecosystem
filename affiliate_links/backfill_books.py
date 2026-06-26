"""
Backfill affiliate-поля в lab_site/src/data/books.json.

Принимает JSON-список маппингов slug → litres_url из stdin или файла,
для каждой книги добавляет блок affiliate с уже посчитанным advcake_url.

Использование:

  # Из файла:
  python affiliate_links/backfill_books.py urls.json

  # Из stdin:
  echo '{"books": [{"slug":"alhimik-koeluo","litres_url":"https://www.litres.ru/book/paulo-koelo/alhimik-122351/"}]}' \\
    | python affiliate_links/backfill_books.py --stdin

  # Интерактивный режим — спрашивает URL по одной книге:
  python affiliate_links/backfill_books.py --interactive

Файл urls.json имеет формат:
  {
    "books": [
      {"slug": "alhimik-koeluo", "litres_url": "https://www.litres.ru/book/.../"},
      ...
    ]
  }

Скрипт:
  1. Читает lab_site/src/data/books.json
  2. Для каждой книги из маппинга — генерирует advcake_url через advcake.py
  3. Атомарно перезаписывает books.json с обновлённым полем affiliate
  4. Помечает updated_at на текущий момент

ВАЖНО: при `books.json` сначала делается бэкап `books.json.bak`.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

# Чтобы работали относительные импорты при запуске из любой cwd:
_HERE = Path(__file__).parent
sys.path.insert(0, str(_HERE.parent))

from affiliate_links.advcake import (
    build_litres_url,
    make_book_affiliate,
    cache_book,
)


BOOKS_JSON = (
    _HERE.parent / "lab_site" / "src" / "data" / "books.json"
)


def _now_iso_z() -> str:
    """ISO 8601 в UTC с 'Z' на конце (как принято в books.json)."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _load_books() -> dict:
    return json.loads(BOOKS_JSON.read_text(encoding="utf-8"))


def _save_books(data: dict) -> None:
    BOOKS_JSON.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _backup() -> Path:
    backup = BOOKS_JSON.with_suffix(".json.bak")
    backup.write_text(BOOKS_JSON.read_text(encoding="utf-8"), encoding="utf-8")
    return backup


def _set_affiliate(books_data: dict, mapping: dict) -> tuple[int, list[str]]:
    """Обновить блок affiliate у книг из mapping.

    Returns: (количество обновлённых, список slug-ов, которые не найдены).
    """
    by_slug = {b["slug"]: b for b in books_data["books"]}
    updated = 0
    not_found: list[str] = []
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    for entry in mapping:
        slug = entry["slug"]
        litres_url = entry["litres_url"].strip()
        if slug not in by_slug:
            not_found.append(slug)
            continue
        subid = entry.get("subid") or f"site_{today}_{slug}"
        aff = make_book_affiliate(slug, litres_url, subid=subid)
        by_slug[slug]["affiliate"] = {
            "litres_url": aff.litres_url,
            "advcake_url": aff.advcake_url,
            "erid": aff.erid,
            "advcake_hash": aff.hash,
            "advertiser": {
                "name": "ООО ЛИТРЕС",
                "inn": "7719571260",
            },
            "subid": subid,
            "updated_at": _now_iso_z(),
        }
        cache_book(aff)
        updated += 1
    if updated:
        books_data["updated_at"] = today
    return updated, not_found


def _from_file(path: Path) -> list[dict]:
    return json.loads(path.read_text(encoding="utf-8")).get("books", [])


def _from_stdin() -> list[dict]:
    raw = sys.stdin.read()
    data = json.loads(raw) if raw.strip() else {}
    if isinstance(data, list):
        return data
    return data.get("books", [])


def _from_interactive(books: list[dict]) -> list[dict]:
    """Спросить URL у пользователя по одной книге."""
    print(f"\nВ books.json {len(books)} книг. Введи litres_url для каждой "
          f"(Enter = пропустить, 'q' = выход).\n", file=sys.stderr)
    out = []
    for b in books:
        existing = b.get("affiliate", {}).get("litres_url", "")
        prompt = f"  {b['slug']:40s}  [{b['title'][:30]}]\n    URL [{existing}]: "
        try:
            ans = input(prompt).strip()
        except EOFError:
            break
        if ans.lower() in ("q", "quit", "exit", ""):
            if ans == "" and existing:
                # Оставляем как есть — backfill не трогает
                continue
            if ans == "":
                continue
            break
        out.append({"slug": b["slug"], "litres_url": ans})
    return out


def main() -> int:
    p = argparse.ArgumentParser(description="Backfill affiliate в books.json")
    p.add_argument("file", nargs="?", default=None,
                   help="JSON с маппингом slug → litres_url")
    p.add_argument("--stdin", action="store_true")
    p.add_argument("--interactive", action="store_true")
    p.add_argument("--dry-run", action="store_true",
                   help="не записывать books.json, только показать diff")
    args = p.parse_args()

    books = _load_books()
    if args.file:
        mapping = _from_file(Path(args.file))
    elif args.stdin:
        mapping = _from_stdin()
    elif args.interactive:
        mapping = _from_interactive(books["books"])
    else:
        p.error("укажи файл, --stdin или --interactive")

    if not mapping:
        print("Нет данных для backfill.", file=sys.stderr)
        return 1

    updated, not_found = _set_affiliate(books, mapping)
    print(f"\nГотово: обновлено {updated} книг, не найдено {len(not_found)}",
          file=sys.stderr)
    if not_found:
        print(f"  not found: {', '.join(not_found)}", file=sys.stderr)

    if args.dry_run:
        # Покажем только обновлённые куски
        result = {
            "updated_at": books["updated_at"],
            "books": [
                {k: v.get("affiliate") for k, v in [
                    ("affiliate", b) for b in books["books"]
                    if b.get("slug") in {m["slug"] for m in mapping}
                ]}
            ],
        }
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0

    backup = _backup()
    _save_books(books)
    print(f"Backup → {backup}", file=sys.stderr)
    print(f"Saved → {BOOKS_JSON}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())