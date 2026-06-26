r"""
Загрузчик карточек экспертов из expert-reviews-hub.

Источник:
  C:\Users\kfigh\expert-reviews-hub\experts\{slug}.md

Формат карточки — markdown с frontmatter (см. expert-reviews-hub/templates/expert-card.md).
"""
from __future__ import annotations

import json
import re
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
EXPERTS_HUB_ROOT = Path(
    r"C:\Users\kfigh\expert-reviews-hub"
).resolve()


@dataclass
class ExpertCard:
    """Структурированная карточка эксперта для публикации на сайте."""
    slug: str
    name: str
    jobTitle: str = ""
    description: str = ""
    url: str = ""
    image: str = ""
    email: str = ""
    sameAs: list[str] = field(default_factory=list)        # соцсети
    knowsAbout: list[str] = field(default_factory=list)    # навыки
    alumniOf: list[str] = field(default_factory=list)       # вузы
    awards: list[str] = field(default_factory=list)
    worksFor: str = ""                                     # место работы
    quotes: list[dict] = field(default_factory=list)       # [{quote, source, year}]
    media: dict = field(default_factory=dict)              # {youtube, telegram, vk}
    tags: list[str] = field(default_factory=list)
    score: int = 0                                         # 0-100
    schema_jsonld: dict = field(default_factory=dict)      # Schema.org Person
    source_md: str = ""                                    # оригинальный MD
    source_path: str = ""                                  # путь к .md
    recommended_books: list[dict] = field(default_factory=list)  # [{slug, title, context}]
    generated_at: str = ""
    featured_video: str = ""                               # YouTube video ID (11 chars)

    def to_dict(self) -> dict:
        return {k: v for k, v in asdict(self).items() if k not in ("source_md",)}


# ── Frontmatter парсер (минимальный YAML) ─────────────────
_FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n(.*)$", re.DOTALL)


def _parse_frontmatter(text: str) -> tuple[dict, str]:
    """Возвращает (frontmatter_dict, body). Пустой dict если нет frontmatter."""
    m = _FRONTMATTER_RE.match(text)
    if not m:
        return {}, text
    fm_raw, body = m.group(1), m.group(2)

    # Простой YAML-парсер: key: value, списки через [...]
    fm = {}
    list_buffer_key = None
    list_buffer_indent = None
    for line in fm_raw.splitlines():
        if not line.strip():
            continue
        # Список (item) с отступом 2+ пробела и "- "
        if line.lstrip().startswith("- ") and list_buffer_key:
            val = line.lstrip()[2:].strip().strip('"').strip("'")
            fm.setdefault(list_buffer_key, []).append(val)
            continue
        # Ключ: значение
        m2 = re.match(r"^([\w_-]+):\s*(.*)$", line)
        if not m2:
            continue
        key, val = m2.group(1), m2.group(2).strip()
        if not val:
            list_buffer_key = key
            list_buffer_indent = None
            fm.setdefault(key, [])
        else:
            list_buffer_key = None
            val = val.strip('"').strip("'")
            fm[key] = val
    return fm, body


# ── Секции body ───────────────────────────────────────────
def _parse_sections(body: str) -> dict[str, str]:
    """Парсит секции вида '## 📋 Основное' → {'📋 Основное': '...'}"""
    sections: dict[str, str] = {}
    current_key = None
    current_lines: list[str] = []
    for line in body.splitlines():
        m = re.match(r"^##\s+(.+)$", line)
        if m:
            if current_key is not None:
                sections[current_key] = "\n".join(current_lines).strip()
            current_key = m.group(1).strip()
            current_lines = []
        else:
            current_lines.append(line)
    if current_key is not None:
        sections[current_key] = "\n".join(current_lines).strip()
    return sections


def _parse_table(section: str) -> dict[str, str]:
    """Парсит markdown-таблицу → {key: value}."""
    table: dict[str, str] = {}
    in_table = False
    for line in section.splitlines():
        if "|" in line and "---" not in line:
            parts = [p.strip() for p in line.split("|") if p.strip()]
            if len(parts) >= 2 and not in_table:
                in_table = True
            if len(parts) >= 2 and in_table:
                # первая строка — заголовки, вторая — данные
                # здесь мы обрабатываем только строки формата "| **Поле** | Значение |"
                if parts[0].startswith("**") and ":" not in parts[0]:
                    key = parts[0].strip("*").strip()
                    val = " ".join(parts[1:]).strip()
                    if key and val:
                        table[key] = val
        elif "---" in line:
            in_table = False
    return table


