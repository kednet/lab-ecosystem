"""
Маппинг 19 книг WishLibrarian (output/library/) на латинские slug-ы.
Алгоритм: транслитерация кириллицы + lowercase + дефисы.
"""
import re
import sys
import io
from pathlib import Path

if sys.platform.startswith("win"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8")

WL_LIBRARY = Path("C:/Users/kfigh/wish_librarian/output/library")

# Маппинг кириллица → латиница (ГОСТ 7.79 система Б)
TRANSLIT = {
    "а": "a", "б": "b", "в": "v", "г": "g", "д": "d", "е": "e", "ё": "yo",
    "ж": "zh", "з": "z", "и": "i", "й": "y", "к": "k", "л": "l", "м": "m",
    "н": "n", "о": "o", "п": "p", "р": "r", "с": "s", "т": "t", "у": "u",
    "ф": "f", "х": "kh", "ц": "ts", "ч": "ch", "ш": "sh", "щ": "shch", "ъ": "",
    "ы": "y", "ь": "", "э": "e", "ю": "yu", "я": "ya",
    "і": "i", "ї": "yi", "є": "ye", "ґ": "g",
}

def translit(s: str) -> str:
    result = []
    for ch in s.lower():
        if ch in TRANSLIT:
            result.append(TRANSLIT[ch])
        elif ch.isalnum():
            result.append(ch)
        elif ch in " _-":
            result.append("-")
    out = "".join(result)
    # Схлопываем повторяющиеся дефисы
    out = re.sub(r"-+", "-", out)
    return out.strip("-")


def folder_to_slug(folder: str) -> str:
    """
    Транслитерируем полное имя папки → slug.
    Примеры:
      'transerfing-realnosti' → 'transerfing-realnosti'
      'Аndreeva_Тri_klyucha_k_ispolneniyu_zhelanii' → 'andreeva-tri-klyucha-k-ispolneniyu-zhelanii'
      'Даниэль_Канеман_Думай_медленно_решай_быстро__Даниэль_Канеман' → 'daniel-kaneman-dumay-medlenno-reshay-bystro-daniel-kaneman'
      'Вадим_Зеланд_Трансерфинг_реальности_2004' → 'vadim-zeland-transerfing-realnosti-2004'
    """
    # Сначала убираем подчёркивания, транслитерируем, потом снова дефисы
    parts = folder.split("_")
    # Двойные подчёркивания = "повтор имени автора в конце" — пропускаем дубли
    seen = set()
    unique_parts = []
    for p in parts:
        if p and p not in seen:
            seen.add(p)
            unique_parts.append(p)
    transliterated = [translit(p) for p in unique_parts if p]
    slug = "-".join(t for t in transliterated if t)
    slug = re.sub(r"-+", "-", slug).strip("-")
    return slug


# Соберём маппинг
mapping = {}
for folder in sorted(WL_LIBRARY.iterdir()):
    if folder.is_dir():
        slug = folder_to_slug(folder.name)
        mapping[folder.name] = slug

# Сохраняем в YAML вручную (без зависимостей)
out = Path(__file__).parent.parent / "data/wl_slugs.yaml"
out.parent.mkdir(parents=True, exist_ok=True)

lines = [
    "# Маппинг книг WishLibrarian (output/library/) → латинские slug-ы",
    "# Используется в data/spheres/*.yaml как source_book_id",
    "# Сгенерировано scripts/build_wl_slugs.py",
    "",
    "books:",
]
for folder, slug in sorted(mapping.items()):
    lines.append(f"  - folder: \"{folder}\"")
    lines.append(f"    slug: \"{slug}\"")

out.write_text("\n".join(lines) + "\n", encoding="utf-8")
print(f"Маппинг сохранён: {out}")
print(f"Книг обработано: {len(mapping)}")
print()
print("Примеры:")
for i, (f, s) in enumerate(list(mapping.items())[:5]):
    print(f"  {f}")
    print(f"    → {s}")
