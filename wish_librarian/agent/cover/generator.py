"""
CoverGenerator — главный класс генерации SVG-обложек.

Использование:
    from agent.cover import CoverGenerator, CoverStyle
    gen = CoverGenerator()
    result = gen.generate(
        title="Трансерфинг реальности",
        author="Вадим Зеланд",
        genre="эзотерика",
    )
    # result = {"svg": bytes, "style": CoverStyle.MYSTICAL, "scheme": {...}, "png": bytes|None}

    # Сохранение:
    folder / "cover_local.svg".write_bytes(result["svg"])
    if result["png"]:
        (folder / "cover.png").write_bytes(result["png"])
"""
from __future__ import annotations

import re
from enum import Enum
from pathlib import Path
from typing import Optional, Union

from agent.cover.colors import ColorGenerator, get_color_generator
from agent.cover.templates import get_template
from agent.models import BookInfo
from agent.utils.logger import get_logger


logger = get_logger()


class CoverStyle(str, Enum):
    """Стиль обложки. `value` — строка для шаблонов и метаданных.

    `OG` — отдельный формат 1200×630 для og:image (не книжная обложка).
    """
    MINIMAL   = "minimal"
    GRADIENT  = "gradient"
    GEOMETRIC = "geometric"
    MYSTICAL  = "mystical"
    BUSINESS  = "business"
    MODERN    = "modern"
    CLASSIC   = "classic"
    VINTAGE   = "vintage"
    OG        = "og"

    @classmethod
    def parse(cls, value: Optional[str]) -> Optional["CoverStyle"]:
        """Парсит строку в enum, None/'' → None (использовать auto)."""
        if not value:
            return None
        v = value.strip().lower()
        for s in cls:
            if s.value == v:
                return s
        return None


# ── Маппинг жанр → стиль (word-boundary, не substring!) ────────────
# Новые стили (modern/classic/vintage) — ПОСЛЕ базовых, чтобы не затирать
# основные правила (если в title есть слово «классик», это может быть не
# наш стиль «classic», а просто жанровая отсылка → пусть сначала отработают
# базовые правила).
_STYLE_RULES: list[tuple[CoverStyle, tuple[str, ...]]] = [
    (CoverStyle.MYSTICAL, (
        "эзотер", "духовн", "мистик", "медитац", "трансерф",
        "реальност", "энергет", "карма", "астрал", "чакр",
    )),
    (CoverStyle.BUSINESS, (
        "бизнес", "финанс", "карьер", "маркетинг", "продаж",
        "менеджмент", "лидерств", "стартап", "предприним",
    )),
    (CoverStyle.GRADIENT, (
        "психолог", "саморазвит", "мотивац", "привычк", "мышлени",
        "эмоци", "отношен", "коммуникац", "самосовершенств",
    )),
    (CoverStyle.GEOMETRIC, (
        "наука", "научн", "исследован", "технолог", "истор",
    )),
    # ── Новые стили (после базовых) ──
    (CoverStyle.MODERN, (
        "модерн", "современ", "актуальн", "digital",
    )),
    (CoverStyle.CLASSIC, (
        "классик", "шедевр", "бестселлер", "легендарн", "франкл",
    )),
    (CoverStyle.VINTAGE, (
        "винтаж", "ретро", "старин", "архив", "эпос",
    )),
]


# ── Маппинг жанр/название → категория-плашка ──────────────────────
# CATEGORY — это короткая надпись-плашка («Психология», «Эзотерика» и т.п.)
# для новых шаблонов modern/classic/vintage. В старых шаблонах просто
# игнорируется (плейсхолдер подставляется, но в SVG не используется).
_CATEGORY_RULES: list[tuple[str, tuple[str, ...]]] = [
    ("Психология", (
        "психолог", "мышлени", "эмоци", "отношен", "коммуникац",
        "привычк", "канеман",
    )),
    ("Эзотерика", (
        "эзотер", "духовн", "мистик", "медитац", "трансерф",
        "реальност", "энергет", "карма", "астрал", "чакр",
        "зеланд", "лиллен", "годдард", "уолш",
    )),
    ("Бизнес", (
        "бизнес", "финанс", "карьер", "маркетинг", "продаж",
        "менеджмент", "лидерств", "стартап", "предприним",
        "деньг", "заработ", "три_тайных",
    )),
    ("Саморазвитие", (
        "саморазвит", "мотивац", "самосоверш", "успех", "мечт", "достижен",
    )),
    ("Философия", (
        "философ", "смысл", "счастье", "франкл", "конт",
    )),
    ("Наука", (
        "наука", "научн", "исследован", "технолог",
    )),
    ("Практика", (
        "практик", "техник", "упражнен", "аффермац",
    )),
    # (default — Non-fiction)
]


