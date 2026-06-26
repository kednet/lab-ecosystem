"""
`--export` — конвертация обработанной книги в PDF/EPUB/DOCX.

Использует `pandoc` если установлен в системе, иначе:
  - PDF  → reportlab (чистый Python, всегда работает)
  - HTML → собственный мини-конвертер
  - EPUB/DOCX — без pandoc не создаются
"""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from typing import List, Optional

from agent.utils.logger import get_logger

logger = get_logger()


def _check_pandoc() -> bool:
    return shutil.which("pandoc") is not None


def collect_book_text(folder: Path) -> str:
    """Собрать все .md файлы книги в один текст (для экспорта)."""
    parts: List[str] = []
    md_files = [
        ("summary.md", "📝 Конспект"),
        ("workbook.md", "✍️  Воркбук"),
        ("practical_tips.md", "💡 Практические советы"),
        ("reviews.md", "💬 Отзывы"),
        ("scientific.md", "🔬 Научные статьи"),
        ("buy_links.md", "🛒 Где купить"),
    ]
    for fname, title in md_files:
        p = folder / fname
        if p.exists():
            parts.append(f"\n\n# {title}\n\n")
            parts.append(p.read_text(encoding="utf-8", errors="ignore"))
    if not parts:
        return ""
    # Метаданные в шапку
    meta = folder / "metadata.json"
    if meta.exists():
        try:
            import json
            md = json.loads(meta.read_text(encoding="utf-8"))
            header = (
                f"# {md.get('title', 'Без названия')}\n\n"
                f"_Автор: {md.get('author', '—')}_\n\n"
                f"{md.get('short_description') or ''}\n\n"
            )
            parts.insert(0, header)
        except (OSError, ValueError):
            pass
    return "".join(parts)


def export_book(
    folder: Path,
    formats: List[str],
    output_dir: Optional[Path] = None,
) -> List[Path]:
    """
    Экспортировать книгу в указанные форматы.
    Возвращает список созданных файлов.
    """
    output_dir = output_dir or folder
    text = collect_book_text(folder)
    if not text:
        return []

    out_files: List[Path] = []
    stem = folder.name

    for fmt in formats:
        fmt = fmt.strip().lower()
        if fmt == "txt":
            p = output_dir / f"{stem}.txt"
            p.write_text(text, encoding="utf-8")
            out_files.append(p)
        elif fmt == "pdf":
            # Всегда пробуем reportlab (pure-Python), без зависимости от pandoc
            p = output_dir / f"{stem}.pdf"
            try:
                _md_text_to_pdf_file(text, p, title=stem)
                out_files.append(p)
            except Exception as e:
                logger.error("Не удалось создать PDF: {}", e)
        elif fmt == "html":
            p = output_dir / f"{stem}.html"
            html = _md_to_html_simple(text)
            p.write_text(html, encoding="utf-8")
            out_files.append(p)
        elif fmt in ("epub", "docx"):
            if not _check_pandoc():
                logger.warning(
                    "⚠️  Формат {} требует pandoc. Установите: "
                    "https://pandoc.org/", fmt,
                )
                continue
            md_file = output_dir / f"{stem}.md"
            if not md_file.exists():
                md_file.write_text(text, encoding="utf-8")
            try:
                subprocess.run(
                    ["pandoc", str(md_file), "-o", str(output_dir / f"{stem}.{fmt}")],
                    check=True, capture_output=True, timeout=60,
                )
                out_files.append(output_dir / f"{stem}.{fmt}")
                md_file.unlink(missing_ok=True)
            except (subprocess.CalledProcessError, subprocess.TimeoutExpired, FileNotFoundError):
                continue
    return out_files


def md_to_pdf(md_path: Path, pdf_path: Path) -> Path:
    """
    Сконвертировать один .md файл в .pdf (reportlab).
    Возвращает путь к созданному PDF.
    """
    text = md_path.read_text(encoding="utf-8", errors="ignore")
    title = md_path.stem.replace("_", " ")
    _md_text_to_pdf_file(text, pdf_path, title=title)
    return pdf_path


