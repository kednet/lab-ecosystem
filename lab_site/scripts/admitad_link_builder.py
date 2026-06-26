#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
admitad_link_builder.py — генерирует buy_links.md с партнёрскими ссылками
для книг в /src/data/books/ и в WL output/library/.

Зачем:
  - В блоке «Где купить» на странице книги (/library/<slug>/) хотим
    deeplink'и с admitad_uid, чтобы получать комиссию.
  - WL-агент раньше генерил файл с плейсхолдерами партнёров
    («Литрес (партнёр: 123456789)»). Этот скрипт — замена,
    прицельно под наш кабинет Admitad.

Что делает:
  1. Берёт список книг из src/data/books.json.
  2. По каждой книге ищет папку с MD: сначала src/data/books/<slug>/,
     иначе source_path из books.json (WL-папка).
  3. Если buy_links.md уже есть и не указан --force — пропускает.
  4. Генерирует buy_links.md с шаблонами из admitad_config.json.
  5. Если указано --book=<slug> — обрабатывает только эту книгу.

Запуск:
  # одна книга (превью)
  python scripts/admitad_link_builder.py --book=transerfing-realnosti

  # все книги
  python scripts/admitad_link_builder.py --all

  # принудительно перезаписать
  python scripts/admitad_link_builder.py --all --force

Конфиг (scripts/admitad_config.json) обновляется вручную, когда:
  - получаем новый admitad_uid из ЛК
  - подключаем новую партнёрку (Альпина, Book24 и т.д.)
  - меняется deeplink-формат магазина

Закон РФ о рекламе:
  Каждая ссылка помечается как реклама, плюс блок «Маркировка».
  Erid и ИНН рекламодателя берутся из admitad_config.json
  (поле marker.erid, marker.advertiser_inn).
