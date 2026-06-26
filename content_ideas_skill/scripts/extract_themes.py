#!/usr/bin/env python3
"""
extract_themes.py — извлечение тем из источников (LLM).

Источники:
  --source wl          — книги из WishLibrarian (C:\\Users\\kfigh\\wish_librarian\\output\\library)
  --source coach       — модули WishCoach (C:\\Users\\kfigh\\coach_agent\\) — stub
  --source competitors — посты конкурентов (data/competitors/<group>/posts.json) — stub

Использование:
  python extract_themes.py --source wl                       # все книги
  python extract_themes.py --source wl --book-id "transerfing-realnosti"
  python extract_themes.py --source wl --limit 5             # первые 5 книг
  python extract_themes.py --source wl --offline             # без LLM
  python extract_themes.py --source wl --update-bank         # обновить sources/books-from-wl.md

Выход:
  data/themes/<source>-themes.json   — детальный JSON (темы + цитаты + практики)
  data/themes/<source>-themes.md     — markdown-сводка
  sources/books-from-wl.md           — обновляется с --update-bank (только для wl)

Статус: v0.2 — реальный LLM-анализ для WL.
"""

import argparse
import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional, Iterable

# Force UTF-8 output on Windows
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass

# Добавляем scripts/lib в sys.path для импорта llm_client
sys.path.insert(0, str(Path(__file__).parent / "lib"))

SKILL_DIR = Path(__file__).parent.parent
DATA_DIR = SKILL_DIR / "data"
THEMES_DIR = DATA_DIR / "themes"
SOURCES_DIR = SKILL_DIR / "sources"

# Пути к зависимым скилам (из config.yaml)
WL_LIBRARY = Path("C:/Users/kfigh/wish_librarian/output/library")
COACH_DIR = Path("C:/Users/kfigh/coach_agent")


# ==== Общие утилиты ====

def safe_read_text(path: Path, max_chars: int = 4000) -> str:
    """Безопасно прочитать текст, обрезав до max_chars."""
    if not path.exists():
        return ""
    try:
        text = path.read_text(encoding="utf-8").strip()
    except (UnicodeDecodeError, OSError):
        return ""
    if len(text) > max_chars:
        text = text[: max_chars - 100] + "\n\n[…truncated…]"
    return text


def parse_json_strict(text: str) -> Any:
    """Распарсить JSON из LLM-ответа. Терпимо к ```json обёрткам и лишнему тексту.

    Поддерживает ответы 3 видов:
      - {"themes": [...]} (dict с массивом внутри)
      - [...] (голый массив)
      - ```json ... ``` обёрнутый в markdown
    """
    if not text:
        return None
    t = text.strip()
    t = re.sub(r"^```(?:json)?\s*", "", t)
    t = re.sub(r"\s*```\s*$", "", t)
    t = t.strip()

    # 1) Сначала пытаемся распарсить целиком
    try:
        return json.loads(t)
    except json.JSONDecodeError:
        pass

    # 2) Если целиком не вышло — ищем первый { или [ и до парной закрывающей
    first_brace = t.find("{")
    first_bracket = t.find("[")
    if first_brace == -1 and first_bracket == -1:
        return None

    # Выбираем что раньше: dict или list
    if first_brace != -1 and (first_bracket == -1 or first_brace < first_bracket):
        # Ищем парную } через баланс скобок
        depth = 0
        end_idx = -1
        for i in range(first_brace, len(t)):
            if t[i] == "{":
                depth += 1
            elif t[i] == "}":
                depth -= 1
                if depth == 0:
                    end_idx = i
                    break
        if end_idx == -1:
            return None
        candidate = t[first_brace:end_idx + 1]
    else:
        # list — ищем парную ] через баланс
        depth = 0
        end_idx = -1
        for i in range(first_bracket, len(t)):
            if t[i] == "[":
                depth += 1
            elif t[i] == "]":
                depth -= 1
                if depth == 0:
                    end_idx = i
                    break
        if end_idx == -1:
            return None
        candidate = t[first_bracket:end_idx + 1]

    try:
        return json.loads(candidate)
    except json.JSONDecodeError:
        return None


# ==== WL (WishLibrarian) ====

