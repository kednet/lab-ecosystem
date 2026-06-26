"""
Скрипт верификации slug-ов WL в черновиках wish_market.
Сравнивает source_book_id из markdown-черновиков с реальными folder_name в WL.
"""
import re
import sys
import io
from pathlib import Path

if sys.platform.startswith("win"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8")

ROOT = Path(__file__).parent.parent
WL_LIBRARY = Path("C:/Users/kfigh/wish_librarian/output/library")
DRAFTS_DIR = ROOT / "data/library"

# Соберём реальные folder_name из WL
real_folders = set(f.name for f in WL_LIBRARY.iterdir() if f.is_dir()) if WL_LIBRARY.exists() else set()
# Транслитерированные латиницей префиксы
real_slugs_latin = set()
for f in real_folders:
    # Берём часть до первого подчёркивания
    head = f.split("_")[0].lower()
    real_slugs_latin.add(head)

# Соберём все slug-ы из черновиков (столбец "Книга" в таблице)
slug_pattern = re.compile(r'\|\s*([a-z][a-z0-9-]+)\s*\|\s*—\s*\|')
all_slugs = {}  # slug -> [сферы где встречается]
for f in sorted(DRAFTS_DIR.glob("_draft-*.md")):
    text = f.read_text(encoding="utf-8")
    for m in slug_pattern.finditer(text):
        s = m.group(1)
        # Пропускаем слова из заголовка таблицы
        if s in ("text", "description", "книга", "глава", "no", "yes"):
            continue
        all_slugs.setdefault(s, []).append(f.stem)

# Проверяем каждый slug
# Создаём словарь для поиска: slug (и его части) -> folder
slugs_to_folders = {}
for s in sorted(all_slugs.keys()):
    found = None
    # Прямое совпадение
    for folder in real_folders:
        if s in folder.lower():
            found = folder
            break
    if not found:
        # Совпадение по началу (транслит-префикс)
        head = s.split("-")[0]
        for folder in real_folders:
            if folder.lower().startswith(head):
                found = folder
                break
    slugs_to_folders[s] = found

# Записываем отчёт
out = ROOT / "tmp/_slug-verification.md"
out.parent.mkdir(exist_ok=True)

lines = [
    "# 🔍 Проверка slug-ов WL в черновиках wish_market",
    "",
    f"**Дата:** {Path(__file__).stat().st_mtime}",
    f"**Всего уникальных slug-ов в черновиках:** {len(all_slugs)}",
    f"**Всего книг в WL output/library/:** {len(real_folders)}",
    "",
    "## ✅ Валидные slug-ы (найдены в WL)",
    "",
]
valid = {s: f for s, f in slugs_to_folders.items() if f}
invalid = {s: f for s, f in slugs_to_folders.items() if not f}

if valid:
    for s in sorted(valid.keys()):
        folder = valid[s]
        spheres = sorted(set(all_slugs[s]))
        lines.append(f"- `{s}` → `{folder}` (использован в: {', '.join(spheres)})")
else:
    lines.append("_Нет валидных slug-ов_")

lines.extend([
    "",
    f"## ❌ Невалидные slug-ы (НЕ найдены в WL): {len(invalid)}",
    "",
    "**Проблема:** YandexGPT выдумал slug-ы, не соответствующие реальным folder_name в WL.",
    "**Решение:** заменить на `null` или найти правильный slug по смыслу.",
    "",
])
for s in sorted(invalid.keys()):
    spheres = sorted(set(all_slugs[s]))
    lines.append(f"- `{s}` (использован в: {', '.join(spheres)})")

lines.extend([
    "",
    "## 📚 Реальные книги в WL (output/library/)",
    "",
])
for folder in sorted(real_folders):
    lines.append(f"- `{folder}`")

lines.extend([
    "",
    "## 🎯 Рекомендация",
    "",
    "1. Все невалидные slug-ы заменить на `null` в финальном JSON",
    "2. Перед импортом в PostgreSQL — пройтись по `wishes_final.json` и проверить каждый `source_book_id` против списка выше",
    "3. В будущем: добавить функцию в скрипт генерации, которая получает список реальных slug-ов и передаёт в промпт YandexGPT",
    "",
])
out.write_text("\n".join(lines), encoding="utf-8")
print(f"Отчёт сохранён: {out}")
print(f"Валидных: {len(valid)}, невалидных: {len(invalid)}")
