#!/usr/bin/env python3
"""
mine_audience_pains.py — mining болей ЦА из комментариев VK.

Использование:
  python mine_audience_pains.py --group pulabru
  python mine_audience_pains.py --group pulabru --max-comments 200
  python mine_audience_pains.py --group pulabru --offline
  python mine_audience_pains.py --input data/competitors/pulabru/comments.json

Вход:  data/competitors/<group>/comments.json (или --input)
       Формат: { "comments": [ {"text": "...", "post_id": ..., "likes": ...}, ... ] }

Процесс:
  1. Фильтрация мусора (короткие, спам, сервис)
  2. LLM-классификация каждого комментария по 5 категориям:
       боль | вопрос | возражение | инсайт | история
  3. Группировка по темам (LLM extract_themes)
  4. Извлечение «магнитов» — повторяющихся фраз (частотный анализ)
  5. Сохранение в JSON + Markdown

Выход:
  data/audience/pains-<group>.json
  data/audience/pains-<group>.md
  (опц.) обновление audience-mining/pain-language-bank.md — агрегатор

Статус: v0.2 — реальный LLM-анализ. Без LLM (--offline) — частотный анализ без классификации.
"""

import argparse
import json
import os
import re
import sys
from collections import Counter
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
COMPETITORS_DIR = DATA_DIR / "competitors"
AUDIENCE_DIR = DATA_DIR / "audience"
PAIN_BANK_MD = SKILL_DIR / "audience-mining" / "pain-language-bank.md"

# 5 категорий классификации комментариев
CATEGORIES = ["боль", "вопрос", "возражение", "инсайт", "история"]

# Стоп-слова и паттерны сервисных комментов
SERVICE_PATTERNS = [
    r"^\s*$",
    r"^[👍👎❤💔😂😭🔥🤔👏🙏✌🤝💯]+$",  # только эмодзи
    r"^(да|нет|ага|неа|ок|okay|ok)\.?$",
    r"^(подписка|подписался|подписалась|репост|репостнул[аи]?)\b",
    r"^(круто|класс|супер|топ|огонь|бомба|огонёк|норм)\s*[.!👍]*$",
    r"^@\w+",
    r"https?://\S+",
    r"^[a-zа-я]\s*$",  # 1 буква
]

MIN_COMMENT_LEN = 15  # минимальная длина после очистки


def is_service_comment(text: str) -> bool:
    """Сервисный/мусорный коммент? True = выбрасываем."""
    if not text:
        return True
    t = text.strip()
    if len(t) < MIN_COMMENT_LEN:
        return True
    for pat in SERVICE_PATTERNS:
        if re.search(pat, t, re.IGNORECASE):
            return True
    return False


def clean_text(text: str) -> str:
    """Очистить текст коммента от шума, оставив 1 предложение."""
    t = re.sub(r"http\S+", "", text)
    t = re.sub(r"@\w+", "", t)
    t = re.sub(r"\s+", " ", t)
    t = t.strip()
    # Берём первое предложение (для коротких цитат в отчёте)
    if len(t) > 200:
        t = t[:197] + "..."
    return t