def _parse_quotes(section: str) -> list[dict]:
    """Парсит секцию '💬 Цитаты' → [{quote, source, year}]."""
    quotes = []
    blocks = re.split(r"(?:^|\n)> «", section)
    for block in blocks[1:]:
        # block = "цитата»\n> — Автор, источник, год"
        end = block.find("»")
        if end < 0:
            continue
        quote = block[:end].strip()
        rest = block[end + 1:].strip()
        # Убираем "— " в начале
        rest = re.sub(r"^> ?—\s*", "", rest).strip()
        # Парсим "Автор, источник, год" или "— контекст, год"
        parts = [p.strip() for p in rest.split(",")]
        if len(parts) >= 2:
            author = parts[0]
            source = parts[1] if len(parts) >= 2 else ""
            year_m = re.search(r"(\d{4})", rest)
            year = int(year_m.group(1)) if year_m else None
        else:
            author, source, year = rest, "", None
        quotes.append({
            "quote": quote,
            "author": author,
            "source": source,
            "year": year,
        })
    return quotes


def _parse_media(section: str) -> dict:
    """Парсит секцию '🎙️ Медиа' → {youtube, telegram, vk}."""
    media: dict[str, str] = {}
    for line in section.splitlines():
        m = re.search(r"\[([^\]]+)\]\((https?://[^\)]+)\)", line)
        if not m:
            continue
        name = m.group(1).lower()
        url = m.group(2)
        if "youtube" in url or "youtu.be" in url:
            media["youtube"] = url
        elif "t.me" in url or "telegram" in url:
            media["telegram"] = url
        elif "vk.com" in url:
            media["vk"] = url
    return media


def _parse_schema_jsonld(body: str) -> dict:
    """Извлекает JSON-LD блок ```json ... ``` с типом Person."""
    blocks = re.findall(r"```json\s*\n(.*?)```", body, re.DOTALL)
    for raw in blocks:
        try:
            obj = json.loads(raw)
        except Exception:
            continue
        if isinstance(obj, dict) and obj.get("@type") == "Person":
            return obj
    return {}


# ── Slugify ───────────────────────────────────────────────
def _slugify(text: str) -> str:
    table = {
        'а': 'a', 'б': 'b', 'в': 'v', 'г': 'g', 'д': 'd', 'е': 'e', 'ё': 'e',
        'ж': 'zh', 'з': 'z', 'и': 'i', 'й': 'i', 'к': 'k', 'л': 'l', 'м': 'm',
        'н': 'n', 'о': 'o', 'п': 'p', 'р': 'r', 'с': 's', 'т': 't', 'у': 'u',
        'ф': 'f', 'х': 'h', 'ц': 'ts', 'ч': 'ch', 'ш': 'sh', 'щ': 'shch',
        'ъ': '', 'ы': 'y', 'ь': '', 'э': 'e', 'ю': 'yu', 'я': 'ya',
    }
    out = []
    for ch in text.lower():
        if ch in table:
            out.append(table[ch])
        elif ch.isascii() and ch.isalnum():
            out.append(ch)
        elif ch in " -_":
            out.append("-")
    s = "".join(out)
    return re.sub(r"-+", "-", s).strip("-")[:80] or "expert"