def list_books(book_id: Optional[str] = None, limit: Optional[int] = None) -> List[Path]:
    """Список директорий книг в WL (только те, где есть metadata.json)."""
    if not WL_LIBRARY.exists():
        print(f"[error] {WL_LIBRARY} не найден")
        return []
    books: List[Path] = []
    for child in sorted(WL_LIBRARY.iterdir()):
        if not child.is_dir():
            continue
        if not (child / "metadata.json").exists():
            continue
        if book_id and book_id != child.name:
            continue
        books.append(child)
        if limit and len(books) >= limit:
            break
    return books


def load_book(book_dir: Path) -> Optional[Dict[str, Any]]:
    """Загрузить книгу: metadata + summary + tips + reviews."""
    meta_path = book_dir / "metadata.json"
    if not meta_path.exists():
        return None
    try:
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    return {
        "id": book_dir.name,
        "title": meta.get("title", book_dir.name),
        "author": meta.get("author", "—"),
        "year": meta.get("year"),
        "short_description": (meta.get("short_description") or "").strip(),
        "key_ideas": meta.get("key_ideas") or [],
        "quotes": meta.get("quotes") or [],
        "summary_md": safe_read_text(book_dir / "summary.md", max_chars=3500),
        "practical_tips_md": safe_read_text(book_dir / "practical_tips.md", max_chars=1500),
        "reviews_md": safe_read_text(book_dir / "reviews.md", max_chars=800),
    }