"""

import argparse
import json
import os
import sys
import io
from pathlib import Path

# Фикс для Windows-консоли (cp1252 не вывозит эмодзи/кириллицу в print).
if sys.platform == "win32":
    try:
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8")
    except Exception:
        pass
from urllib.parse import quote
from datetime import datetime, timezone

# Пути — корень проекта
PROJECT_ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = PROJECT_ROOT / "scripts" / "admitad_config.json"
BOOKS_JSON = PROJECT_ROOT / "src" / "data" / "books.json"
BOOKS_DIR = PROJECT_ROOT / "src" / "data" / "books"


def load_config() -> dict:
    if not CONFIG_PATH.exists():
        print(f"❌ Не найден конфиг: {CONFIG_PATH}")
        print("   Создай scripts/admitad_config.json по образцу (см. README ниже).")
        sys.exit(1)
    with CONFIG_PATH.open("r", encoding="utf-8") as f:
        return json.load(f)


def load_books() -> list[dict]:
    if not BOOKS_JSON.exists():
        print(f"❌ Не найден books.json: {BOOKS_JSON}")
        sys.exit(1)
    with BOOKS_JSON.open("r", encoding="utf-8") as f:
        data = json.load(f)
    return data.get("books", [])


def find_book_dir(slug: str, source_path: str | None) -> Path | None:
    """Ищет папку с MD-контентом книги. Аналог loadMD() в src/lib/books.ts."""
    candidates: list[Path] = []
    candidates.append(BOOKS_DIR / slug)
    if source_path:
        sp = Path(source_path)
        candidates.append(sp)
        # wl_dir рядом с books.json
        wl_dir_name = sp.name
        if wl_dir_name:
            candidates.append(BOOKS_DIR / wl_dir_name)
    for c in candidates:
        if c.exists() and c.is_dir():
            return c
    return None


def build_query(title: str, author: str) -> str:
    return f"{title} {author}"


def build_url(template: str, query: str, uid: str, erid: str = "") -> str:
    """Подставляет {query_encoded}, {uid}, {erid} в шаблон deeplink.
    Для codeaven.com шаблон НЕ использует query — Admitad атрибутирует по cookie,
    пользователь попадает на главную МИФ и сам ищет книгу."""
    return template.format(
        query_encoded=quote(query, safe=""),
        uid=uid,
        erid=erid,
    )


def render_buy_links(
    title: str,
    author: str,
    stores: dict,
    uid: str,
    erid: str = "",
    marker: dict | None = None,
    source_label: str = "WishLibrarian",
) -> str:
    """Генерирует markdown для вкладки «Где купить».

    Если в `stores` передан только не-admitad-партнёр (admitad_partner=null),
    блок маркировки ФЗ-347 не выводится — это обычная ссылка.
    """
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    query = build_query(title, author)
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    # Рекламный блок (ФЗ-347 «О рекламе»).
    # Выводим только если среди активных магазинов есть хотя бы один с admitad-партнёром.
    if marker is None:
        marker = {}
    has_admitad_store = any(s.get("admitad_partner") for s in stores.values())
    if has_admitad_store:
        erid = marker.get("erid", "PENDING")
        advertiser_name = marker.get("advertiser_name", "")
        advertiser_inn = marker.get("advertiser_inn", "—")
        if erid in ("PENDING", "", None):
            marker_line = (
                f"_Рекламная ссылка. Партнёр: {advertiser_name} (ИНН {advertiser_inn}). "
                f"Маркировка (erid) оформляется через Admitad ОРД._"
            )
        else:
            marker_line = f"_Реклама. {advertiser_name}, ИНН {advertiser_inn}. Erid: {erid}._"
    else:
        marker_line = None

    lines: list[str] = [
        f"# 🛒 Где купить: {title}",
        "",
        f"_{author}_",
        "",
        "Партнёрские ссылки на книжные магазины. Покупая по этим ссылкам, вы поддерживаете проект «ЛАБОРАТОРИЯ ЖЕЛАНИЙ» — нам начисляется небольшая комиссия, для вас цена не меняется.",
        "",
    ]
    if marker_line:
        lines.extend([marker_line, ""])

    for store_id, store in stores.items():
        store_name = store.get("name", store_id)
        store_template = store["url_template"]
        url = build_url(store_template, query, uid, erid=erid)
        # Если UID не задан — отметим как заглушку
        if uid in ("UID_TBD", "PENDING", ""):
            url_note = " _(UID не задан — ссылка не будет работать)_"
        else:
            url_note = ""

        # Показываем admitad-партнёра, если есть
        partner = store.get("admitad_partner")
        partner_tag = f" `(партнёр: {partner})`" if partner else ""

        lines.append(f"## {store_name}{partner_tag}{url_note}")
        lines.append("")
        lines.append(f"[🔗 Перейти в магазин]({url})")
        lines.append("")

    lines.append("---")
    lines.append("")
    lines.append(f"_Сгенерировано {source_label} • {now}_")
    lines.append("")

    return "\n".join(lines)


def process_book(book: dict, config: dict, force: bool) -> tuple[str, str]:
    """
    Возвращает (status, message), где status ∈ {ok, skip, err, no_dir}.
    """
    slug = book["slug"]
    title = book["title"]
    author = book["author"]
    source_path = book.get("source_path")

    book_dir = find_book_dir(slug, source_path)
    if not book_dir:
        return ("no_dir", f"нет папки с MD для {slug}")

    target = book_dir / "buy_links.md"
    if target.exists() and not force:
        return ("skip", f"{slug}: уже есть (use --force)")

    # Выбор набора магазинов: per-book override или дефолт
    overrides = config.get("book_overrides", {})
    override = overrides.get(slug)
    if override and "stores" in override:
        store_ids = override["stores"]
        active_stores = {sid: config["stores"][sid] for sid in store_ids if sid in config["stores"]}
        used = "override"
    else:
        active_stores = config["stores"]
        used = "default"

    content = render_buy_links(
        title=title,
        author=author,
        stores=active_stores,
        uid=config["admitad_uid"],
        erid=config.get("marker", {}).get("erid", ""),
        marker=config.get("marker", {}),
    )
    target.write_text(content, encoding="utf-8")
    return ("ok", f"{slug}: написано в {target} [{used}: {','.join(active_stores.keys())}]")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--all", action="store_true", help="обработать все книги")
    g.add_argument("--book", metavar="SLUG", help="одна книга (по slug из books.json)")
    ap.add_argument("--force", action="store_true", help="перезаписать существующий buy_links.md")
    args = ap.parse_args()

    config = load_config()
    books = load_books()
    print(f"📚 Книг в books.json: {len(books)}")
    print(f"🔑 UID: {config['admitad_uid']}  Сторов: {list(config['stores'].keys())}")

    if args.book:
        targets = [b for b in books if b["slug"] == args.book]
        if not targets:
            print(f"❌ Slug {args.book!r} не найден в books.json")
            return 1
    else:
        targets = books

    counts = {"ok": 0, "skip": 0, "no_dir": 0, "err": 0}
    for book in targets:
        status, msg = process_book(book, config, args.force)
        counts[status] = counts.get(status, 0) + 1
        icon = {"ok": "✅", "skip": "⏭", "no_dir": "⚠️", "err": "❌"}.get(status, "?")
        print(f"  {icon} {msg}")

    print()
    print("---")
    print(f"✅ записано: {counts['ok']}  ⏭ пропущено: {counts['skip']}  "
          f"⚠️ нет папки: {counts['no_dir']}  ❌ ошибок: {counts['err']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