# ── Public API ────────────────────────────────────────────
def load_expert(slug: str, *, hub_root: Path = EXPERTS_HUB_ROOT) -> Optional[ExpertCard]:
    """Загрузить одного эксперта по slug. Возвращает None если не найден."""
    # Поиск файла: experts/{slug}.md
    md_path = hub_root / "experts" / f"{slug}.md"
    if not md_path.exists():
        return None

    text = md_path.read_text(encoding="utf-8")
    fm, body = _parse_frontmatter(text)
    sections = _parse_sections(body)

    # Имя — из frontmatter, fallback — slug → "Mark Rozin"
    name = fm.get("name") or fm.get("title") or slug.replace("-", " ").title()
    name = name.strip()

    # Из frontmatter
    tags_raw = fm.get("tags", [])
    if isinstance(tags_raw, str):
        tags = [t.strip() for t in tags_raw.split(",") if t.strip()]
    else:
        tags = list(tags_raw)

    # Секции
    main_table = _parse_table(sections.get("📋 Основное", ""))
    job_title = main_table.get("Должность / главная роль", "")
    if not job_title:
        # fallback — первая строка под # Имя
        m = re.match(r"^\*\*([^*]+)\*\*", body)
        if m:
            job_title = m.group(1).strip()

    description = sections.get("> ", "").strip().lstrip(">").strip() or main_table.get("ФИО", "")
    if not description and "Имя Фамилия" in body:
        # Возьмём первую цитату-эпиграф
        m = re.search(r"^>\s+(.+?)$", body, re.MULTILINE)
        if m:
            description = m.group(1).strip().lstrip("«").rstrip("»").strip()

    education = sections.get("🎓 Образование и регалии", "")
    alumni_of = re.findall(r"\*\*([^*]+)\*\*", education)

    quotes = _parse_quotes(sections.get("💬 Цитаты", ""))
    media = _parse_media(sections.get("🎙️ Медиа", ""))
    schema = _parse_schema_jsonld(body)

    # Связь с WL
    wl_section = sections.get("🔗 Связь с Лабораторией желаний", "")
    slugs = re.findall(r"`([a-z0-9-]+)`", wl_section)

    # Score — из frontmatter или score секции
    score = 0
    score_m = re.search(r"\*\*Score:\*\*\s*(\d+)/100", body)
    if score_m:
        score = int(score_m.group(1))
    elif "score" in fm:
        try:
            score = int(str(fm["score"]))
        except ValueError:
            pass

    return ExpertCard(
        slug=slug,
        name=name,
        jobTitle=job_title,
        description=description,
        url=main_table.get("Сайт", ""),
        image=schema.get("image", ""),
        email=main_table.get("Email", ""),
        sameAs=schema.get("sameAs", []),
        knowsAbout=schema.get("knowsAbout", []),
        alumniOf=alumni_of,
        awards=schema.get("award", []),
        worksFor=schema.get("worksFor", {}).get("name", "") if isinstance(schema.get("worksFor"), dict) else "",
        quotes=quotes,
        media=media,
        tags=tags,
        score=score,
        schema_jsonld=schema,
        source_md=text,
        source_path=str(md_path),
        recommended_books=[{"slug": s} for s in slugs],
        featured_video=str(fm.get("featured_video", "")).strip(),
    )

def load_all_experts(*, hub_root: Path = EXPERTS_HUB_ROOT) -> list[ExpertCard]:
    """Загрузить всех экспертов из experts/*.md."""
    experts_dir = hub_root / "experts"
    if not experts_dir.exists():
        return []

    cards: list[ExpertCard] = []
    for md_path in sorted(experts_dir.glob("*.md")):
        slug = _slugify(md_path.stem)
        # Если в frontmatter есть slug — используем его
        text = md_path.read_text(encoding="utf-8")
        fm, _ = _parse_frontmatter(text)
        if "slug" in fm:
            slug = str(fm["slug"]).strip()

        card = load_expert(slug, hub_root=hub_root)
        if card is not None:
            cards.append(card)

    # Сортировка по score ↓, потом по имени
    cards.sort(key=lambda c: (-c.score, c.name))
    return cards


def load_index(*, hub_root: Path = EXPERTS_HUB_ROOT) -> dict:
    """Сгенерировать index.json для быстрого листинга."""
    experts = load_all_experts(hub_root=hub_root)
    return {
        "generated_at": _now_iso(),
        "total": len(experts),
        "experts": [
            {
                "slug": e.slug,
                "name": e.name,
                "jobTitle": e.jobTitle,
                "tags": e.tags,
                "score": e.score,
                "image": e.image,
            }
            for e in experts
        ],
    }


def _now_iso() -> str:
    from datetime import datetime
    return datetime.now().isoformat(timespec="seconds")


# ── CLI: smoke test ───────────────────────────────────────
if __name__ == "__main__":
    import json as _json
    cards = load_all_experts()
    print(f"Loaded {len(cards)} experts:")
    for c in cards:
        print(f"  {c.score:3d} | {c.slug:30s} | {c.name} — {c.jobTitle[:50]}")
    print()
    if cards:
        first = cards[0]
        print(f"First expert sample (dict without source_md):")
        sample = {k: v for k, v in first.to_dict().items() if k != "source_md"}
        print(_json.dumps(sample, ensure_ascii=False, indent=2)[:1500])
