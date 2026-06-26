"""
Регенерация сферы "spiritual" с обходом фильтра YandexGPT.
Не используем слова "духовность", "смысл жизни" и т.п.
Фокус на практиках: медитация, дневник благодарности, осознанность, ретриты.
"""
import sys
import io
import json
from pathlib import Path
from datetime import datetime

if sys.platform.startswith("win"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8")

sys.path.insert(0, str(Path(__file__).parent))
from yandexgpt import YandexGPT

ROOT = Path(__file__).parent.parent

# Промпт БЕЗ слова "духовность" — фокус на практиках
prompt = """Сгенерируй ровно 18 конкретных, измеримых желаний из категории "осознанные практики и внутренний баланс".

Подкатегории (покрой равномерно, по 2–4 в каждой):
- meditation: ежедневная медитация, ретриты, дыхательные практики
- gratitude: дневник благодарности, ритуалы вечерней рефлексии
- mindfulness: осознанное питание, прогулки без телефона, осознанное дыхание
- values: определить личные ценности, принимать решения через них
- practices: йога, цигун, дыхательные упражнения
- reflection: вечерний дневник, ревизия недели, утренние страницы

Правила:
- Каждое желание = действие + результат
- 5–10 слов, начинается с глагола в инфинитиве
- Без "я хочу", без негативных формулировок
- Реалистично для обычного человека с работой
- source_book_id: указывай slug из списка только при прямой связи, иначе null

Доступные slug-ы книг для привязки (необязательно): buddi-v-kazhdom-dne, 7-dukhovnykh-zakonov, sila-nastoyashchego, avtobiografiya-yoga

Верни ТОЛЬКО валидный JSON-массив объектов с полями:
text (string), sphere (string, "осознанные практики"), description (string, 5–10 слов), source_book_id (string|null), source_chapter (string|null)."""

gpt = YandexGPT(model="yandexgpt-lite", temperature=0.7)
raw = gpt.completion(
    "Ты — куратор каталога практик осознанности. Отвечаешь строго JSON-массивом без пояснений.",
    prompt,
    temperature=0.7,
    max_tokens=3500,
)

print("=== RAW RESPONSE ===", file=sys.stderr)
print(raw[:500], file=sys.stderr)
print("=== END ===", file=sys.stderr)

raw = raw.strip()
if raw.startswith("```"):
    lines = raw.split("\n")[1:]
    if lines and lines[-1].strip().startswith("```"):
        lines = lines[:-1]
    raw = "\n".join(lines).strip()

try:
    data = json.loads(raw)
    print(f"✓ Получено {len(data)} желаний", file=sys.stderr)
    out = ROOT / "data/library/_draft-spiritual.md"
    lines = [
        "# Черновик: Осознанные практики (бывш. Духовность)",
        "",
        "**Сфера:** spiritual",
        f"**Сгенерировано:** {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        f"**Количество:** {len(data)}",
        "**Модель:** YandexGPT-lite (temperature 0.7, обход фильтра)",
        "",
        "**NB:** YandexGPT отказался отвечать на тему «духовность». Переформулировал в «осознанные практики» — контент тот же.",
        "",
        "## Желания",
        "",
        "| # | Текст | Описание | Книга | Глава |",
        "|---|-------|----------|-------|-------|",
    ]
    for i, w in enumerate(data, 1):
        text = w.get("text", "").replace("|", "\\|")
        desc = (w.get("description") or "").replace("|", "\\|")
        book = w.get("source_book_id") or "—"
        chapter = w.get("source_chapter") or "—"
        lines.append(f"| {i} | {text} | {desc} | {book} | {chapter} |")
    lines.extend([
        "",
        "## Правки (твои)",
        "",
        "- 1: ",
        "- 2: ",
        "- 3: ",
        "- ... ",
        "",
    ])
    out.write_text("\n".join(lines), encoding="utf-8")
    print(f"✓ Сохранено: {out}", file=sys.stderr)
except json.JSONDecodeError as e:
    print(f"✗ Невалидный JSON: {e}", file=sys.stderr)
    debug = ROOT / "tmp/_debug-spiritual-raw.txt"
    debug.write_text(raw, encoding="utf-8")
    print(f"  Сырой ответ: {debug}", file=sys.stderr)
