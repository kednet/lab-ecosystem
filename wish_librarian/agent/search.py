"""
`--query` — простой поиск по уже обработанным книгам.

Сканирует summary.md во всех папках, ищет подстроку (регистронезависимо).
Сортирует по релевантности (TF).
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import List, Tuple


STOPWORDS = {"и", "в", "на", "по", "о", "об", "с", "со", "к", "у", "из", "от",
             "the", "a", "an", "of", "to", "for", "in", "on", "and", "or"}


def _tokenize(text: str) -> List[str]:
    text = text.lower()
    text = re.sub(r"[^a-zа-яё0-9\s]+", " ", text)
    return [t for t in text.split() if t and t not in STOPWORDS and len(t) > 2]


def search_library(
    query: str,
    library_dir: Path,
    *,
    max_results: int = 20,
) -> List[Tuple[Path, int, str]]:
    """
    Вернуть список (folder, score, snippet) отсортированный по score.
    """
    if not query.strip() or not library_dir.exists():
        return []

    tokens = _tokenize(query)
    if not tokens:
        tokens = [query.lower()]

    results: List[Tuple[Path, int, str]] = []
    for folder in sorted(library_dir.iterdir()):
        if not folder.is_dir():
            continue
        summary = folder / "summary.md"
        if not summary.exists():
            continue
        try:
            text = summary.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        text_lower = text.lower()
        score = 0
        for t in tokens:
            score += text_lower.count(t)
        # Также учитываем метаданные
        meta = folder / "metadata.json"
        if meta.exists():
            try:
                import json
                md = json.loads(meta.read_text(encoding="utf-8"))
                title = (md.get("title") or "").lower()
                author = (md.get("author") or "").lower()
                for t in tokens:
                    if t in title:
                        score += 10
                    if t in author:
                        score += 5
            except (OSError, ValueError):
                pass
        if score > 0:
            # сниппет: первое вхождение одного из токенов
            snippet = ""
            for t in tokens:
                idx = text_lower.find(t)
                if idx >= 0:
                    start = max(0, idx - 80)
                    end = min(len(text), idx + 200)
                    snippet = "..." + text[start:end].replace("\n", " ") + "..."
                    break
            results.append((folder, score, snippet))
    results.sort(key=lambda x: x[1], reverse=True)
    return results[:max_results]