def _md_to_html_simple(text: str) -> str:
    """Минимальный MD → HTML (без зависимостей)."""
    import html as _html
    out = []
    for line in text.splitlines():
        if line.startswith("# "):
            out.append(f"<h1>{_html.escape(line[2:])}</h1>")
        elif line.startswith("## "):
            out.append(f"<h2>{_html.escape(line[3:])}</h2>")
        elif line.startswith("### "):
            out.append(f"<h3>{_html.escape(line[4:])}</h3>")
        elif line.startswith("- "):
            out.append(f"<li>{_html.escape(line[2:])}</li>")
        elif line.strip() == "":
            out.append("<br>")
        else:
            out.append(f"<p>{_html.escape(line)}</p>")
    return (
        "<!doctype html><html><head><meta charset='utf-8'>"
        "<style>body{font-family:system-ui;max-width:800px;margin:2em auto;padding:0 1em;line-height:1.6}"
        "h1,h2,h3{color:#333}</style></head><body>"
        + "\n".join(out) + "</body></html>"
    )


# ── MD → PDF (reportlab) ──────────────────────────────────────────

# Поддержка кириллицы в reportlab: используем встроенный шрифт Helvetica,
# но для кириллицы — DejaVuSans / Liberation (если есть в системе).
# Если кириллического шрифта нет — fallback на Helvetica + transliterate.

def _try_register_cyrillic_font():
    """
    Попробовать зарегистрировать TTF-шрифт с поддержкой кириллицы.
    Возвращает (font_name, is_cyrillic).
    """
    try:
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont
    except ImportError:
        return "Helvetica", False

    # Кандидаты шрифтов, которые обычно есть в системе
    candidates = [
        # Linux
        ("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", "DejaVu"),
        ("/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf", "Liberation"),
        # Windows
        ("C:/Windows/Fonts/arial.ttf", "Arial"),
        ("C:/Windows/Fonts/segoeui.ttf", "SegoeUI"),
        ("C:/Windows/Fonts/tahoma.ttf", "Tahoma"),
        # Mac
        ("/Library/Fonts/Arial.ttf", "ArialMac"),
        ("/System/Library/Fonts/Supplemental/Arial.ttf", "ArialMac2"),
    ]
    for path, name in candidates:
        if Path(path).exists():
            try:
                pdfmetrics.registerFont(TTFont(name, path))
                return name, True
            except Exception as e:
                logger.debug("Не удалось зарегистрировать {}: {}", path, e)
                continue
    return "Helvetica", False


def _strip_inline_md(text: str) -> str:
    """Снять простую inline-разметку: **жирный**, *курсив*, `код` → текст."""
    import re as _re
    # Сохраняем маркеры на потом, чтобы reportlab мог отрисовать жирный/курсив
    # Здесь только убираем лишние переносы и пробелы
    return text.replace("\r\n", "\n")