# ── Маппинг стиль → max_chars для переноса title ───────────────
# font-size в шаблоне определяет, сколько символов влезает в 340px
# (viewBox 400, отступ 30px с каждой стороны).
# Эмпирические значения:
#   modern (font-size=38)         → 14  (bold, широкие буквы)
#   classic (font-size=34)        → 16
#   vintage (font-size=32)        → 18
#   minimal/gradient (28)         → 22
#   mystical (26)                 → 24
#   business (28)                 → 22
#   geometric (28)                → 22
#   og (большой layout)           → 28
_STYLE_MAX_CHARS: dict[str, int] = {
    "modern":    14,
    "classic":   16,
    "vintage":   18,
    "minimal":   22,
    "gradient":  22,
    "geometric": 22,
    "mystical":  24,
    "business":  22,
    "og":        28,
}


# ── Конфиг центрирования title-блока для шаблонов с динамическим y ──
# block_top / block_bottom — диапазон y, внутри которого title должен
# центрироваться (последняя строка не должна налезать на бренд / автора).
# line_height_factor — множитель для font-size в line-height (1.2 = 120%).
_TITLE_BLOCK_CONFIG: dict[str, dict] = {
    "mystical": {
        "block_top": 200,                # ниже верхнего декора (circle r=40 на y=120)
        "block_bottom": 420,             # выше блока автора (y=455 в новом шаблоне)
        "line_height_factor": 1.2,
    },
}


