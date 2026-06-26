"""
Куратор каталога желаний через YandexGPT-lite.
Генерирует черновик 15–20 желаний для одной сферы (или всех 8) → markdown для ревью.

Использование:
    python scripts/curate_wishes.py --sphere=health
    python scripts/curate_wishes.py --all
    python scripts/curate_wishes.py --sphere=finance --count=20 --temperature=0.7

Зависимости:
    pip install pyyaml requests python-dotenv
"""

import argparse
import io
import os
import sys
from pathlib import Path
from datetime import datetime

if sys.platform.startswith("win"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8")

try:
    import yaml
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).parent.parent / ".env")
except ImportError as e:
    print(f"[!] pip install pyyaml python-dotenv: {e}", file=sys.stderr)
    sys.exit(1)

sys.path.insert(0, str(Path(__file__).parent))
from yandexgpt import YandexGPT  # noqa: E402

ROOT = Path(__file__).parent.parent
PROMPT_PATH = ROOT / "prompts" / "curate-wish.md"
SPHERES_DIR = ROOT / "data" / "spheres"
WL_SLUGS_PATH = ROOT / "data" / "wl_slugs.yaml"
LIBRARY_DIR = ROOT / "data" / "library"
LIBRARY_DIR.mkdir(parents=True, exist_ok=True)


def load_wl_slugs() -> set[str]:
    """Загружает множество валидных slug-ов WL из wl_slugs.yaml."""
    if not WL_SLUGS_PATH.exists():
        return set()
    with open(WL_SLUGS_PATH, encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    return {b["slug"] for b in data.get("books", [])}


def load_system_prompt() -> str:
    return PROMPT_PATH.read_text(encoding="utf-8") if hasattr(PROMPT_PATH, "read_text") else open(PROMPT_PATH, encoding="utf-8").read()


def load_sphere(sphere_id: str) -> dict:
    path = SPHERES_DIR / f"{sphere_id}.yaml"
    if not path.exists():
        raise FileNotFoundError(f"Нет файла сферы: {path}")
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def build_user_prompt(sphere: dict, count: int, valid_slugs: set[str]) -> str:
    """
    Формирует user-промпт на основе описания сферы и подсфер.
    YandexGPT должен вернуть JSON-массив.
    """
    name = sphere["sphere"]["name"]
    desc = sphere["sphere"]["description"]
    subs = sphere.get("subsphere_hints", [])
    sub_lines = "\n".join(f"- {next(iter(s.keys()))}: {next(iter(s.values()))}" for s in subs)

    # Список книг для справки (только валидные slug-ы из wl_slugs.yaml)
    sphere_books = sphere.get("source_books", [])
    valid_sphere_slugs = [b["slug"] for b in sphere_books if b["slug"] in valid_slugs]
    book_lines = ", ".join(valid_sphere_slugs) if valid_sphere_slugs else "нет валидных slug-ов для этой сферы"

    return f"""Сгенерируй ровно {count} желаний в сфере «{name}».

Описание сферы: {desc}

Подсферы (покрой их равномерно — по 2–4 желания в каждой):
{sub_lines}

Доступные книги WL для привязки (slug-ы): {book_lines}

Требования:
1. Каждое желание = действие + результат
2. 5–10 слов, начинается с глагола в инфинитиве
3. Без «я хочу», без негативных формулировок
4. Реалистично для обычного человека
5. `source_book_id` указывай ТОЛЬКО если есть прямая связь с книгой WL, иначе null
6. Покрой подсферы равномерно

Верни ТОЛЬКО валидный JSON-массив, без markdown-обёртки, без пояснений до/после."""


def generate_for_sphere(
    gpt: YandexGPT,
    sphere_id: str,
    count: int = 18,
    temperature: float = 0.6,
    valid_slugs: set[str] | None = None,
) -> list[dict]:
    sphere = load_sphere(sphere_id)
    sys_prompt = load_system_prompt()
    user_prompt = build_user_prompt(sphere, count, valid_slugs or set())

    print(f"  → Сфера: {sphere['sphere']['name']}, запрошено {count} желаний", file=sys.stderr)
    result = gpt.completion_json(sys_prompt, user_prompt, temperature=temperature)
    if not isinstance(result, list):
        raise ValueError(f"YandexGPT вернул не массив, а {type(result)}")
    # Пост-валидация: заменяем невалидные slug-ы на null
    for w in result:
        sb = w.get("source_book_id")
        if sb and valid_slugs and sb not in valid_slugs:
            w["source_book_id"] = None
            w["source_chapter"] = None
    return result


def save_draft_markdown(sphere_id: str, sphere_name: str, wishes: list[dict]) -> Path:
    """
    Сохраняет черновик как markdown для удобного ревью глазами.
    """
    out = LIBRARY_DIR / f"_draft-{sphere_id}.md"
    lines = [
        f"# Черновик: {sphere_name}",
        "",
        f"**Сфера:** {sphere_id}",
        f"**Сгенерировано:** {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        f"**Количество:** {len(wishes)}",
        f"**Модель:** YandexGPT-lite (temperature 0.6)",
        "",
        "## Желания",
        "",
        "| # | Текст | Описание | Книга | Глава |",
        "|---|-------|----------|-------|-------|",
    ]
    for i, w in enumerate(wishes, 1):
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
        "## Итог",
        "",
        "Когда ревью готов — скажи «в финал», и я смержу в `wishes_final.json`.",
        "",
    ])
    out.write_text("\n".join(lines), encoding="utf-8")
    return out


def main():
    ap = argparse.ArgumentParser(description="Куратор каталога желаний")
    ap.add_argument("--sphere", help="ID сферы (health, relations, finance, ...)")
    ap.add_argument("--all", action="store_true", help="Все 8 сфер")
    ap.add_argument("--count", type=int, default=18, help="Количество желаний на сферу (15–20)")
    ap.add_argument("--temperature", type=float, default=0.6, help="Temperature YandexGPT")
    ap.add_argument("--model", default="yandexgpt-lite", help="Модель (yandexgpt-lite, yandexgpt)")
    args = ap.parse_args()

    if not args.sphere and not args.all:
        ap.error("Укажи --sphere=<id> или --all")

    gpt = YandexGPT(model=args.model, temperature=args.temperature)
    valid_slugs = load_wl_slugs()
    print(f"Валидных WL slug-ов: {len(valid_slugs)}", file=sys.stderr)

    if args.all:
        sphere_ids = [p.stem for p in SPHERES_DIR.glob("*.yaml")]
        sphere_ids.sort()
    else:
        sphere_ids = [args.sphere]

    results = {}
    for sid in sphere_ids:
        try:
            wishes = generate_for_sphere(gpt, sid, count=args.count, temperature=args.temperature, valid_slugs=valid_slugs)
            sphere = load_sphere(sid)
            out_path = save_draft_markdown(sid, sphere["sphere"]["name"], wishes)
            print(f"  ✓ {sphere['sphere']['name']}: {len(wishes)} желаний → {out_path}")
            results[sid] = wishes
        except Exception as e:
            import traceback
            print(f"  ✗ {sid}: {type(e).__name__}: {e}", file=sys.stderr)
            traceback.print_exc(file=sys.stderr)
            results[sid] = None

    # Итог
    success = sum(1 for v in results.values() if v is not None)
    print(f"\n[Готово] {success}/{len(sphere_ids)} сфер обработано.")
    print(f"Файлы: {LIBRARY_DIR}/_draft-*.md")


if __name__ == "__main__":
    main()
