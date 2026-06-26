"""
Одноразовый скрипт: импорт готовых PDF-конспектов и воркбуков в библиотеку.

Назначение: «привести к одному виду» папку с PDF, сгенерированными ранее
(другим ИИ-инструментом или этой же программой), и положить их в
``output/library/`` в стандартной раскладке WishLibrarian.

LLM НЕ вызывается. Текст из PDF сохраняется как есть, с минимальной
очисткой шапки (двойные пробелы, заголовки «PDF»).

Использование:
    source .venv/Scripts/activate
    python -X utf8 scripts/import_external_pdfs.py
    python -X utf8 scripts/import_external_pdfs.py --src "C:/path/to/pdfs"
    python -X utf8 scripts/import_external_pdfs.py --src "..." --dry-run
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# Корень проекта (родитель scripts/)
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from agent.book_reader import read_book  # noqa: E402
from agent.config import get_settings  # noqa: E402
from agent.utils.logger import get_logger, setup_logging  # noqa: E402

logger = get_logger()


# ── Классификация ───────────────────────────────────────────────────

@dataclass
class PdfRecord:
    """Распарсенный PDF."""
    path: Path
    kind: str  # "summary" | "workbook" | "skip"
    title: str = ""
    author: str = ""
    text: str = ""
    raw_bytes: bytes = b""
    matched_book_title: str = ""  # для воркбука — найденная книга


# Мусорные имена, которые точно не книги
SKIP_FILENAMES = {
    "Новый документ",
    "шаблоны ",
    "Новый документ.pdf",
}


def _norm_text(s: str) -> str:
    """Сжать множественные пробелы/переносы, убрать emoji-мусор PDF."""
    s = re.sub(r"[ \t]+", " ", s)
    s = re.sub(r"\n[ \t]+", "\n", s)
    s = re.sub(r"\n{3,}", "\n\n", s)
    return s.strip()


def _is_summary(text_head: str) -> bool:
    """Первые ~500 символов текста — это конспект книги?"""
    head = text_head.lower()
    return "конспект книги" in head or "книги" in head[:200]


def _is_workbook(name: str, text_head: str) -> bool:
    """Это воркбук (по имени файла или тексту)?"""
    name_low = name.lower()
    if "воркбук" in name_low:
        return True
    head = text_head.lower()
    return "рабочая тетрадь" in head or "📝 воркбук" in head


def _extract_title_from_pdf_meta_or_text(p: Path, res: dict) -> str:
    """Title — из метаданных PDF; если мусор — берём из текста."""
    title = (res.get("title") or "").strip()
    if title and title not in ("Новый документ", "шаблоны ", "Microsoft Word Document"):
        return title
    # Fallback — первая строка текста
    text = res.get("text", "")
    for line in text.splitlines()[:10]:
        line = line.strip()
        if len(line) > 5 and "ЛАБОРАТОРИЯ" not in line.upper():
            return line
    return p.stem


def _extract_author_and_title(raw_title: str, text: str) -> Tuple[str, str]:
    """
    Из 'Айя Лиллен «Как загадывать желания…»' → ('Айя Лиллен', 'Как загадывать…').
    Из 'Виктор Франкл «Сказать жизни „Да…»' → ('Виктор Франкл', 'Сказать жизни „Да…').
    Из 'Конспект Э Е Вагер Выбор' → ('Э Е Вагер', 'Выбор').
    """
    # Случай 1: «Автор «Название»» / «Автор "Название"» / «Автор „Название"»
    # В метадате PDF название часто обрезано (нет закрывающей кавычки),
    # поэтому делаем закрывающую кавычку опциональной.
    m = re.match(
        r"^(?P<a>[^«»“”„‟\"]+?)\s*[«“„\"]"
        r"(?P<t>.+)$",
        raw_title,
    )
    if m:
        t = m.group("t").strip()
        # Если название заканчивается на закрывающую кавычку — снимаем
        t = re.sub(r"[»”\"]+\s*$", "", t).strip()
        return m.group("a").strip(), t

    # Случай 2: «Конспект И О Автор Название»
    m = re.match(
        r"^Конспект\s+(?:книги\s+)?(?P<a>[А-ЯЁ]\.?\s*[А-ЯЁ]\.?\s*[А-ЯЁа-яё\-]+)\s+(?P<t>.+)$",
        raw_title,
    )
    if m:
        return m.group("a").strip(), m.group("t").strip()

    # Случай 3: «Автор Название» (без кавычек) — ищем «По книге <Автор>» в тексте
    head = text[:1500]
    m = re.search(
        r"[Пп]о\s+книге\s+([А-ЯЁ][а-яё\-]+(?:\s+[А-ЯЁ][а-яё\-]+){0,3})",
        head,
    )
    if m:
        author_guess = m.group(1).strip()
        title = re.sub(r"^(Конспект|Книга)\s+", "", raw_title).strip()
        return author_guess, title

    # Случай 4: ничего не нашли
    return "—", raw_title


def _folder_name(author: str, title: str) -> str:
    """
    Транслит-имя папки.
    «Айя Лиллен» + «Как загадывать желания» → «Лillen_Как_загадывать_желания»
    """
    from agent.utils.normalize import _TRANSLIT

    def _tl(s: str) -> str:
        return "".join(_TRANSLIT.get(c, c) for c in s)

    a = re.sub(r"[^\w\s\-]", "", author).strip()
    t = re.sub(r"[^\w\s\-]", "", title).strip()
    # Если автор = «—» — используем только title
    if a == "—" or not a:
        return _tl(t)[:120].replace(" ", "_")
    # Иначе берём фамилию (последнее слово) + title
    a_short = a.split()[-1] if a.split() else a
    return f"{_tl(a_short)}_{_tl(t)}"[:140].replace(" ", "_")


# Явный маппинг для воркбуков «ЛАБОРАТОРИЯ ЖЕЛАНИЙ»:
# №  → (по какой книге этот воркбук)
WORKBOOK_NUMBER_TO_BOOK_TITLE = {
    "1": "Сказать жизни „Да",
    "2": "Выбор",
    "3": "Мечтать не вредно",
    "4": "Теория невероятности",
    "5": "Три ключа к исполнению желаний",
    "6": "Курс исполнения желаний",
    "7": "Код исполнения желаний",
    "8": "Правила достижения цели",
    "9": "Три ключа к исполнению желаний",
    "10": "Сила осознания",
    "11": "Сила осознания",
    "12": "Сила осознания",
    "13": "Сила осознания",
    "14": "Код исполнения желаний",
    "15": "Как загадывать желания, чтобы они исполнялись",
}


def _detect_workbook_target(
    workbook_text: str,
    summaries: List[PdfRecord],
    workbook_name: str = "",
) -> Optional[PdfRecord]:
    """Найти, к какому конспекту относится этот воркбук."""
    head = workbook_text[:1500]

    # 0) Fallback: номер воркбука (для «ЛАБОРАТОРИЯ ЖЕЛАНИЙ» — известная серия)
    m_num = re.search(r"Воркбук\s*№?\s*(\d+)", workbook_name, re.IGNORECASE)
    if not m_num:
        m_num = re.search(r"Воркбук\s*№?\s*(\d+)", head[:200], re.IGNORECASE)
    if m_num:
        num = m_num.group(1)
        ref_title_prefix = WORKBOOK_NUMBER_TO_BOOK_TITLE.get(num)
        if ref_title_prefix:
            ref_norm = re.sub(r"\s+", " ", ref_title_prefix).lower()
            ref_words = [w for w in re.split(r"\s+", ref_norm) if len(w) > 3]
            best: Optional[PdfRecord] = None
            best_score = 0
            for s in summaries:
                s_norm = (s.title + " " + s.author).lower()
                score = sum(1 for w in ref_words if w in s_norm)
                if score > best_score:
                    best_score = score
                    best = s
            if best and best_score >= 1:
                return best

    # 1) «По книге Автора»
    m = re.search(r"[Пп]о\s+книге\s+([А-ЯЁа-яё\.\s\-]{3,80}?)(?:\s+[«\"]|\n|$)", head)
    candidates_text = []
    if m:
        candidates_text.append(m.group(1).strip())

    # 2) «Автора „Название“» / «Автор Автор "Название"»
    m = re.search(r"([А-ЯЁа-яё\.\s\-]{3,80}?)\s*[«\"]([А-ЯЁа-яё][^«»\"]{2,100})[»\"]", head)
    if m:
        candidates_text.append(m.group(1).strip())

    # 3) «ВОРКБУК №N. Автор „Название“» (свёрнутая форма)
    m = re.match(
        r"📝\s*ВОРОБУК\s*(?:№\s*\d+\.?)?\s*\.?\s*"
        r"(?:Рабочая\s+тетрадь[:\s]+)?"
        r"(?:[А-ЯЁа-яё\.\s\-]{0,80}?)\s*[«\"]([А-ЯЁа-яё][^«»\"]{2,100})[»\"]",
        head,
    )
    if m:
        candidates_text.append(head.split("\n")[0])

    for cand in candidates_text:
        cand_norm = re.sub(r"\s+", " ", cand).lower().strip()
        if not cand_norm or len(cand_norm) < 3:
            continue
        cand_words = [w for w in re.split(r"\s+", cand_norm) if len(w) > 3]

        best: Optional[PdfRecord] = None
        best_score = 0
        for s in summaries:
            s_title_norm = s.title.lower()
            s_author_norm = s.author.lower()
            score = 0
            # По автору — главный критерий
            for w in cand_words:
                if w in s_author_norm:
                    score += 3
                if w in s_title_norm:
                    score += 1
            if score > best_score:
                best_score = score
                best = s

        if best and best_score >= 3:
            return best

    return None


# ── Главный процесс ────────────────────────────────────────────────

def scan_folder(src: Path) -> Tuple[List[PdfRecord], List[PdfRecord], List[Path]]:
    """Вернуть (summaries, workbooks, skipped)."""
    summaries: List[PdfRecord] = []
    workbooks: List[PdfRecord] = []
    skipped: List[Path] = []

    pdfs = sorted(src.glob("*.pdf"))
    logger.info("📂 Найдено PDF: {}", len(pdfs))

    for p in pdfs:
        # Быстрый skip по имени
        if p.stem.strip() in SKIP_FILENAMES:
            skipped.append(p)
            continue
        if p.stem.strip().lower() in {"шаблоны", "новый документ"}:
            skipped.append(p)
            continue
        # Шпаргалки / навигатор / кинотеатр — skip
        if any(s in p.stem.lower() for s in ("шпаргалк", "навигатор", "кинозал", "кинотеатр")):
            skipped.append(p)
            continue

        try:
            res = read_book(p)
        except Exception as e:
            logger.warning("⚠️  Не удалось прочитать {}: {}", p.name, e)
            skipped.append(p)
            continue

        text = _norm_text(res.get("text", ""))
        raw_title = _extract_title_from_pdf_meta_or_text(p, res)
        author, title = _extract_author_and_title(raw_title, text)
        # Если ничего не нашли — оставляем имя файла
        if not title or title == p.stem:
            title = p.stem

        head = text[:600]
        kind = "skip"
        if _is_summary(head):
            kind = "summary"
        elif _is_workbook(p.stem, head):
            kind = "workbook"
        else:
            skipped.append(p)
            continue

        rec = PdfRecord(
            path=p,
            kind=kind,
            title=title,
            author=author,
            text=text,
            raw_bytes=p.read_bytes(),
        )
        if kind == "summary":
            summaries.append(rec)
        else:
            workbooks.append(rec)

    return summaries, workbooks, skipped


def _clean_text_for_md(text: str) -> str:
    """Убираем PDF-маркеры в начале и причёсываем."""
    # Удаляем первый блок «ЛАБОРАТОРИЯ ЖЕЛАНИЙ» и «PDF» (если есть)
    text = re.sub(r"^ЛАБОРАТОРИЯ\s*\n?\s*ЖЕЛАНИЙ\s*\n+", "", text, flags=re.IGNORECASE)
    text = re.sub(r"^PDF\s*\n+", "", text, flags=re.IGNORECASE)
    # «📖  КОНСПЕКТ  КНИГИ» → «# Конспект книги» (если встречается в начале)
    text = re.sub(
        r"^📖\s*КОНСПЕКТ\s+КНИГИ\s*\n+",
        "## 📖 Конспект книги\n\n",
        text,
    )
    # «🎙  Голос  Желания» → «### 🎙 Голос Желания»
    text = re.sub(r"^([🎙🧪🔍🎁💭⚡📅🔥✍️📝🧩])\s+([А-ЯЁ][^\n]{2,80})$", r"### \1 \2", text, flags=re.MULTILINE)
    return text.strip()


def _make_header(rec: PdfRecord) -> str:
    return (
        f"# {rec.title}\n\n"
        f"**Автор:** {rec.author}\n\n"
        f"_Импортировано из `{rec.path.name}` (внешний PDF-конспект)_\n\n"
        f"---\n\n"
    )


def import_to_library(
    summaries: List[PdfRecord],
    workbooks: List[PdfRecord],
    output_dir: Path,
    dry_run: bool = False,
) -> Dict[str, int]:
    """Положить файлы в output/library/."""
    stats = {
        "summaries_imported": 0,
        "summaries_updated": 0,
        "workbooks_attached": 0,
        "workbooks_alone": 0,
        "errors": 0,
    }

    for s in summaries:
        folder_name = _folder_name(s.author, s.title)
        folder = output_dir / folder_name
        try:
            if folder.exists() and (folder / "summary.md").exists():
                if dry_run:
                    logger.info("⏭  [DRY] Уже есть: {} (пропуск)", folder.name)
                    stats["summaries_imported"] += 1
                else:
                    logger.info("⏭  Уже есть: {} (пропуск)", folder.name)
                    stats["summaries_imported"] += 1
                continue

            body = _clean_text_for_md(s.text)
            header = _make_header(s)
            full_text = header + body

            if dry_run:
                logger.info("📝 [DRY] Создам: {}/summary.md ({} символов)", folder_name, len(full_text))
                stats["summaries_imported"] += 1
                continue

            folder.mkdir(parents=True, exist_ok=True)
            (folder / "raw").mkdir(exist_ok=True)
            (folder / "summary.md").write_text(full_text, encoding="utf-8")
            # Копия оригинального PDF
            (folder / "source.pdf").write_bytes(s.raw_bytes)
            # Metadata
            metadata = {
                "title": s.title,
                "author": s.author,
                "source": "external_pdf",
                "source_file": s.path.name,
                "template_summary": "external",
                "template_workbook": "external",
                "imported_at": __import__("datetime").datetime.now().isoformat(timespec="seconds"),
            }
            (folder / "metadata.json").write_text(
                json.dumps(metadata, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            logger.info("✅ Импортирован: {} ({} симв.)", folder_name, len(full_text))
            stats["summaries_imported"] += 1
        except Exception as e:
            logger.error("💥 Ошибка при импорте {}: {}", s.path.name, e)
            stats["errors"] += 1

    # Воркбуки — привязываем к существующим/только что созданным папкам
    for w in workbooks:
        target = _detect_workbook_target(w.text, summaries, w.path.name)
        if target is None:
            # Не нашли пару — кладём как одиночный workbook
            folder_name = _folder_name(w.author or w.title, w.title or w.path.stem)
            folder = output_dir / folder_name
            try:
                if dry_run:
                    logger.info("📝 [DRY] Воркбук-одиночка: {}/workbook.md", folder_name)
                    stats["workbooks_alone"] += 1
                    continue
                folder.mkdir(parents=True, exist_ok=True)
                body = _clean_text_for_md(w.text)
                header = _make_header(w).replace("# ", "# ✍️ Воркбук: ")
                (folder / "workbook.md").write_text(header + body, encoding="utf-8")
                (folder / "source.pdf").write_bytes(w.raw_bytes)
                logger.info("✅ Воркбук-одиночка: {}", folder_name)
                stats["workbooks_alone"] += 1
            except Exception as e:
                logger.error("💥 Ошибка: {}", e)
                stats["errors"] += 1
            continue

        folder_name = _folder_name(target.author, target.title)
        folder = output_dir / folder_name
        try:
            if dry_run:
                logger.info("📝 [DRY] Воркбук → {} (из {})", folder_name, w.path.name)
                stats["workbooks_attached"] += 1
                continue
            folder.mkdir(parents=True, exist_ok=True)
            body = _clean_text_for_md(w.text)
            header = (
                f"# ✍️ Воркбук: {target.title}\n\n"
                f"**Автор:** {target.author}\n\n"
                f"_Импортировано из `{w.path.name}` (внешний PDF-воркбук)_\n\n"
                f"---\n\n"
            )
            (folder / "workbook.md").write_text(header + body, encoding="utf-8")
            # Обновляем metadata
            meta_path = folder / "metadata.json"
            if meta_path.exists():
                try:
                    meta = json.loads(meta_path.read_text(encoding="utf-8"))
                except (OSError, ValueError):
                    meta = {}
            else:
                meta = {"title": target.title, "author": target.author}
            meta["template_workbook"] = "external"
            meta["workbook_source"] = w.path.name
            meta_path.write_text(
                json.dumps(meta, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            logger.info("✅ Воркбук привязан к: {}", folder_name)
            stats["workbooks_attached"] += 1
        except Exception as e:
            logger.error("💥 Ошибка: {}", e)
            stats["errors"] += 1

    return stats


def main() -> int:
    parser = argparse.ArgumentParser(description="Импорт PDF-конспектов в библиотеку")
    parser.add_argument(
        "--src",
        type=Path,
        default=Path(r"C:\Users\kfigh\OneDrive\Desktop\Конспекты"),
        help="Папка с PDF (по умолчанию: папка «Конспекты» на рабочем столе)",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=None,
        help="Куда положить (по умолчанию: output/library из .env)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Только показать, что будет сделано, не создавая файлов",
    )
    args = parser.parse_args()

    setup_logging()
    logger.info("🚀 Импорт PDF-конспектов в библиотеку")
    logger.info("📂 Источник: {}", args.src)
    output_dir = args.out or get_settings().output_dir
    logger.info("📁 Назначение: {}", output_dir)

    if not args.src.exists():
        logger.error("❌ Папка не найдена: {}", args.src)
        return 2

    summaries, workbooks, skipped = scan_folder(args.src)

    logger.info("")
    logger.info("📊 Классификация:")
    logger.info("   📚 Конспектов (summary): {}", len(summaries))
    logger.info("   📝 Воркбуков:            {}", len(workbooks))
    logger.info("   🚫 Пропущено:            {}", len(skipped))
    for p in skipped:
        logger.info("      - {}", p.name)

    if not summaries and not workbooks:
        logger.warning("⚠️  Нечего импортировать")
        return 0

    logger.info("")
    logger.info("📚 Найденные конспекты:")
    for s in summaries:
        logger.info("   - «{}» — {} → /{}", s.title, s.author, _folder_name(s.author, s.title))
    logger.info("")
    logger.info("📝 Найденные воркбуки:")
    for w in workbooks:
        target = _detect_workbook_target(w.text, summaries, w.path.name)
        if target:
            logger.info("   - {} → «{}»", w.path.name, target.title)
        else:
            logger.info("   - {} → (без пары)", w.path.name)

    if args.dry_run:
        logger.info("")
        logger.info("🔍 Режим --dry-run, файлы не создаются")
        return 0

    logger.info("")
    stats = import_to_library(summaries, workbooks, output_dir, dry_run=False)

    logger.info("")
    logger.info("═══════════════════════════════════════")
    logger.info("✅ Конспектов импортировано:    {}", stats["summaries_imported"])
    logger.info("✅ Воркбуков привязано:         {}", stats["workbooks_attached"])
    logger.info("✅ Воркбуков-одиночек:          {}", stats["workbooks_alone"])
    logger.info("❌ Ошибок:                      {}", stats["errors"])
    logger.info("═══════════════════════════════════════")
    return 0 if stats["errors"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