# ── Главный класс ──────────────────────────────────────────────────
class CoverGenerator:
    """
    Генерирует SVG-обложку + (опц.) PNG.

    Детерминирован: одна и та же (title, author) → один и тот же SVG.
    """

    DEFAULT_BRAND_NAME     = "ЛАБОРАТОРИЯ ЖЕЛАНИЙ"
    DEFAULT_DISCLAIMER     = "Обложка сгенерирована автоматически, не является официальным изданием"
    MAX_TITLE_LEN          = 38
    MAX_AUTHOR_LEN         = 45

    def __init__(self, color_gen: Optional[ColorGenerator] = None):
        self.color_gen = color_gen or get_color_generator()

    # ── Главный метод ───────────────────────────────────────────
    def generate(
        self,
        title: str,
        author: str,
        *,
        genre: Optional[str] = None,
        style: Optional[Union[CoverStyle, str]] = None,
        brand_name: Optional[str] = None,
        disclaimer: Optional[str] = None,
        forced_scheme: Optional[str] = None,
        category: Optional[str] = None,
    ) -> dict:
        """
        Сгенерировать SVG-обложку.

        Args:
            title: название книги
            author: автор
            genre: жанр (используется для автодетекта стиля/категории)
            style: явный стиль (CoverStyle enum или строка) или None для auto
            category: явная категория-плашка (например, «Психология»).
                     Если None — определяется по genre+title через _detect_category().

        Returns:
            {
              "svg":    bytes,            # SVG-код
              "style":  CoverStyle,       # использованный стиль
              "scheme": dict,            # {primary, secondary, text, accent}
              "title":  str,              # усечённый title
              "author": str,              # усечённый author
              "category": str,            # категория-плашка (для логов/метаданных)
            }
        """
        # 1. Стиль: явный > из жанра > minimal
        if isinstance(style, str):
            style = CoverStyle.parse(style)
        if style is None:
            style = self._detect_style_from_text(genre or "")
        if style is None:
            style = CoverStyle.MINIMAL

        # 2. Палитра (с авто-фиксом контраста)
        scheme = self.color_gen.generate(
            title, author, forced_scheme=forced_scheme,
        )

        # 3. Усечение title/author
        # НЕ усекаем title жёстко (38) — лучше пусть wrap разобьёт на 2-3 строки.
        # Жёсткое усечение сделаем ПОСЛЕ wrap, если title всё равно не влезает.
        title_clean  = self._strip(title or "")
        author_clean = self._truncate(self._strip(author or ""), self.MAX_AUTHOR_LEN)

        # 4. Категория-плашка (явная > автодетект по genre+title > "Non-fiction")
        category_clean = self._truncate(
            self._strip(category or self._detect_category(genre or "", title or "") or "Non-fiction"),
            24,
        )

        # 5. Подстановка в шаблон
        template = get_template(style.value)
        svg = template
        svg = svg.replace("{{TITLE}}",       self._escape(title_clean))
        svg = svg.replace("{{AUTHOR}}",      self._escape(author_clean))
        svg = svg.replace("{{CATEGORY}}",    self._escape(category_clean))
        svg = svg.replace("{{COLOR1}}",      scheme["primary"])
        svg = svg.replace("{{COLOR2}}",      scheme["secondary"])
        svg = svg.replace("{{TEXT_COLOR}}",  scheme["text"])
        svg = svg.replace("{{ACCENT}}",      scheme["accent"])
        svg = svg.replace(
            "{{BRAND_NAME}}",
            self._escape(self._truncate(brand_name or self.DEFAULT_BRAND_NAME, 35)),
        )
        svg = svg.replace(
            "{{DISCLAIMER}}",
            self._escape(disclaimer or self.DEFAULT_DISCLAIMER),
        )

        # 6. Перенос длинных title на строки (max_chars по font-size)
        # Ширина viewBox = 400, запас по 30px с каждой стороны = 340px юзабельных
        # font-size 38 → ~14-16 симв, 32 → ~18-20, 28 → ~22-24, 26 → ~24-26, 22 → ~28-30
        # Сделаем зависимость: max_chars = int(360 / font_size * 1.4)
        # На практике подбираем по шаблону (см. _STYLE_TO_MAX_CHARS).
        max_chars = _STYLE_MAX_CHARS.get(style.value, 22)
        svg, title_lines = self._wrap_title_to_tspans(svg, max_chars=max_chars)

        # 7. Для шаблонов с динамическим title-блоком (mystical) — рассчитать
        #    базовый y первой строки и line-height, чтобы блок центрировался
        #    по высоте вне зависимости от числа строк.
        svg = self._fit_title_block(svg, style=style.value, lines=title_lines)

        return {
            "svg":      svg.encode("utf-8"),
            "style":    style,
            "scheme":   scheme,
            "title":    title_clean,
            "author":   author_clean,
            "category": category_clean,
        }

    # ── Хелпер: перенос длинного title на строки для SVG ───────
    @staticmethod
    def _wrap_title_to_tspans(svg: str, max_chars: int, max_lines: int = 3) -> tuple[str, int]:
        """
        Находит в SVG все вхождения `<text ...>SINGLE_TITLE</text>` (одна строка)
        и заменяет на multi-tspan с переносом по словам, если title длиннее
        max_chars.

        Ограничения:
          - Не трогает мелкий текст (font-size ≤ 10) — это disclaimer / бренд-блок,
            его перенос ломает визуал (на скрине видно было: «Обложка сгенерирована
            автоматически, не является официальным изданием» расползлось на 4 строки).
          - Максимум max_lines строк (default 3). Если и после этого не влезает —
            последняя строка обрезается с «…».
          - title-anchor=middle: x выравнивается по центру; иначе — не трогаем.

        Returns:
            (svg, max_lines_count) — кол-во строк в самом «длинном» title-блоке
            (используется _fit_title_block для центрирования).
        """
        import re

        max_seen_lines = 1

        def repl(match: re.Match) -> str:
            nonlocal max_seen_lines
            open_tag = match.group(1)
            content = match.group(2).strip()
            if not content or "<tspan" in content or "\n" in content:
                return match.group(0)  # уже multiline, не трогаем

            # Достаём font-size
            fs_m = re.search(r'font-size="([^"]+)"', open_tag)
            fs = float(fs_m.group(1)) if fs_m else 28

            # Мелкий текст (disclaimer, brand) — не переносим, оставляем как есть
            if fs <= 10:
                return match.group(0)

            # Короткий title — не трогаем
            if len(content) <= max_chars:
                max_seen_lines = max(max_seen_lines, 1)
                return match.group(0)

            # Достаём x, y, text-anchor
            x_m = re.search(r'x="([^"]+)"', open_tag)
            y_m = re.search(r'y="([^"]+)"', open_tag)
            ta_m = re.search(r'text-anchor="([^"]+)"', open_tag)
            x = x_m.group(1) if x_m else "200"
            y = y_m.group(1) if y_m else "290"
            text_anchor = ta_m.group(1) if ta_m else "middle"
            line_h = fs * (1.2 if fs < 32 else 1.1)

            # Разбиваем по словам
            words = content.split()
            lines: list[str] = []
            cur = ""
            for w in words:
                # Если слово длиннее max_chars — режем посимвольно
                while len(w) > max_chars:
                    if cur:
                        lines.append(cur)
                        cur = ""
                    lines.append(w[:max_chars])
                    w = w[max_chars:]
                if not cur:
                    cur = w
                elif len(cur) + 1 + len(w) <= max_chars:
                    cur += " " + w
                else:
                    lines.append(cur)
                    cur = w
            if cur:
                lines.append(cur)

            # Если строк > max_lines — обрезаем с «…»
            if len(lines) > max_lines:
                lines = lines[:max_lines]
                last = lines[-1]
                if len(last) > max_chars - 1:
                    last = last[: max_chars - 2].rstrip() + "…"
                else:
                    last = last.rstrip() + "…"
                lines[-1] = last

            if len(lines) <= 1:
                max_seen_lines = max(max_seen_lines, 1)
                return match.group(0)  # одна строка, оставляем

            # Собираем tspan'ы (каждый с x= и dy= для перехода на новую строку)
            # ВАЖНО: text-anchor="middle" нужно дублировать в каждый tspan —
            # в Chromium/Edge text-anchor НЕ наследуется через tspan с явным x=.
            tspans = []
            for i, line in enumerate(lines):
                dy = "0" if i == 0 else f"{line_h:.1f}"
                tspans.append(f'<tspan x="{x}" dy="{dy}" text-anchor="{text_anchor}">{line}</tspan>')
            max_seen_lines = max(max_seen_lines, len(lines))
            return f'<text {open_tag}>{chr(10).join(tspans)}</text>'

        # Паттерн: <text {любые атрибуты}>{title}</text>
        # title может содержать HTML-escaped символы (&amp; &lt; &gt; &quot; &apos;)
        pattern = re.compile(
            r'<text ([^>]+)>([^<]+)</text>',
            re.MULTILINE,
        )
        new_svg = pattern.sub(repl, svg)
        return new_svg, max_seen_lines

    # ── Хелпер: центрирование title-блока по высоте ─────────────
    @staticmethod
    def _fit_title_block(svg: str, style: str, lines: int) -> str:
        """
        Для шаблонов, где title-блок центрируется по высоте обложки
        (плейсхолдер {{TITLE_Y}}), рассчитать базовую y-координату первой
        строки так, чтобы блок центрировался.

        Остальные стили (с фиксированным y) — функция ничего не делает
        (плейсхолдер в шаблоне не объявлен, replace вернёт исходную строку).

        Алгоритм:
        1. Найти в шаблоне font-size для title-блока.
        2. Вычислить line-height по font-size × коэффициент из _TITLE_BLOCK_CONFIG.
        3. Поставить первую строку на y = center - (lines-1) * line_h / 2.
        4. Ограничить, чтобы блок не вылезал за block_top / block_bottom.
        """
        import re

        cfg = _TITLE_BLOCK_CONFIG.get(style)
        if not cfg:
            return svg

        # Если плейсхолдера нет в шаблоне — ничего не делаем
        if "{{TITLE_Y}}" not in svg:
            return svg

        # Достаём font-size из тега, где стоит {{TITLE_Y}} (после того как
        # _wrap_title_to_tspans мог превратить <text> в <text><tspan/></text>,
        # {{TITLE_Y}} всё ещё в открывающем теге <text>).
        fs_match = re.search(
            r'y="\{\{TITLE_Y\}\}"[^>]*font-size="([^"]+)"',
            svg,
        )
        if not fs_match:
            return svg
        font_size = float(fs_match.group(1))
        line_height = font_size * cfg["line_height_factor"]

        # Если блок однострочный — ставим y ровно в центр диапазона
        if lines <= 1:
            first_y = (cfg["block_top"] + cfg["block_bottom"]) / 2
        else:
            # Базовая y для первой строки, чтобы блок из `lines` строк
            # оказался отцентрирован по (block_top + block_bottom) / 2
            center_y = (cfg["block_top"] + cfg["block_bottom"]) / 2
            first_y = center_y - (lines - 1) * line_height / 2
            # Ограничиваем: первая строка не выше block_top
            first_y = max(cfg["block_top"], first_y)
            # Последняя строка не ниже block_bottom
            last_y = first_y + (lines - 1) * line_height
            if last_y > cfg["block_bottom"]:
                first_y -= (last_y - cfg["block_bottom"])

        svg = svg.replace("{{TITLE_Y}}", f"{first_y:.1f}")
        # {{TITLE_LH}} оставлен для обратной совместимости (некоторые шаблоны
        # могут его использовать; в tspan'ах dy всё равно зашит _wrap_title_to_tspans)
        svg = svg.replace("{{TITLE_LH}}", f"{line_height:.1f}")
        return svg

    # ── Детекция стиля ──────────────────────────────────────────
    def detect_style(self, book: BookInfo) -> CoverStyle:
        """
        Определить стиль по book.genre (или book.title как fallback).
        Одна точка входа — вызывается и из librarian.py.
        """
        text = (book.genre or "") + " " + (book.title or "")
        return self._detect_style_from_text(text) or CoverStyle.MINIMAL

    def _detect_style_from_text(self, text: str) -> Optional[CoverStyle]:
        """Word-boundary поиск по правилам. Регистронезависимо.
        Приватный алиас — публичная версия ниже (для backfill и CLI)."""
        return self.detect_style_from_text(text)

    def detect_style_from_text(self, text: str) -> Optional[CoverStyle]:
        """Публичный API: детекция стиля по свободному тексту (жанр/название)."""
        if not text:
            return None
        t = text.lower()
        for style, keywords in _STYLE_RULES:
            for kw in keywords:
                # Python re \b корректно работает с кириллицей с Python 3.7+
                if re.search(r"\b" + re.escape(kw), t):
                    return style
        return None

    # ── Категория-плашка ─────────────────────────────────────────
    def detect_category(self, genre: Optional[str] = None, title: Optional[str] = None) -> str:
        """Публичный API: детекция категории по genre+title (для логов/метаданных)."""
        return self._detect_category(genre or "", title or "")

    def _detect_category(self, genre: str, title: str) -> Optional[str]:
        """
        Keyword-based детекция категории-плашки.
        Сначала ищет в genre, потом в title (как fallback).
        Возвращает None если ничего не нашлось → caller подставит «Non-fiction».
        """
        for source in (genre, title):
            if not source:
                continue
            t = source.lower()
            for cat, keywords in _CATEGORY_RULES:
                for kw in keywords:
                    if re.search(r"\b" + re.escape(kw), t):
                        return cat
        return None

    # ── OG-картинка 1200×630 ────────────────────────────────────
    def generate_og(
        self,
        title: str,
        author: str,
        *,
        genre: Optional[str] = None,
        brand_name: Optional[str] = None,
        disclaimer: Optional[str] = None,
    ) -> dict:
        """
        Сгенерировать OG-картинку 1200×630 для соцсетей.

        Использует ту же палитру, что и обложка (по жанру → стилю),
        но фиксированный стиль `OG` (горизонтальный layout).

        Returns: тот же формат, что и `generate()`.
        """
        return self.generate(
            title=title,
            author=author,
            genre=genre,
            style=CoverStyle.OG,
            brand_name=brand_name,
            disclaimer=disclaimer,
        )

    # ── Сохранение в файл ───────────────────────────────────────
    def save(
        self,
        result: dict,
        folder: Union[str, Path],
        *,
        svg_name: str = "cover_local.svg",
        png_format: str = "none",  # "none" | "png" | "jpg"
        png_width: int = 1200,
        png_height: int = 1800,
    ) -> dict[str, Optional[Path]]:
        """
        Сохранить SVG (всегда) + PNG (если запрошено и cairosvg есть).

        Returns: {"svg": Path, "png": Path|None}
        """
        folder = Path(folder)
        folder.mkdir(parents=True, exist_ok=True)

        svg_path = folder / svg_name
        svg_path.write_bytes(result["svg"])
        logger.info("🎨 SVG-обложка: {}", svg_path.name)

        png_path: Optional[Path] = None
        if png_format in ("png", "jpg"):
            from agent.cover.png_export import svg_to_png
            png_path = svg_to_png(
                result["svg"],
                folder / "cover",
                width=png_width,
                height=png_height,
                output_format=png_format,
            )
            if png_path:
                logger.info("🎨 {} обложка: {}", png_format.upper(), png_path.name)
        return {"svg": svg_path, "png": png_path}

    # ── Хелперы (статические) ───────────────────────────────────
    @staticmethod
    def _escape(text: str) -> str:
        """Полный HTML/SVG escape (XML-валидный)."""
        return (
            text.replace("&", "&amp;")
                .replace("<", "&lt;")
                .replace(">", "&gt;")
                .replace('"', "&quot;")
                .replace("'", "&apos;")
        )

    @staticmethod
    def _strip(text: str) -> str:
        return (text or "").strip().replace("\n", " ").replace("\r", " ")

    @staticmethod
    def _truncate(text: str, max_len: int) -> str:
        if len(text) <= max_len:
            return text
        return text[: max_len - 1].rstrip() + "…"
