"""
Regenerate ONLY workbook.md for an existing book using a new template.

Usage:
    python scripts/regen_workbook.py "output/library/Muzhitskaya_..." --template=workbook_v3

Используется для пилота «вовлечение в контент» — перегенерировать workbook.md
Мужицкой через новый шаблон workbook_v3 (с финальным блоком «Поделитесь
результатом» → /my-experiment/?from=workbook).

ВАЖНО: _generate_workbook берёт контекст из summary.md в той же папке
(librarian.py:527-530), поэтому сначала убедитесь, что summary.md уже в
нужной версии (для пилота — v3 с «Мини-эксперимент» + «А у тебя как?»).
"""
from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# Подменяем ENV ДО reload_settings
import os
template = "workbook_v3"
no_cache = False
book_folder_arg = None
for arg in sys.argv[1:]:
    if arg.startswith("--template="):
        template = arg.split("=", 1)[1]
    elif arg == "--no-cache":
        no_cache = True
    elif not arg.startswith("--"):
        book_folder_arg = arg

os.environ["TEMPLATE_WORKBOOK"] = template
if no_cache:
    os.environ["AI_NO_CACHE"] = "1"

from agent.config import get_settings, reload_settings  # noqa: E402
reload_settings()

from agent.book_reader import read_book, truncate_for_llm  # noqa: E402
from agent.librarian import WishLibrarian  # noqa: E402
from agent.models import ChapterInfo, BookInfo  # noqa: E402


def main() -> int:
    if not book_folder_arg:
        print("Usage: python regen_workbook.py <book_folder> [--template=NAME] [--no-cache]")
        return 1

    book_folder = Path(book_folder_arg)
    if not book_folder.exists():
        print(f"[!] Папка не найдена: {book_folder}")
        return 1

    source_pdf = book_folder / "source.pdf"
    if not source_pdf.exists():
        print(f"[!] source.pdf не найден в {book_folder}")
        return 1

    settings = get_settings()
    print(f"[*] Настройки: template_workbook={settings.template_workbook}, "
          f"AI_PROVIDER={settings.ai_provider}, no_cache={no_cache}")

    # Предупреждение если summary ещё не v3 — workbook получит «пустой» контекст
    summary_path = book_folder / "summary.md"
    if summary_path.exists():
        summary_text = summary_path.read_text(encoding="utf-8")
        if "Мини-эксперимент" in summary_text and "А у тебя как?" in summary_text:
            print("[*] ✅ summary.md содержит v3-секции (Мини-эксперимент + А у тебя как?)")
        else:
            print("[!] ⚠️  summary.md выглядит как v2 (нет секций v3). "
                  "Workbook получит «пустой» контекст — LLM может сгенерировать generic-CTA.")
    else:
        print("[!] ⚠️  summary.md отсутствует — workbook не получит контекст.")

    # Читаем PDF и готовим BookInfo (по аналогии с process_local_file)
    data = read_book(source_pdf)
    full_text = data["text"]
    if not full_text or len(full_text) < 500:
        print(f"[!] PDF слишком короткий: {len(full_text or '')} символов")
        return 1

    book = BookInfo(
        title=data.get("title") or source_pdf.stem,
        author=data.get("author") or "—",
        source_url=f"file://{source_pdf.resolve()}",
    )
    if data.get("chapters"):
        book.chapters = [
            ChapterInfo(number=i + 1, title=t)
            for i, t in enumerate(data["chapters"][:80])
        ]

    # Описание + идеи для AI
    import re
    sentences = re.split(r"(?<=[.!?])\s+", full_text)
    book.short_description = " ".join(sentences[:5])[:500]
    book.key_ideas = [
        p[:200] for p in full_text.split("\n\n") if len(p) > 50
    ][:10]

    print(f"[*] Книга: «{book.title}» ({book.author}), "
          f"{len(full_text)} chars, {len(book.chapters)} глав")

    librarian = WishLibrarian(use_ai_cache=not no_cache)

    try:
        workbook_path = librarian._generate_workbook(book, book_folder)
        if workbook_path:
            print(f"\n[+] Workbook готов: {workbook_path}")
            content = Path(workbook_path).read_text(encoding="utf-8")
            print(f"[+] Размер: {len(content)} chars")
            # Проверим наличие нового блока
            if "Поделитесь результатом" in content and "?from=workbook" in content:
                print("[+] ✅ Новый блок (Поделитесь результатом + ссылка ?from=workbook) на месте")
            else:
                print("[!] ⚠️  Новый блок или ссылка НЕ найдены — проверь вручную")
            return 0
        print("[!] _generate_workbook вернул None")
        return 2
    except Exception as e:
        print(f"[!] Ошибка: {e}")
        import traceback
        traceback.print_exc()
        return 3


if __name__ == "__main__":
    sys.exit(main())