def _md_text_to_pdf_file(text: str, out_path: Path, *, title: str = "Book") -> None:
    """
    Сконвертировать markdown-текст в PDF через reportlab.
    Поддерживает: #/##/### заголовки, - списки, **жирный**, *курсив*, `код`, |таблицы|.
    """
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_LEFT
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import cm
    from reportlab.platypus import (
        Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle,
    )

    font_name, cyrillic = _try_register_cyrillic_font()
    if not cyrillic:
        # Транслитерируем весь текст, чтобы кириллица хоть как-то отобразилась
        try:
            from agent.utils.normalize import _TRANSLIT
            def _tl(s: str) -> str:
                return "".join(_TRANSLIT.get(c, c) for c in s)
            text = _tl(text)
            title = _tl(title)
            logger.warning(
                "⚠️  Кириллический шрифт не найден — PDF будет транслитерирован. "
                "Установите DejaVu/Liberation/Arial для корректного отображения."
            )
        except ImportError:
            pass

    doc = SimpleDocTemplate(
        str(out_path),
        pagesize=A4,
        leftMargin=2 * cm,
        rightMargin=2 * cm,
        topMargin=2 * cm,
        bottomMargin=2 * cm,
        title=title,
    )

    base = getSampleStyleSheet()
    h1 = ParagraphStyle(
        "H1", parent=base["Heading1"], fontName=font_name,
        fontSize=22, leading=28, spaceAfter=14, textColor=colors.HexColor("#1a1a1a"),
    )
    h2 = ParagraphStyle(
        "H2", parent=base["Heading2"], fontName=font_name,
        fontSize=16, leading=22, spaceAfter=10, textColor=colors.HexColor("#333333"),
    )
    h3 = ParagraphStyle(
        "H3", parent=base["Heading3"], fontName=font_name,
        fontSize=13, leading=18, spaceAfter=8, textColor=colors.HexColor("#444444"),
    )
    body = ParagraphStyle(
        "Body", parent=base["BodyText"], fontName=font_name,
        fontSize=10.5, leading=15, spaceAfter=6, alignment=TA_LEFT,
    )
    bullet = ParagraphStyle(
        "Bullet", parent=body, leftIndent=18, bulletIndent=6, spaceAfter=2,
    )
    quote = ParagraphStyle(
        "Quote", parent=body, leftIndent=20, fontSize=10,
        textColor=colors.HexColor("#555555"), spaceAfter=10,
    )
    code = ParagraphStyle(
        "Code", parent=body, fontName="Courier", fontSize=9,
        leftIndent=10, textColor=colors.HexColor("#222222"),
        backColor=colors.HexColor("#f5f5f5"), spaceAfter=8,
    )

    story = []
    # Разбираем markdown построчно
    lines = _strip_inline_md(text).split("\n")
    i = 0
    while i < len(lines):
        line = lines[i].rstrip()

        # Пустая строка — пропуск
        if not line.strip():
            i += 1
            continue

        # Горизонтальная линия
        if line.strip() in ("---", "***", "___"):
            story.append(Spacer(1, 0.2 * cm))
            from reportlab.platypus import HRFlowable
            story.append(HRFlowable(width="100%", thickness=0.5, color=colors.grey))
            story.append(Spacer(1, 0.2 * cm))
            i += 1
            continue

        # Заголовки
        if line.startswith("# "):
            story.append(Paragraph(_md_inline_to_html(line[2:].strip()), h1))
        elif line.startswith("## "):
            heading_text = line[3:].strip()
            story.append(Paragraph(_md_inline_to_html(heading_text), h2))
            # Спец-секция: «📝 Поля для ответов» → рисуем пустые строки
            # под каждый вопрос для рукописного заполнения.
            if "Поля для ответов" in heading_text:
                i = _render_answer_fields_block(
                    story, lines, i, font_name, cm, Paragraph,
                    ParagraphStyle, Table, TableStyle, colors, Spacer,
                )
                continue
        elif line.startswith("### "):
            story.append(Paragraph(_md_inline_to_html(line[4:].strip()), h3))
        # Маркированный список
        elif line.lstrip().startswith(("- ", "* ", "+ ")):
            item = line.lstrip()[2:].strip()
            story.append(Paragraph("• " + _md_inline_to_html(item), bullet))
        # Нумерованный список
        elif line[:3].rstrip(".").isdigit() and line[3:5] in (". ", ") "):
            item = line.split(" ", 1)[1] if " " in line else ""
            story.append(Paragraph(_md_inline_to_html(item), bullet))
        # Чекбокс
        elif line.lstrip().startswith(("- [ ] ", "- [x] ", "* [ ] ", "* [x] ")):
            item = line.lstrip()[6:].strip()
            mark = "☐" if "[ ]" in line[:8] else "☑"
            story.append(Paragraph(f"{mark} {_md_inline_to_html(item)}", bullet))
        # Цитата
        elif line.startswith("> "):
            story.append(Paragraph(_md_inline_to_html(line[2:].strip()), quote))
        # Код-блок
        elif line.startswith("```"):
            i += 1
            code_lines = []
            while i < len(lines) and not lines[i].lstrip().startswith("```"):
                code_lines.append(lines[i])
                i += 1
            code_text = _html.escape("\n".join(code_lines))
            story.append(Paragraph(code_text.replace("\n", "<br/>"), code))
            i += 1
            continue
        # Таблица markdown
        elif line.strip().startswith("|") and i + 1 < len(lines) and lines[i + 1].strip().startswith("|"):
            tbl_lines = []
            while i < len(lines) and lines[i].strip().startswith("|"):
                tbl_lines.append(lines[i].strip())
                i += 1
            try:
                _add_md_table(story, tbl_lines, font_name)
            except Exception as e:
                logger.debug("Не удалось отрисовать таблицу: {}", e)
            continue
        # Обычный параграф
        else:
            story.append(Paragraph(_md_inline_to_html(line), body))
        i += 1

    doc.build(story)


