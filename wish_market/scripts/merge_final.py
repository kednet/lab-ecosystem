"""
Сборка финального банка желаний из черновиков.
Парсит markdown-таблицы из _draft-*.md, валидирует slug-ы, пишет wishes_final.json.
"""
import re
import sys
import io
import json
import uuid
from pathlib import Path
from datetime import datetime

if sys.platform.startswith("win"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8")

import yaml

ROOT = Path(__file__).parent.parent
DRAFTS_DIR = ROOT / "data/library"
WL_SLUGS_PATH = ROOT / "data/wl_slugs.yaml"
FINAL_PATH = ROOT / "data/library/wishes_final.json"


def load_valid_slugs() -> set[str]:
    with open(WL_SLUGS_PATH, encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return {b["slug"] for b in data.get("books", [])}


def parse_draft(path: Path, valid_slugs: set[str]) -> list[dict]:
    """
    Парсит markdown-черновик в список dict'ов.
    Формат таблицы: | # | text | description | slug | chapter |
    """
    text = path.read_text(encoding="utf-8")
    # Сфера из заголовка
    sphere_match = re.search(r"\*\*Сфера:\*\*\s*(\S+)", text)
    if not sphere_match:
        raise ValueError(f"Не найдена сфера в {path.name}")
    sphere_id = sphere_match.group(1)

    wishes = []
    # Парсим строки таблицы, пропуская заголовок
    for line in text.split("\n"):
        # Ищем строки вида: | 1 | Текст | Описание | slug | chapter |
        m = re.match(r"\|\s*(\d+)\s*\|\s*(.+?)\s*\|\s*(.*?)\s*\|\s*(.+?)\s*\|\s*(.*?)\s*\|", line)
        if not m:
            continue
        n, wish_text, desc, slug_raw, chapter_raw = m.groups()
        n = int(n)
        # Скорее всего это строка-заголовок таблицы
        if wish_text.strip() in ("Текст", "----"):
            continue
        if not (1 <= n <= 100):
            continue

        slug = None if (slug_raw or "").strip() in ("—", "-", "") else (slug_raw or "").strip()
        if slug and slug not in valid_slugs:
            slug = None
            chapter_raw = None

        chapter = None if (chapter_raw or "").strip() in ("—", "-", "") else (chapter_raw or "").strip()

        wishes.append({
            "id": str(uuid.uuid4()),
            "text": wish_text.strip(),
            "sphere_id": sphere_id,
            "description": desc.strip() if desc.strip() else None,
            "source_book_id": slug,
            "source_chapter": chapter,
            "is_ai_generated": True,
            "created_by": "curator",
            "is_active": True,
        })
    return wishes


def main():
    valid_slugs = load_valid_slugs()
    print(f"Валидных WL slug-ов: {len(valid_slugs)}")

    all_wishes = []
    stats_by_sphere = {}
    invalid_slugs_seen = set()

    for draft in sorted(DRAFTS_DIR.glob("_draft-*.md")):
        wishes = parse_draft(draft, valid_slugs)
        all_wishes.extend(wishes)
        sphere_id = wishes[0]["sphere_id"] if wishes else draft.stem.replace("_draft-", "")
        stats_by_sphere[sphere_id] = len(wishes)
        # Собираем невалидные slug-ы (для отчёта)
        for w in wishes:
            if w["source_book_id"] is None and draft.stem == "_draft-spiritual":
                pass  # spiritual с null — норма

    final = {
        "version": "0.1",
        "generated_at": datetime.now().isoformat(),
        "total_wishes": len(all_wishes),
        "spheres": [
            {"id": "health", "name": "Здоровье", "order": 1},
            {"id": "relations", "name": "Отношения", "order": 2},
            {"id": "finance", "name": "Финансы", "order": 3},
            {"id": "career", "name": "Карьера", "order": 4},
            {"id": "spiritual", "name": "Духовность и осознанность", "order": 5},
            {"id": "rest", "name": "Отдых", "order": 6},
            {"id": "learning", "name": "Обучение", "order": 7},
            {"id": "appearance", "name": "Внешность", "order": 8},
        ],
        "wishes": all_wishes,
    }

    FINAL_PATH.write_text(
        json.dumps(final, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print(f"\nИтого: {len(all_wishes)} желаний")
    print(f"По сферам:")
    for sid, count in stats_by_sphere.items():
        print(f"  {sid}: {count}")
    print(f"\nСохранено: {FINAL_PATH}")

    # Сколько имеют привязку к WL
    with_source = sum(1 for w in all_wishes if w["source_book_id"])
    print(f"С привязкой к WL: {with_source} ({with_source * 100 // len(all_wishes)}%)")


if __name__ == "__main__":
    main()
