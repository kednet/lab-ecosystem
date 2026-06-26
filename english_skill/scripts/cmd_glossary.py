"""
cmd_glossary.py — IT-глоссарий + импортированный словарь xlsx.

Источники:
  - data/it_glossary.yaml     — 80 must-know фраз по 8 темам (meetings, standup, ...)
  - data/it_terms_xlsx.yaml   — 244 термина из рабочего xlsx, 12 тем (базовая лексика, ...)

--source=xlsx|main  — выбрать набор (default: main)
--topic=X            — фильтр по группе
--export=csv         — экспорт в CSV для Anki
--word=deploy        — быстрый перевод одного слова (RU→EN и EN→RU)
"""
from pathlib import Path
import csv

from _english_common import fix_utf8, ensure_dirs, print_header, print_section, load_yaml, DATA_DIR, TMP_DIR


# === Источники (2 файла) ===

SOURCES = {
    "main": DATA_DIR / "it_glossary.yaml",
    "xlsx": DATA_DIR / "it_terms_xlsx.yaml",
}


def list_sources() -> list:
    """Возвращает доступные source-ключи (те, чьи файлы существуют)."""
    return [k for k, p in SOURCES.items() if p.exists()]


def _resolve_source(source: str | None) -> str:
    """Возвращает ключ source (default = main). Если файла нет — fallback на доступный."""
    if source and source in SOURCES and SOURCES[source].exists():
        return source
    # default = main, но если его нет — берём xlsx
    if not SOURCES["main"].exists() and SOURCES["xlsx"].exists():
        return "xlsx"
    return "main"


def _load(source: str = None) -> dict:
    """Загружает указанный glossary, возвращает dict с ключами meta/groups."""
    src = _resolve_source(source)
    return load_yaml(SOURCES[src])


def list_groups(source: str = None) -> list:
    """Возвращает список групп в выбранном наборе."""
    return [g["name"] for g in _load(source).get("groups", [])]


def get_group(name: str, source: str = None) -> dict:
    """Возвращает группу по name или None."""
    for g in _load(source).get("groups", []):
        if g["name"] == name:
            return g
    return None


def find_word(word: str) -> list:
    """Ищет слово во всех источниках. Возвращает список совпадений."""
    word_low = word.lower().strip()
    out = []
    for src_key in list_sources():
        data = _load(src_key)
        for g in data.get("groups", []):
            for p in g.get("phrases", []):
                phrase = p.get("phrase", "")
                # Совпадение: точное вхождение в EN или в RU переводе
                en_match = word_low in phrase.lower()
                ru_match = word_low in p.get("translation_ru", "").lower()
                if en_match or ru_match:
                    out.append({
                        "source": src_key,
                        "group": g.get("title", g["name"]),
                        "phrase": phrase,
                        "translation_ru": p.get("translation_ru", ""),
                        "example_en": p.get("example_en", ""),
                        "example_ru": p.get("example_ru", ""),
                    })
    return out


def _render_group(group: dict, full: bool = False) -> str:
    """Рендерит одну группу в markdown."""
    lines = []
    lines.append(f"## 📚 {group.get('title', group['name'])}")
    if group.get("description"):
        lines.append(f"_{group['description']}_")
    lines.append("")
    lines.append(f"Фраз: {len(group.get('phrases', []))}")
    lines.append("")

    lines.append("| Фраза | Перевод | Пример |")
    lines.append("|---|---|---|")
    for p in group.get("phrases", []):
        phrase = p.get("phrase", "")
        trans = p.get("translation_ru", "")
        ex_en = p.get("example_en", "")
        ex_ru = p.get("example_ru", "")
        if ex_en and ex_ru:
            example = f"_{ex_en}_ → {ex_ru}"
        elif ex_en or ex_ru:
            example = f"_{ex_en or ex_ru}_"
        else:
            example = "—"
        if full and p.get("tags"):
            example = f"{example}  \n`tags:` {', '.join(p['tags'])}"
        lines.append(f"| **{phrase}** | {trans} | {example} |")

    return "\n".join(lines)