def _render_answer_fields_block(
    story, lines, start_idx, font_name, cm_mod, Paragraph,
    ParagraphStyle, Table, TableStyle, colors, Spacer,
):
    """
    Спец-рендер секции «📝 Поля для ответов».

    Ожидаемый формат после заголовка::

        N. _Вопрос_
           _______________
           _______________
           ...

    Рисует под каждым вопросом сетку из пустых строк с горизонтальной
    линией снизу — для письма от руки.
    Возвращает индекс строки, на которой основной цикл должен продолжить.
    """
    import re as _re
    LINE_RE = _re.compile(r"^\s*(\d+)\.\s+(.*)$")
    i = start_idx + 1
    while i < len(lines):
        ln = lines[i]
        s = ln.strip()
        if s.startswith("## "):
            # вышли в следующую секцию — внешний цикл обработает её
            return i - 1
        m = LINE_RE.match(ln)
        if m:
            qno = m.group(1)
            qtext = m.group(2)
            story.append(Paragraph(
                f"<b>{qno}.</b> {_md_inline_to_html(qtext)}",
                ParagraphStyle("AFQuestion", fontName=font_name, fontSize=10.5, leading=14, spaceBefore=6, spaceAfter=2),
            ))
            # Считаем подряд идущие строки-подчёркивания
            j = i + 1
            blanks = 0
            while j < len(lines) and lines[j].strip().startswith("_"):
                blanks += 1
                j += 1
            blanks = max(blanks, 1)
            # Таблица с одной колонкой и N пустыми строками + нижняя граница
            rows = [[" "]] * blanks
            t = Table(rows, colWidths=[16 * cm_mod], rowHeights=[0.85 * cm_mod] * blanks)
            t.setStyle(TableStyle([
                ("LINEBELOW", (0, -1), (-1, -1), 0.5, colors.HexColor("#666666")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                ("TOPPADDING", (0, 0), (-1, -1), 1),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 1),
            ]))
            story.append(t)
            i = j
            continue
        # пустая строка или текст без номера — пропускаем
        if not s:
            i += 1
            continue
        # мусор между вопросами — тоже пропускаем, но не уходим за секцию
        i += 1
    return i - 1


def _md_inline_to_html(text: str) -> str:
    """
    Конвертировать inline-разметку markdown в HTML для reportlab Paragraph:
      **жирный** → <b>...</b>
      *курсив*   → <i>...</i>
      `код`     → <font face="Courier">...</font>
      [link](url) → <link href="url">link</link>
    """
    import re as _re
    import html as _html

    # Экранируем HTML-опасные символы
    s = _html.escape(text)

    # Код (`...`) — сначала, чтобы ** и * внутри не мешали
    s = _re.sub(
        r"`([^`]+)`",
        r'<font face="Courier" color="#222">\1</font>',
        s,
    )
    # Жирный (**...**)
    s = _re.sub(r"\*\*([^\*]+)\*\*", r"<b>\1</b>", s)
    # Курсив (*...* или _..._)
    s = _re.sub(r"(?<!\*)\*([^\*]+)\*(?!\*)", r"<i>\1</i>", s)
    s = _re.sub(r"(?<!_)_([^_]+)_(?!_)", r"<i>\1</i>", s)
    # Ссылки [text](url) — оставляем как plain text, без clickable (reportlab)
    s = _re.sub(r"\[([^\]]+)\]\(([^\)]+)\)", r'<font color="#0066cc">\1</font>', s)

    return s


def _add_md_table(story, tbl_lines: list, font_name: str) -> None:
    """Добавить markdown-таблицу в story."""
    from reportlab.lib import colors
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.units import cm
    from reportlab.platypus import Paragraph, Table, TableStyle

    cell_style = ParagraphStyle(
        "Cell", fontName=font_name, fontSize=9, leading=12,
    )
    header_style = ParagraphStyle(
        "CellH", fontName=font_name, fontSize=9, leading=12,
        textColor=colors.white,
    )

    rows = []
    for idx, raw in enumerate(tbl_lines):
        # Парсим "| a | b | c |"
        cells = [c.strip() for c in raw.strip("|").split("|")]
        is_separator = all(_re_is_separator(c) for c in cells)
        if is_separator:
            continue
        styled = [
            Paragraph(_md_inline_to_html(c), header_style if idx == 0 else cell_style)
            for c in cells
        ]
        rows.append(styled)

    if not rows:
        return

    t = Table(rows, hAlign="LEFT")
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#3a7bc8")),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.grey),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    story.append(t)
    from reportlab.platypus import Spacer
    story.append(Spacer(1, 0.3 * cm))


def _re_is_separator(s: str) -> bool:
    """`---`, `:---:`, `---:` → True."""
    import re as _re
    return bool(_re.match(r"^:?-+:?$", s.strip()))
