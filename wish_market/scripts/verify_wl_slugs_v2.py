"""
Правильная проверка slug-ов: ищем в wl_slugs.yaml, а не в folder_name.
"""
import re
import sys
import io
from pathlib import Path

if sys.platform.startswith("win"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8")

import yaml

ROOT = Path(__file__).parent.parent
WL_SLUGS_PATH = ROOT / "data/wl_slugs.yaml"
DRAFTS_DIR = ROOT / "data/library"

# Загружаем ВАЛИДНЫЕ slug-ы из wl_slugs.yaml
with open(WL_SLUGS_PATH, encoding="utf-8") as f:
    data = yaml.safe_load(f)
valid_slugs = {b["slug"] for b in data.get("books", [])}

# Соберём slug-ы из черновиков
slug_pattern = re.compile(r'\|\s*([a-z][a-z0-9-]+)\s*\|\s*—\s*\|')
all_slugs = {}
for f in sorted(DRAFTS_DIR.glob("_draft-*.md")):
    text = f.read_text(encoding="utf-8")
    for m in slug_pattern.finditer(text):
        s = m.group(1)
        if s in ("text", "description", "книга", "глава", "no", "yes"):
            continue
        all_slugs.setdefault(s, []).append(f.stem)

# Проверяем
valid = {s: sorted(set(all_slugs[s])) for s in all_slugs if s in valid_slugs}
invalid = {s: sorted(set(all_slugs[s])) for s in all_slugs if s not in valid_slugs}

out = ROOT / "tmp/_slug-verification.md"
out.parent.mkdir(exist_ok=True)
lines = [
    "# Проверка slug-ов WL в черновиках wish_market (v2)",
    "",
    f"Всего валидных slug-ов в wl_slugs.yaml: {len(valid_slugs)}",
    f"Всего уникальных slug-ов в черновиках: {len(all_slugs)}",
    f"Валидных: {len(valid)}, невалидных: {len(invalid)}",
    "",
    "## Валидные slug-ы (найдены в wl_slugs.yaml)",
    "",
]
if valid:
    for s in sorted(valid.keys()):
        lines.append(f"- `{s}` (использован в: {', '.join(valid[s])})")
else:
    lines.append("_Нет валидных slug-ов_")

lines.extend([
    "",
    f"## Невалидные slug-ы: {len(invalid)}",
    "",
    "Эти slug-ы YandexGPT выдумал или взял из старой версии. Заменены на null при пост-валидации.",
    "",
])
for s in sorted(invalid.keys()):
    lines.append(f"- `{s}` (использован в: {', '.join(invalid[s])})")

out.write_text("\n".join(lines) + "\n", encoding="utf-8")
print(f"Валидных: {len(valid)}, невалидных: {len(invalid)}")
print(f"Отчёт: {out}")
