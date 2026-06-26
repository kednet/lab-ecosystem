"""
PDF → черновой YAML парсер для Audio Skill.

Читает PDF (например, «Скрипты для аудио.pdf»), извлекает один или все скрипты,
сохраняет в data/library/_draft-<slug>.yaml для последующей LLM-адаптации.

Использование:
    python scripts/pdf_parse.py "C:/Users/kfigh/Downloads/Скрипты для аудио.pdf"
    python scripts/pdf_parse.py "..." --script-id=1 --out=data/library/_draft-zolotye-pravila.yaml
    python scripts/pdf_parse.py "..." --all  # все 10 скриптов

Что делает:
1. pdfplumber извлекает текст по страницам.
2. Regex ищет заголовки «### Скрипт №N. „Название"».
3. Из шапки (между заголовком и текстом) парсит: Зона, Жанр, Тайминг.
4. Скрипт целиком (с мета-метками [МУЗЫКА, ПАУЗА, ШЁПОТ, ТИШИНА]) сохраняется
   в поле `script` чернового YAML.
5. Черновой YAML — это вход для scripts/llm_adapt.py.
"""

import argparse
import io
import re
import sys
from pathlib import Path

# Принудительно UTF-8 для Windows-консоли (cp1252 не понимает кириллицу)
if sys.platform.startswith("win"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8")

try:
    import pdfplumber
except ImportError:
    print("[!] pip install pdfplumber", file=sys.stderr)
    sys.exit(1)

try:
    import yaml
except ImportError:
    print("[!] pip install pyyaml", file=sys.stderr)
    sys.exit(1)


# Regex для заголовков «### Скрипт №1. „Золотые правила исполнения желаний" (3 минуты)»
# Допускаем «ёлочки» или "прямые" кавычки вокруг названия, и внутренние "..." в кавычках ёлочках
# (для №6 «Техника "100 желаний"»). Берём название greedy до последней закрывающей «ёлочки».
SCRIPT_HEADER_RE = re.compile(
    r"^###\s*Скрипт\s*№\s*(\d+)\.\s*[«](.+?)[»]"
    r"(?:\s*\(([^)]+)\))?",
    re.MULTILINE,
)

# Regex для шапки: «Зона: ... | Жанр: ...» (опционально, в твоём PDF 2026-06-11 их нет,
# но если в будущих PDF появятся — парсер их подхватит)
META_LINE_RE = re.compile(
    r"^Зона:\s*(.+?)\s*\|\s*Жанр:\s*(.+?)\s*$",
    re.MULTILINE,
)

# Regex для тайминга в скобках: «(3 минуты)» → 180
DURATION_RE = re.compile(r"(\d+)\s*минут", re.IGNORECASE)


def slugify_ru(text: str) -> str:
    """Простой slugify для русского текста (латиницей не пишем, кириллица ок)."""
    text = text.lower()
    # Транслитерация
    translit = {
        "а": "a", "б": "b", "в": "v", "г": "g", "д": "d", "е": "e", "ё": "yo",
        "ж": "zh", "з": "z", "и": "i", "й": "y", "к": "k", "л": "l", "м": "m",
        "н": "n", "о": "o", "п": "p", "р": "r", "с": "s", "т": "t", "у": "u",
        "ф": "f", "х": "h", "ц": "ts", "ч": "ch", "ш": "sh", "щ": "sch",
        "ъ": "", "ы": "y", "ь": "", "э": "e", "ю": "yu", "я": "ya",
    }
    result = []
    for ch in text:
        if ch in translit:
            result.append(translit[ch])
        elif ch.isalnum():
            result.append(ch)
        elif ch in (" ", "-", "_"):
            result.append("-")
    slug = "".join(result).strip("-")
    return re.sub(r"-+", "-", slug)


def extract_pdf_text(pdf_path: str) -> str:
    """Достаём весь текст из PDF через pdfplumber."""
    full_text = []
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            text = page.extract_text() or ""
            full_text.append(text)
    return "\n".join(full_text)


def _truncate_trailing_garbage(body: str) -> tuple[str, int]:
    """Обрезает «мусорный» хвост скрипта (ПЛАН ДЕЙСТВИЙ, Если хотите и т.п.).

    Возвращает (чистый_body, кол-во_обрезанных_chars).
    """
    # Маркеры конца скрипта — после них обычно идёт инструкция, а не сам скрипт
    end_markers = [
        r"\n##\s*🚀",           # «## 🚀 ПЛАН ДЕЙСТВИЙ»
        r"\n##\s*ПЛАН\s*ДЕЙСТВИЙ",
        r"\n###\s*Этап\s+\d+",   # «### Этап 1. ...»
        r"\nЕсли хотите, я могу",
        r"\nЧто вам сейчас нужнее",
        r"\n---\s*\n##",        # разделитель + новая секция
        r"\n\*\*[А-ЯЁ]",        # новая жирная секция
    ]
    cut_pos = len(body)
    for marker in end_markers:
        m = re.search(marker, body)
        if m and m.start() < cut_pos:
            cut_pos = m.start()
    if cut_pos < len(body):
        return body[:cut_pos].rstrip(), len(body) - cut_pos
    return body, 0


def parse_scripts(full_text: str) -> list[dict]:
    """Находим все «### Скрипт №N» и парсим шапку + тело."""
    matches = list(SCRIPT_HEADER_RE.finditer(full_text))
    if not matches:
        print("[!] Не нашли ни одного «### Скрипт №N.». Проверь формат PDF.", file=sys.stderr)
        return []

    scripts = []
    for i, m in enumerate(matches):
        script_id = int(m.group(1))
        title = m.group(2).strip()
        duration_str = m.group(3)  # «3 минуты» или None
        # Тело скрипта — от конца совпадения до начала следующего «### Скрипт» или конца текста
        body_start = m.end()
        body_end = matches[i + 1].start() if i + 1 < len(matches) else len(full_text)
        body = full_text[body_start:body_end].strip()

        # Обрезаем «мусорный» хвост (ПЛАН ДЕЙСТВИЙ и т.п.), если есть
        body, garbage_chars = _truncate_trailing_garbage(body)
        if garbage_chars > 0:
            print(f"  [i] Скрипт №{script_id} «{title}»: обрезано {garbage_chars} chars "
                  f"мусорного хвоста (ПЛАН ДЕЙСТВИЙ и т.п.)")

        # Парсим «Зона: ... | Жанр: ...»
        meta_match = META_LINE_RE.search(body)
        zone = None
        genre = None
        if meta_match:
            zone = meta_match.group(1).strip()
            genre = meta_match.group(2).strip()
            # Убираем строку мета из тела скрипта
            body = (body[:meta_match.start()] + body[meta_match.end():]).strip()

        # Парсим тайминг из заголовка
        duration_sec = None
        if duration_str:
            d = DURATION_RE.search(duration_str)
            if d:
                duration_sec = int(d.group(1)) * 60

        scripts.append({
            "script_id": script_id,
            "title": title,
            "slug": slugify_ru(title),
            "duration_target": duration_sec,
            "duration_str": duration_str,
            "zone": zone,
            "genre": genre,
            "script": body,
        })

    return scripts


def to_draft_yaml(script: dict, pdf_path: str) -> str:
    """Превращаем распарсенный скрипт в черновой YAML для LLM-адаптера."""
    # Экранируем YAML-спецсимволы в script (просто оборачиваем в literal block)
    draft = {
        "_draft": True,
        "_source": {
            "pdf": str(pdf_path),
            "script_id": script["script_id"],
        },
        "slug": script["slug"],
        "title": script["title"],
        "duration_target": script["duration_target"],
        "duration_str": script["duration_str"],
        "zone": script["zone"],
        "genre": script["genre"],
        # Поля ниже LLM-адаптер заполнит
        "voice": None,
        "background": None,
        "music_intro": None,
        "music_outro": None,
        "tone": None,
        "pov": "second_person",
        "language": "ru-RU",
        "remove_concrete_examples": False,
        "preserve_structure": True,
        "script": script["script"],
        "pauses": {
            "default": "1s",
            "between_paragraphs": "1s",
            "between_rules": "1.5s",
            "before_outro": "2s",
        },
        "ssml": {
            "prosody": {"rate": 0.9, "pitch": 0, "volume": "medium"},
            "whisper": {"enabled_in": [], "strength": 30},
        },
        "meta": {
            "category": None,
            "tags": [],
            "target_audience": None,
            "recommended_at": ["anytime"],
            "zone": script["zone"],
            "source_pdf": Path(pdf_path).name,
            "source_script_id": script["script_id"],
            "has_concrete_examples": True,
        },
    }
    # yaml.dump с allow_unicode=True (русский текст без escape)
    return yaml.dump(draft, allow_unicode=True, sort_keys=False, default_flow_style=False)


def main() -> int:
    ap = argparse.ArgumentParser(description="Парсер PDF скриптов в черновой YAML")
    ap.add_argument("pdf", help="Путь к PDF (например, 'Скрипты для аудио.pdf')")
    ap.add_argument("--script-id", type=int, help="Парсить только один скрипт (1..10)")
    ap.add_argument("--all", action="store_true", help="Парсить все скрипты")
    ap.add_argument("--out-dir", default="data/library", help="Куда сохранять черновики")
    ap.add_argument("--list", action="store_true", help="Только показать список скриптов")
    args = ap.parse_args()

    pdf_path = args.pdf
    if not Path(pdf_path).exists():
        print(f"[!] PDF не найден: {pdf_path}", file=sys.stderr)
        return 1

    print(f"[*] Читаю {pdf_path}...")
    full_text = extract_pdf_text(pdf_path)
    print(f"[*] Извлечено {len(full_text)} символов")

    scripts = parse_scripts(full_text)
    print(f"[*] Найдено скриптов: {len(scripts)}")

    if args.list:
        for s in scripts:
            print(f"  #{s['script_id']:2d}  {s['title']}  ({s['duration_str']})  зона={s['zone']}  жанр={s['genre']}")
        return 0

    if args.script_id is not None:
        scripts = [s for s in scripts if s["script_id"] == args.script_id]
        if not scripts:
            print(f"[!] Скрипт №{args.script_id} не найден", file=sys.stderr)
            return 1
    elif not args.all:
        # По умолчанию — все
        pass

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    for s in scripts:
        out_path = out_dir / f"_draft-{s['slug']}.yaml"
        out_path.write_text(to_draft_yaml(s, pdf_path), encoding="utf-8")
        print(f"[+] {out_path}  ({s['duration_str']})")

    print(f"\n[*] Готово. Следующий шаг:")
    for s in scripts:
        print(f"    python scripts/llm_adapt.py data/library/_draft-{s['slug']}.yaml "
              f"--provider=claude --remove-concrete-examples --out=data/library/{s['slug']}.yaml")

    return 0


if __name__ == "__main__":
    sys.exit(main())