def _export_csv(group_name: str | None, source: str = None) -> Path:
    """Экспортирует глоссарий (или одну группу) в CSV (Anki-compatible)."""
    src = _resolve_source(source)
    data = _load(src)
    groups = data.get("groups", [])
    if group_name:
        groups = [g for g in groups if g["name"] == group_name]

    out_dir = TMP_DIR / "glossary_export"
    out_dir.mkdir(parents=True, exist_ok=True)
    suffix_parts = [src]
    if group_name:
        suffix_parts.append(group_name)
    suffix = "_" + "_".join(suffix_parts)
    out_path = out_dir / f"glossary{suffix}.csv"

    with open(out_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["group", "phrase", "translation_ru", "example_en", "example_ru", "tags"])
        for g in groups:
            for p in g.get("phrases", []):
                writer.writerow([
                    g["name"],
                    p.get("phrase", ""),
                    p.get("translation_ru", ""),
                    p.get("example_en", ""),
                    p.get("example_ru", ""),
                    ", ".join(p.get("tags", []) or []),
                ])

    return out_path


def _word_lookup(word: str) -> None:
    """Печатает результаты поиска слова."""
    matches = find_word(word)
    if not matches:
        print(f"❌ Слово '{word}' не найдено ни в одном наборе.")
        return

    print_header(f"🔍 Перевод: {word}")
    print(f"Найдено совпадений: {len(matches)}")
    print()

    for m in matches[:15]:  # лимит 15
        print(f"### {m['phrase']}")
        print(f"**Перевод:** {m['translation_ru']}")
        if m['example_en']:
            print(f"**Пример:** _{m['example_en']}_")
            if m['example_ru']:
                print(f"         → {m['example_ru']}")
        print(f"**Группа:** {m['group']} (`{m['source']}`)")
        print()
    if len(matches) > 15:
        print(f"_…и ещё {len(matches) - 15} совпадений_")
        print()


def run(args) -> int:
    fix_utf8()
    ensure_dirs()

    topic = getattr(args, "topic", None)
    export = getattr(args, "export", None)
    source = getattr(args, "source", None)
    word = getattr(args, "word", None)

    # === --word=deploy (быстрый перевод) ===
    if word:
        _word_lookup(word)
        return 0

    src = _resolve_source(source)

    # === --export=csv ===
    if export:
        out_path = _export_csv(topic, src)
        n = sum(len(g.get("phrases", []))
                for g in _load(src).get("groups", [])
                if not topic or g["name"] == topic)
        scope = f"группы `{topic}`" if topic else "весь набор"
        src_label = "xlsx-словарь (244 термина)" if src == "xlsx" else "main-глоссарий (80 фраз)"
        print(f"✅ Экспортировано {n} фраз ({scope}, {src_label})")
        print(f"📄 CSV: `{out_path.relative_to(Path.cwd())}`")
        print()
        print("💡 Импорт в Anki: File → Import → выбери CSV → ")
        print("   Field 1 = phrase, Field 2 = translation_ru, Field 3 = example_en")
        return 0

    # === --topic=X ===
    if topic:
        group = get_group(topic, src)
        if not group:
            print(f"❌ Группа '{topic}' не найдена в `{src}`.")
            print(f"Доступные в `{src}`: {', '.join(list_groups(src))}")
            return 1
        print_header(f"IT Glossary [{src}]: {group.get('title', topic)}")
        print(_render_group(group, full=True))
        return 0

    # === Сводка (default) ===
    data = _load(src)
    groups = data.get("groups", [])
    total = sum(len(g.get("phrases", [])) for g in groups)

    src_title = "📚 IT Glossary (main, 8 тем)" if src == "main" else "📚 Словарь из xlsx (12 тем)"
    print_header(src_title)
    print(f"Всего: {len(groups)} групп, {total} фраз")
    print()

    for g in groups:
        print(_render_group(g, full=False))
        print()
        print("---")
        print()

    print("## Как использовать")
    print()
    print(f"1. Сменить набор: `--source=xlsx` (244 термина из рабочего файла) или `--source=main` (default)")
    print(f"2. Фильтр: `glossary --source=xlsx --topic=core-dev`")
    print(f"3. Одно слово: `glossary --word=deploy` — найдёт во всех наборах")
    print(f"4. CSV для Anki: `glossary --source=xlsx --export=csv`")
    return 0