def dedupe_books(books: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Убрать дубликаты по (title|author)."""
    seen: set = set()
    out: List[Dict[str, Any]] = []
    for b in books:
        key = f"{b['title'].lower().strip()}|{b['author'].lower().strip()}"
        if key in seen:
            continue
        seen.add(key)
        out.append(b)
    return out


def build_book_prompt(book: Dict[str, Any]) -> str:
    """Промпт для LLM: извлечь темы/паттерны/цитаты-магниты/практики."""
    key_ideas_str = "\n".join(f"- {x}" for x in book["key_ideas"][:8]) or "—"
    quotes_str = "\n".join(f"- {x}" for x in book["quotes"][:5]) or "—"

    return f"""Проанализируй книгу и извлеки материал для контент-плана Лаборатории желаний (психологическое сообщество для женщин 25-45).

КНИГА: {book['title']} — {book['author']} ({book['year'] or '—'})

ОПИСАНИЕ: {book['short_description'] or '—'}

КЛЮЧЕВЫЕ ИДЕИ (из карточки):
{key_ideas_str}

ЦИТАТЫ (из карточки):
{quotes_str}

КОНСПЕКТ (фрагмент):
{book['summary_md'][:2000] or '—'}

ПРАКТИКИ (фрагмент):
{book['practical_tips_md'][:1000] or '—'}

ТВОЯ ЗАДАЧА: верни ТОЛЬКО валидный JSON (без ```json, без пояснений):

{{
  "themes": [
    {{"name": "тема 3-5 слов", "why_relevant": "почему попадёт в ЦА 1 предложение"}},
    ...минимум 3, максимум 7 тем
  ],
  "magnet_quotes": [
    "яркая цитата или её перефразировка 5-15 слов, которую можно использовать как крючок поста"
    ...1-3 штуки
  ],
  "practices": [
    {{"name": "название практики", "summary": "суть в 1 предложении", "format": "мини-урок | воркбук | эксперимент"}}
    ...1-3 штуки (если есть)
  ],
  "antipattern": "что автор ОТРИЦАЕТ (типичное заблуждение) — 1 предложение, может стать провокацией",
  "target_rubric": "ОДНА рубрика ЛЖ (разбор-цитаты | детектор | история | провокация | практика | миф-vs-правда | подборка) — какая лучше всего подходит под эту книгу"
}}

ВАЖНО:
- Язык — русский, тон — без «успешного успеха» и эзотерики
- Темы формулируй как проблемы/паттерны ЦА, а не как темы из учебника
- magnet_quotes — должны быть КОРОТКИМИ (5-15 слов), узнаваемыми, провокационными
- Если книга совсем не про желания/самопознание — верни пустые массивы
"""


def extract_themes_for_book(
    book: Dict[str, Any],
    client: Any,
) -> Dict[str, Any]:
    """Извлечь темы из одной книги через LLM."""
    prompt = build_book_prompt(book)
    try:
        response = client.generate(
            prompt,
            system="Ты контент-аналитик Лаборатории желаний. Возвращаешь ТОЛЬКО JSON.",
            max_tokens=900,
            temperature=0.5,
        )
    except Exception as e:
        print(f"  [warn] LLM ошибка для '{book['title']}': {e}")
        return _empty_book_extraction(book, error=str(e))

    parsed = parse_json_strict(response)
    if not isinstance(parsed, dict):
        return _empty_book_extraction(book, error="JSON parse failed")

    return {
        "book_id": book["id"],
        "title": book["title"],
        "author": book["author"],
        "year": book["year"],
        "themes": parsed.get("themes", []) or [],
        "magnet_quotes": parsed.get("magnet_quotes", []) or [],
        "practices": parsed.get("practices", []) or [],
        "antipattern": parsed.get("antipattern", ""),
        "target_rubric": parsed.get("target_rubric", "разбор-цитаты"),
        "raw_response_chars": len(response),
        "error": None,
    }


def _empty_book_extraction(book: Dict[str, Any], error: str = "") -> Dict[str, Any]:
    """Заглушка для случая ошибки LLM."""
    return {
        "book_id": book["id"],
        "title": book["title"],
        "author": book["author"],
        "year": book["year"],
        "themes": [],
        "magnet_quotes": book.get("quotes", [])[:2],  # fallback: берём что есть в карточке
        "practices": [],
        "antipattern": "",
        "target_rubric": "разбор-цитаты",
        "raw_response_chars": 0,
        "error": error,
    }


def extract_themes_wl(
    book_id: Optional[str] = None,
    limit: Optional[int] = None,
    use_llm: bool = True,
    progress: bool = True,
) -> List[Dict[str, Any]]:
    """Главная функция: пройтись по книгам WL, извлечь темы."""
    book_dirs = list_books(book_id=book_id, limit=limit)
    if not book_dirs:
        return []
    books = [b for b in (load_book(d) for d in book_dirs) if b]
    books = dedupe_books(books)
    print(f"[wl] Найдено {len(books)} книг (после дедупа)")

    if not use_llm:
        # Offline — просто отдаём карточки как есть
        return [
            _empty_book_extraction(b, error="offline mode") | {
                "themes": [{"name": k[:80], "why_relevant": "(offline — без LLM)"} for k in b["key_ideas"][:5]],
                "magnet_quotes": b.get("quotes", [])[:2],
                "practices": [],
            }
            for b in books
        ]

    try:
        from llm_client import LLMClient
        client = LLMClient()
        if not client.is_available():
            print(f"[warn] LLM недоступен (provider={client.provider}), fallback на offline")
            return extract_themes_wl(book_id=book_id, limit=limit, use_llm=False, progress=progress)
    except Exception as e:
        print(f"[warn] LLM init ошибка: {e}")
        return extract_themes_wl(book_id=book_id, limit=limit, use_llm=False, progress=progress)

    print(f"[llm] Извлекаю темы через {client.provider}/{client.model}...")
    results: List[Dict[str, Any]] = []
    total = len(books)
    for i, book in enumerate(books, 1):
        if progress:
            print(f"  [{i}/{total}] {book['title']} — {book['author']}")
        result = extract_themes_for_book(book, client)
        results.append(result)
    return results


# ==== Сохранение / вывод ====

def save_results(source: str, results: List[Dict[str, Any]], provider: str = "", model: str = "") -> Dict[str, Path]:
    """Сохранить JSON + Markdown. Возвращает dict с путями."""
    THEMES_DIR.mkdir(parents=True, exist_ok=True)
    paths: Dict[str, Path] = {}

    # JSON
    json_path = THEMES_DIR / f"{source}-themes.json"
    payload = {
        "version": "1.0",
        "source": source,
        "fetched": datetime.now().isoformat(),
        "llm_provider": provider,
        "llm_model": model,
        "count": len(results),
        "items": results,
    }
    json_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    paths["json"] = json_path
    print(f"[save] → {json_path}")

    # Markdown
    md_path = THEMES_DIR / f"{source}-themes.md"
    md_path.write_text(render_markdown(source, results, provider, model), encoding="utf-8")
    paths["md"] = md_path
    print(f"[save] → {md_path}")
    return paths


def render_markdown(source: str, results: List[Dict[str, Any]], provider: str, model: str) -> str:
    """Рендер markdown-сводки по всем книгам."""
    lines = [
        f"# Темы из источника: {source}",
        "",
        f"**Дата:** {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        f"**LLM:** {provider or '—'} / {model or '—'}",
        f"**Книг/источников:** {len(results)}",
        "",
        "---",
        "",
    ]
    for i, r in enumerate(results, 1):
        lines.append(f"## {i}. {r['title']}")
        lines.append(f"*{r['author']}* ({r.get('year') or '—'})")
        lines.append(f"`id: {r['book_id']}` · рубрика: **{r.get('target_rubric', '—')}**")
        lines.append("")

        themes = r.get("themes", [])
        if themes:
            lines.append("**Темы:**")
            for t in themes:
                if isinstance(t, dict):
                    lines.append(f"- {t.get('name', '')} — _{t.get('why_relevant', '')}_")
                else:
                    lines.append(f"- {t}")
            lines.append("")

        magnets = r.get("magnet_quotes", [])
        if magnets:
            lines.append("**Цитаты-магниты:**")
            for q in magnets:
                lines.append(f"> {q}")
            lines.append("")

        practices = r.get("practices", [])
        if practices:
            lines.append("**Практики:**")
            for p in practices:
                if isinstance(p, dict):
                    lines.append(f"- **{p.get('name', '')}** ({p.get('format', '—')}): {p.get('summary', '')}")
                else:
                    lines.append(f"- {p}")
            lines.append("")

        anti = r.get("antipattern", "")
        if anti:
            lines.append(f"**Антипример (что отрицает автор):** {anti}")
            lines.append("")

        if r.get("error"):
            lines.append(f"⚠️ _ошибка: {r['error']}_")
            lines.append("")
        lines.append("---")
        lines.append("")

    return "\n".join(lines)


def update_books_from_wl_md(results: List[Dict[str, Any]]) -> None:
    """Обновить sources/books-from-wl.md — реальный каталог книг с темами."""
    target = SOURCES_DIR / "books-from-wl.md"
    lines = [
        "# Источник 1: WishLibrarian — книги (v0.2)",
        "",
        f"> Авто-генерация: `python scripts/extract_themes.py --source wl --update-bank`",
        f"> Обновлено: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        f"> Книг: {len(results)}",
        "",
        "---",
        "",
        "## Назначение",
        "",
        "Карточки книг из `C:\\Users\\kfigh\\wish_librarian\\output\\library\\`,",
        "обогащённые LLM-извлечёнными темами/цитатами/практиками.",
        "Использовать как источник идей: `python generate_ideas.py --source wl --rubric ...`",
        "",
        "## Как устроено",
        "",
        "1. `extract_themes.py --source wl` читает `metadata.json` каждой книги",
        "2. Склеивает с `summary.md` + `practical_tips.md` (если есть)",
        "3. LLM возвращает JSON: `themes[]`, `magnet_quotes[]`, `practices[]`, `antipattern`, `target_rubric`",
        "4. Агрегация — в этот файл + `data/themes/wl-themes.json`",
        "",
        "## Книги (по рубрикам)",
        "",
    ]

    # Группируем по target_rubric
    by_rubric: Dict[str, List[Dict[str, Any]]] = {}
    for r in results:
        rubric = r.get("target_rubric", "—") or "—"
        by_rubric.setdefault(rubric, []).append(r)

    for rubric in sorted(by_rubric.keys()):
        items = by_rubric[rubric]
        lines.append(f"### Рубрика: {rubric} ({len(items)} книг)")
        lines.append("")
        for r in items:
            lines.append(f"#### «{r['title']}» — {r['author']} ({r.get('year') or '—'})")
            lines.append(f"`book_id: {r['book_id']}`")
            lines.append("")
            themes = r.get("themes", [])
            if themes:
                lines.append("**Темы:**")
                for t in themes[:5]:
                    if isinstance(t, dict):
                        lines.append(f"- {t.get('name', '')} — _{t.get('why_relevant', '')}_")
                    else:
                        lines.append(f"- {t}")
                lines.append("")
            magnets = r.get("magnet_quotes", [])
            if magnets:
                lines.append("**Цитаты-магниты (для крючков):**")
                for q in magnets[:3]:
                    lines.append(f"> {q}")
                lines.append("")
            practices = r.get("practices", [])
            if practices:
                lines.append("**Практики:**")
                for p in practices[:3]:
                    if isinstance(p, dict):
                        lines.append(f"- **{p.get('name', '')}** ({p.get('format', '—')}): {p.get('summary', '')}")
                    else:
                        lines.append(f"- {p}")
                lines.append("")
            anti = r.get("antipattern", "")
            if anti:
                lines.append(f"**Антипример:** _{anti}_")
                lines.append("")
            lines.append("---")
            lines.append("")

    # Топ цитат-магнитов
    all_magnets: List[Dict[str, Any]] = []
    for r in results:
        for q in r.get("magnet_quotes", []):
            all_magnets.append({"quote": q, "book": r["title"], "author": r["author"]})
    if all_magnets:
        lines.append("## 🧲 Топ цитат-магнитов (для крючков)")
        lines.append("")
        for m in all_magnets[:20]:
            lines.append(f"> {m['quote']}")
            lines.append(f"> — *{m['book']}*, {m['author']}")
            lines.append("")

    target.write_text("\n".join(lines), encoding="utf-8")
    print(f"[save] → {target} (обновлён каталог книг)")


# ==== main ====

def main() -> int:
    parser = argparse.ArgumentParser(
        description="Извлечение тем из источников (LLM)",
    )
    parser.add_argument("--source", type=str, required=True, choices=["wl", "coach", "competitors"],
                        help="Источник: wl | coach | competitors")
    parser.add_argument("--book-id", type=str, default=None,
                        help="WL: ID книги (папка в output/library)")
    parser.add_argument("--module", type=int, default=None,
                        help="Coach: ID модуля (пока не реализовано)")
    parser.add_argument("--group", type=str, default=None,
                        help="Competitors: имя группы")
    parser.add_argument("--limit", type=int, default=None,
                        help="Ограничить кол-во книг (для теста / экономии токенов)")
    parser.add_argument("--offline", action="store_true",
                        help="Без LLM (только структура из metadata.json)")
    parser.add_argument("--update-bank", action="store_true",
                        help="Обновить sources/books-from-wl.md (только для --source wl)")
    parser.add_argument("--output", type=str, default=None,
                        help="Доп. путь для JSON-результата")

    args = parser.parse_args()

    if args.source == "coach":
        print("[stub] coach — пока не реализовано (см. coach_agent/PRD.md)")
        return 1
    if args.source == "competitors":
        print("[stub] competitors — пока не реализовано (используйте mine_audience_pains.py)")
        return 1

    # === WL ===
    provider = ""
    model = ""
    if not args.offline:
        try:
            from llm_client import LLMClient
            _client = LLMClient()
            provider = _client.provider
            model = _client.model
        except Exception:
            pass

    results = extract_themes_wl(
        book_id=args.book_id,
        limit=args.limit,
        use_llm=not args.offline,
    )

    if not results:
        print("[error] Не удалось получить ни одной книги")
        return 1

    paths = save_results("wl", results, provider=provider, model=model)

    if args.output:
        import shutil
        out_path = Path(args.output)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(paths["json"], out_path)
        print(f"[copy] → {out_path}")

    if args.update_bank:
        update_books_from_wl_md(results)

    # Сводка
    print()
    print("=" * 60)
    print(f"Готово. Книг: {len(results)}")
    total_themes = sum(len(r.get('themes', [])) for r in results)
    total_magnets = sum(len(r.get('magnet_quotes', [])) for r in results)
    total_practices = sum(len(r.get('practices', [])) for r in results)
    print(f"  Тем: {total_themes}")
    print(f"  Цитат-магнитов: {total_magnets}")
    print(f"  Практик: {total_practices}")
    by_rubric: Dict[str, int] = {}
    for r in results:
        r_ = r.get("target_rubric", "—")
        by_rubric[r_] = by_rubric.get(r_, 0) + 1
    print("  По рубрикам:")
    for r_, c in sorted(by_rubric.items(), key=lambda x: -x[1]):
        print(f"    {r_}: {c}")
    print("=" * 60)
    return 0


if __name__ == "__main__":
    sys.exit(main())