def load_comments(input_path: Path) -> List[Dict[str, Any]]:
    """Загрузить комменты из JSON-дампа fetch_comments.py / fetch_vk_posts.py."""
    if not input_path.exists():
        return []
    try:
        data = json.loads(input_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        print(f"[error] Невалидный JSON в {input_path}: {e}")
        return []
    # Поддержка двух форматов: {comments: [...]} и просто [...]
    if isinstance(data, list):
        return data
    return data.get("comments", []) or []


def normalize_comment(raw: Dict[str, Any]) -> Dict[str, Any]:
    """Привести разные форматы к единому виду."""
    text = (
        raw.get("text")
        or raw.get("comment_text")
        or raw.get("body")
        or raw.get("message")
        or ""
    )
    return {
        "id": raw.get("id") or raw.get("comment_id"),
        "text": clean_text(str(text)),
        "post_id": raw.get("post_id"),
        "likes": raw.get("likes", 0) or 0,
        "from_id": raw.get("from_id"),
        "date": raw.get("date"),
    }


def filter_comments(comments: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Отфильтровать мусор и дедуп по тексту."""
    seen: set = set()
    out: List[Dict[str, Any]] = []
    for c in comments:
        text = c.get("text", "")
        if is_service_comment(text):
            continue
        key = text.lower()[:80]
        if key in seen:
            continue
        seen.add(key)
        out.append(c)
    return out


def classify_comments(
    comments: List[Dict[str, Any]],
    client: Any,
    batch_size: int = 1,
) -> Dict[str, List[Dict[str, Any]]]:
    """Классифицировать каждый коммент через LLM. Возвращает dict[cat] = [comments]."""
    buckets: Dict[str, List[Dict[str, Any]]] = {c: [] for c in CATEGORIES}

    total = len(comments)
    print(f"[classify] Классифицирую {total} комментов через LLM ({client.provider}/{client.model})...")

    for i, c in enumerate(comments, 1):
        if i % 20 == 0 or i == total:
            print(f"  [{i}/{total}] {c['text'][:60]}...")
        try:
            cat = client.classify(c["text"], CATEGORIES)
        except Exception as e:
            print(f"  [warn] LLM ошибка на #{i}: {e}")
            cat = "боль"  # fallback
        cat_norm = cat.strip().lower()
        if cat_norm not in buckets:
            cat_norm = "боль"
        c["category"] = cat_norm
        buckets[cat_norm].append(c)

    return buckets


def extract_themes_per_category(
    buckets: Dict[str, List[Dict[str, Any]]],
    client: Any,
    top_n: int = 10,
) -> Dict[str, List[str]]:
    """Извлечь темы в каждой категории."""
    themes_per_cat: Dict[str, List[str]] = {}
    for cat, items in buckets.items():
        if not items:
            themes_per_cat[cat] = []
            continue
        texts = [c["text"] for c in items[:50]]
        try:
            themes = client.extract_themes(texts, top_n=top_n)
        except Exception as e:
            print(f"  [warn] LLM extract_themes для '{cat}': {e}")
            themes = []
        themes_per_cat[cat] = themes
        print(f"  [themes/{cat}] {len(themes)} тем")
    return themes_per_cat


def find_magnets(comments: List[Dict[str, Any]], min_repeats: int = 3, top_n: int = 15) -> List[Dict[str, Any]]:
    """Найти повторяющиесяся первые 3-4 слова (магниты)."""
    starts: Counter = Counter()
    for c in comments:
        words = re.findall(r"\b\w+\b", c["text"].lower())
        if len(words) < 3:
            continue
        # Берём 3-словные начала
        starts[" ".join(words[:3])] += 1
        # И 4-словные (если не слишком обрезано)
        if len(words) >= 4:
            starts[" ".join(words[:4])] += 1

    magnets = []
    for phrase, count in starts.most_common(top_n * 2):
        if count >= min_repeats:
            magnets.append({"phrase": phrase, "count": count})
        if len(magnets) >= top_n:
            break
    return magnets


def build_summary(
    group: str,
    raw_count: int,
    filtered: List[Dict[str, Any]],
    buckets: Dict[str, List[Dict[str, Any]]],
    themes: Dict[str, List[str]],
    magnets: List[Dict[str, Any]],
    provider: str,
    model: str,
) -> Dict[str, Any]:
    """Собрать итоговый dict для JSON-выхода."""
    return {
        "version": "1.0",
        "group": group,
        "fetched": datetime.now().isoformat(),
        "llm_provider": provider,
        "llm_model": model,
        "raw_comment_count": raw_count,
        "filtered_comment_count": len(filtered),
        "by_category": {
            cat: {
                "count": len(items),
                "examples": [
                    {"text": c["text"][:200], "likes": c.get("likes", 0)}
                    for c in sorted(items, key=lambda x: -x.get("likes", 0))[:3]
                ],
                "themes": themes.get(cat, []),
            }
            for cat, items in buckets.items()
        },
        "magnets": magnets,
    }


def save_json(group: str, summary: Dict[str, Any]) -> Path:
    """Сохранить JSON."""
    AUDIENCE_DIR.mkdir(parents=True, exist_ok=True)
    path = AUDIENCE_DIR / f"pains-{group}.json"
    path.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"[save] → {path}")
    return path


def render_markdown(group: str, summary: Dict[str, Any]) -> str:
    """Рендер markdown-отчёта."""
    lines = [
        f"# Боли ЦА: {group}",
        "",
        f"**Дата анализа:** {summary['fetched'][:10]}",
        f"**LLM:** {summary.get('llm_provider', '—')} / {summary.get('llm_model', '—')}",
        f"**Сырых комментов:** {summary['raw_comment_count']}",
        f"**После фильтрации:** {summary['filtered_comment_count']}",
        "",
        "---",
        "",
    ]

    by_cat = summary.get("by_category", {})
    cat_titles = {
        "боль": "🔴 Топ болей",
        "вопрос": "❓ Топ вопросов",
        "возражение": "🚧 Топ возражений",
        "инсайт": "💡 Инсайты ЦА",
        "история": "📖 Истории",
    }
    for cat, title in cat_titles.items():
        data = by_cat.get(cat, {})
        count = data.get("count", 0)
        if count == 0:
            continue
        lines.append(f"## {title} ({count})")
        lines.append("")

        themes = data.get("themes", [])
        if themes:
            lines.append("**Темы:**")
            for t in themes:
                lines.append(f"- {t}")
            lines.append("")

        examples = data.get("examples", [])
        if examples:
            lines.append("**Цитаты (топ по лайкам):**")
            for ex in examples:
                likes = ex.get("likes", 0)
                lines.append(f"> {ex['text']}")
                lines.append(f"> *— {likes} лайков*")
                lines.append("")
        lines.append("---")
        lines.append("")

    magnets = summary.get("magnets", [])
    if magnets:
        lines.append("## 🧲 «Магниты» — повторяющиеся фразы")
        lines.append("")
        lines.append("Когда 3+ комментов начинаются одинаково — это магнит. Использовать в крючках.")
        lines.append("")
        for m in magnets:
            lines.append(f"- **{m['phrase']}** — {m['count']} раз")
        lines.append("")

    return "\n".join(lines)


def save_markdown(group: str, summary: Dict[str, Any]) -> Path:
    """Сохранить markdown-отчёт."""
    AUDIENCE_DIR.mkdir(parents=True, exist_ok=True)
    path = AUDIENCE_DIR / f"pains-{group}.md"
    path.write_text(render_markdown(group, summary), encoding="utf-8")
    print(f"[save] → {path}")
    return path


def update_pain_bank_md(group: str, summary: Dict[str, Any]) -> None:
    """Дописать секцию в audience-mining/pain-language-bank.md (агрегатор)."""
    if not PAIN_BANK_MD.exists():
        print(f"[warn] {PAIN_BANK_MD} не найден, агрегация пропущена")
        return

    text = PAIN_BANK_MD.read_text(encoding="utf-8")
    section_lines = [
        f"### Группа: {group} ({summary['fetched'][:10]})",
        "",
        f"Прокомментировано: {summary['filtered_comment_count']} (сырых: {summary['raw_comment_count']})",
        f"LLM: {summary.get('llm_provider', '—')}/{summary.get('llm_model', '—')}",
        "",
    ]

    by_cat = summary.get("by_category", {})
    for cat in CATEGORIES:
        data = by_cat.get(cat, {})
        if data.get("count", 0) == 0:
            continue
        section_lines.append(f"**{cat.capitalize()} ({data['count']}):**")
        for t in data.get("themes", [])[:5]:
            section_lines.append(f"- {t}")
        for ex in data.get("examples", [])[:2]:
            section_lines.append(f"  - «{ex['text']}»")
        section_lines.append("")

    magnets = summary.get("magnets", [])
    if magnets:
        section_lines.append("**Магниты:**")
        for m in magnets[:5]:
            section_lines.append(f"- «{m['phrase']}» ×{m['count']}")
        section_lines.append("")

    section = "\n".join(section_lines)
    section_header = "\n## Авто-секции (генерируются из mine_audience_pains.py)\n"

    if section_header in text:
        # Заменяем секцию целиком
        before, _, _ = text.partition(section_header)
        text = before + section_header + "\n" + section
    else:
        # Дописываем в конец
        text = text.rstrip() + "\n" + section_header + "\n" + section

    PAIN_BANK_MD.write_text(text, encoding="utf-8")
    print(f"[save] → {PAIN_BANK_MD} (обновлён агрегатор)")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Mining болей ЦА из VK-комментариев (LLM-классификация)",
    )
    parser.add_argument("--group", type=str, default=None,
                        help="Имя группы (= папка в data/competitors/)")
    parser.add_argument("--input", type=str, default=None,
                        help="Прямой путь к comments.json (если --group не задан)")
    parser.add_argument("--max-comments", type=int, default=200,
                        help="Максимум комментов для анализа (default: 200, для экономии LLM-токенов)")
    parser.add_argument("--top-themes", type=int, default=10,
                        help="Сколько тем извлекать в каждой категории (default: 10)")
    parser.add_argument("--offline", action="store_true",
                        help="Без LLM — только фильтрация + магниты")
    parser.add_argument("--no-update-bank", action="store_true",
                        help="Не обновлять pain-language-bank.md (агрегатор)")

    args = parser.parse_args()

    # 1. Определить входной файл
    if args.input:
        input_path = Path(args.input)
    elif args.group:
        input_path = COMPETITORS_DIR / args.group / "comments.json"
    else:
        print("[error] Нужен --group или --input")
        return 1

    group_name = args.group or input_path.stem.replace("comments-", "").replace("comments", "")

    # 2. Загрузить и нормализовать
    raw = load_comments(input_path)
    if not raw:
        print(f"[error] {input_path} не найден или пуст")
        print(f"        Сначала: python fetch_vk_posts.py --group {group_name}")
        print(f"                  python fetch_comments.py --group {group_name}")
        return 1
    raw_count = len(raw)
    normalized = [normalize_comment(r) for r in raw]
    filtered = filter_comments(normalized)
    if args.max_comments and len(filtered) > args.max_comments:
        # Сортируем по лайкам — берём самые «горячие»
        filtered = sorted(filtered, key=lambda c: -c.get("likes", 0))[: args.max_comments]
    print(f"[mine] {group_name}: {raw_count} сырых → {len(filtered)} после фильтрации (лимит: {args.max_comments})")

    if not filtered:
        print("[error] После фильтрации не осталось комментов")
        return 1

    # 3. LLM или offline
    provider = "offline"
    model = "—"
    buckets = {c: [] for c in CATEGORIES}
    themes_per_cat: Dict[str, List[str]] = {c: [] for c in CATEGORIES}

    if not args.offline:
        try:
            from llm_client import LLMClient
            client = LLMClient()
            if not client.is_available():
                print(f"[warn] LLM недоступен (provider={client.provider}), fallback на --offline")
            else:
                provider = client.provider
                model = client.model
                buckets = classify_comments(filtered, client)
                themes_per_cat = extract_themes_per_category(buckets, client, top_n=args.top_themes)
        except Exception as e:
            print(f"[warn] LLM-ошибка: {e}, fallback на offline")
    else:
        # В offline — кладём все в "боль" (частотный анализ потом вытащит)
        for c in filtered:
            c["category"] = "боль"
        buckets["боль"] = filtered

    # 4. Магниты (всегда, даже offline)
    magnets = find_magnets(filtered, min_repeats=3, top_n=15)

    # 5. Сохранить
    summary = build_summary(
        group=group_name,
        raw_count=raw_count,
        filtered=filtered,
        buckets=buckets,
        themes=themes_per_cat,
        magnets=magnets,
        provider=provider,
        model=model,
    )
    save_json(group_name, summary)
    save_markdown(group_name, summary)
    if not args.no_update_bank:
        update_pain_bank_md(group_name, summary)

    # 6. Краткая сводка в stdout
    print()
    print("=" * 60)
    print(f"Готово. {group_name}:")
    for cat in CATEGORIES:
        c = summary["by_category"].get(cat, {}).get("count", 0)
        if c:
            print(f"  {cat}: {c}")
    print(f"  магнитов: {len(magnets)}")
    print("=" * 60)
    return 0


if __name__ == "__main__":
    sys.exit(main())
