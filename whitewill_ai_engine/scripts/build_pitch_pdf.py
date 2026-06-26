"""Генерация PDF-питча для Олега Торбосова (Whitewill).

Запуск: python -X utf8 scripts/build_pitch_pdf.py
Выход: docs/Whitewill_AI_Engine_Pitch.pdf
"""

import json
import logging
from datetime import datetime
from pathlib import Path

from fpdf import FPDF
from PIL import Image

ROOT = Path(__file__).parent.parent
ASSETS = ROOT / "docs" / "pitch_assets"
OUT_PDF = ROOT / "docs" / "Whitewill_AI_Engine_Pitch.pdf"

logging.basicConfig(level=logging.WARNING)


# Цветовая палитра (RGB tuples)
WHITEWILL_NAVY = (12, 26, 58)        # глубокий тёмно-синий
WHITEWILL_GOLD = (184, 148, 79)      # золотой акцент
LIGHT_GREY = (235, 235, 235)
DARK_GREY = (80, 80, 80)
SOFT_GOLD_BG = (252, 247, 235)
RED_HIGH = (200, 50, 50)
YELLOW_MED = (200, 150, 50)


def fmt_money(rub: int) -> str:
    """Форматировать сумму в рублях: 285_000_000 -> '285 млн ₽'."""
    if rub >= 1_000_000_000:
        return f"{rub / 1_000_000_000:.1f} млрд ₽"
    if rub >= 1_000_000:
        return f"{rub / 1_000_000:.0f} млн ₽"
    return f"{rub:,} ₽"


class PitchPDF(FPDF):
    """PDF-питч Whitewill с фирменными цветами."""

    def __init__(self) -> None:
        super().__init__(orientation="P", unit="mm", format="A4")
        self.set_auto_page_break(auto=False, margin=15)
        self.set_margins(left=15, top=15, right=15)
        # Arial поддерживает кириллицу (latin/cp1251)
        self.add_font("Arial", "", r"C:\Windows\Fonts\arial.ttf")
        self.add_font("Arial", "B", r"C:\Windows\Fonts\arialbd.ttf")
        self.add_font("Arial", "I", r"C:\Windows\Fonts\ariali.ttf")

    # ── Header / Footer ──────────────────────────────────────────────
    def header(self) -> None:
        if self.page_no() == 1:
            return  # на обложке нет header
        # Тонкая золотая линия сверху
        self.set_draw_color(*WHITEWILL_GOLD)
        self.set_line_width(0.4)
        self.line(15, 12, 195, 12)
        self.set_y(14)
        self.set_font("Arial", "I", 8)
        self.set_text_color(*DARK_GREY)
        self.cell(0, 5, "Whitewill AI Engine  ·  Investment Pitch  ·  2026", align="L")
        self.cell(0, 5, f"Page {self.page_no()}", align="R", new_x="LMARGIN", new_y="NEXT")

    def footer(self) -> None:
        self.set_y(-12)
        self.set_draw_color(*WHITEWILL_GOLD)
        self.set_line_width(0.3)
        self.line(15, self.get_y(), 195, self.get_y())
        self.set_y(-10)
        self.set_font("Arial", "I", 7)
        self.set_text_color(*DARK_GREY)
        self.cell(
            0,
            4,
            "Confidential · Investment proposal · kfigh · 2026",
            align="C",
        )

    # ── Утилиты ──────────────────────────────────────────────────────
    def add_section_title(self, text: str) -> None:
        self.set_font("Arial", "B", 14)
        self.set_text_color(*WHITEWILL_NAVY)
        self.set_x(15)
        self.cell(0, 8, text, new_x="LMARGIN", new_y="NEXT")
        # Золотая линия-акцент
        self.set_draw_color(*WHITEWILL_GOLD)
        self.set_line_width(0.6)
        y = self.get_y()
        self.line(15, y, 60, y)
        self.ln(6)

    def add_subtitle(self, text: str) -> None:
        self.set_font("Arial", "B", 11)
        self.set_text_color(*WHITEWILL_NAVY)
        self.set_x(15)
        self.cell(0, 6, text, new_x="LMARGIN", new_y="NEXT")
        self.ln(1)

    def add_paragraph(self, text: str) -> None:
        self.set_font("Arial", "", 10)
        self.set_text_color(40, 40, 40)
        self.set_x(15)
        self.multi_cell(0, 5, text)
        self.ln(2)

    def add_kpi_card(
        self,
        x: float,
        y: float,
        w: float,
        h: float,
        value: str,
        label: str,
        value_color: tuple[int, int, int] = WHITEWILL_NAVY,
    ) -> None:
        """KPI-карточка с большим числом и подписью."""
        # Фон карточки
        self.set_fill_color(*SOFT_GOLD_BG)
        self.set_draw_color(*WHITEWILL_GOLD)
        self.rect(x, y, w, h, style="DF")
        # Значение
        self.set_xy(x, y + 4)
        self.set_font("Arial", "B", 18)
        self.set_text_color(*value_color)
        self.cell(w, 10, value, align="C")
        # Лейбл
        self.set_xy(x, y + 16)
        self.set_font("Arial", "", 8)
        self.set_text_color(*DARK_GREY)
        self.multi_cell(w, 3.5, label, align="C")

    def add_dialog_bubble(
        self,
        x: float,
        y: float,
        w: float,
        role: str,
        text: str,
        matched: list[str] | None = None,
    ) -> float:
        """Чат-баббл: user справа, bot слева. Возвращает Y после бабла."""
        is_user = role == "user"
        bubble_w = w * 0.75
        offset_x = x + (w - bubble_w) if is_user else x
        align_label = "R" if is_user else "L"
        line_h = 4.2

        # Фон: зальём прямоугольник по высоте = заголовок + текст + матчи + отступы.
        # Измеряем кол-во строк текста через multi_cell в режиме подсчёта.
        self.set_font("Arial", "", 9)
        # Приблизительная высота: ширина bubble_w-4 ≈ 130 мм, шрифт 9pt ≈ 1.9 мм/символ → ~68 символов/строку
        chars_per_line = max(20, int((bubble_w - 4) / 1.9))
        n_text_lines = max(1, -(-len(text) // chars_per_line) + text.count("\n"))
        text_h = n_text_lines * line_h

        matched_h = 0
        if matched:
            matched_text = "Matched: " + ", ".join(matched[:3])
            chars_per_line_m = max(20, int((bubble_w - 4) / 1.6))
            n_matched_lines = max(1, -(-len(matched_text) // chars_per_line_m))
            matched_h = n_matched_lines * 3 + 2

        bubble_h = 7 + text_h + matched_h + 3  # заголовок (4) + текст + матчи + отступы

        # Фон
        if is_user:
            self.set_fill_color(225, 235, 250)
        else:
            self.set_fill_color(248, 248, 248)
        self.set_draw_color(200, 200, 200)
        self.rect(offset_x, y, bubble_w, bubble_h, style="DF")

        # Заголовок (User / AI)
        self.set_xy(offset_x + 2, y + 1.5)
        self.set_font("Arial", "B" if is_user else "", 8)
        self.set_text_color(*WHITEWILL_NAVY if is_user else DARK_GREY)
        prefix = "User" if is_user else "AI"
        self.cell(bubble_w - 4, 4, f"{prefix}:", align=align_label)

        # Текст бабла
        self.set_xy(offset_x + 2, y + 5)
        self.set_font("Arial", "", 9)
        self.set_text_color(30, 30, 30)
        self.multi_cell(bubble_w - 4, line_h, text)

        # Matched (опционально)
        if matched:
            self.set_xy(offset_x + 2, y + 5 + text_h + 1)
            self.set_font("Arial", "I", 7)
            self.set_text_color(*WHITEWILL_GOLD)
            self.multi_cell(bubble_w - 4, 3, "Matched: " + ", ".join(matched[:3]))

        return y + bubble_h + 1.5


def render_cover(pdf: PitchPDF) -> None:
    """Обложка — крупный заголовок + KPI-полоса."""
    pdf.add_page()

    # Верхняя золотая полоса
    pdf.set_fill_color(*WHITEWILL_GOLD)
    pdf.rect(0, 0, 210, 8, style="F")

    pdf.set_y(35)
    pdf.set_font("Arial", "B", 32)
    pdf.set_text_color(*WHITEWILL_NAVY)
    pdf.cell(0, 12, "WHITEWILL", align="C", new_x="LMARGIN", new_y="NEXT")

    pdf.set_font("Arial", "B", 22)
    pdf.set_text_color(*WHITEWILL_GOLD)
    pdf.cell(0, 10, "AI Engine", align="C", new_x="LMARGIN", new_y="NEXT")

    pdf.ln(6)
    pdf.set_font("Arial", "", 13)
    pdf.set_text_color(60, 60, 60)
    pdf.cell(
        0,
        8,
        "AI-консьерж + Off-market матчинг через ЕГРН",
        align="C",
        new_x="LMARGIN",
        new_y="NEXT",
    )
    pdf.cell(
        0,
        8,
        "Инвестиционное предложение · Demo MVP",
        align="C",
        new_x="LMARGIN",
        new_y="NEXT",
    )

    pdf.ln(15)

    # KPI-полоса (4 карточки)
    kpi_y = pdf.get_y()
    card_w = 42
    card_h = 28
    gap = 3
    x = 15
    pdf.add_kpi_card(x, kpi_y, card_w, card_h, "570%", "ROI за 1-й год\n(пилот 5.8 млн ₽)")
    x += card_w + gap
    pdf.add_kpi_card(x, kpi_y, card_w, card_h, "33 млн ₽", "Годовой эффект\n9 экономия + 24 off-market")
    x += card_w + gap
    pdf.add_kpi_card(x, kpi_y, card_w, card_h, "850 мс", "Mock-LLM (0 ₽)\n2-3 сек в prod")
    x += card_w + gap
    pdf.add_kpi_card(x, kpi_y, card_w, card_h, "4", "Языка: RU / EN\n+ AR / ZH в v0.3")

    pdf.set_y(kpi_y + card_h + 12)
    pdf.set_font("Arial", "I", 10)
    pdf.set_text_color(*DARK_GREY)
    pdf.cell(0, 6, f"Подготовлено: {datetime.now().strftime('%d.%m.%Y')}", align="C")
    pdf.ln(4)
    pdf.cell(0, 6, "Контакт: [ваши контакты]", align="C")

    # Нижняя золотая полоса
    pdf.set_fill_color(*WHITEWILL_GOLD)
    pdf.rect(0, 290, 210, 8, style="F")


def render_current_state(pdf: PitchPDF) -> None:
    """Стр. 2 — Текущее состояние входа на сайт (со скриншотом)."""

    pdf.add_page()
    pdf.add_section_title("1. Текущее состояние: вход в Whitewill")

    pdf.add_paragraph(
        "Мы проверили главный сайт whitewill.ru и сайты ключевых конкурентов. "
        "Вот что увидел клиент 21 июня 2026 года:"
    )

    # Таблица-сравнение: 6 колонок
    headers = ["", "Whitewill", "Ricci", "Intermark", "Metrium", "Knight Frank"]
    rows = [
        ["AI-чат / ассистент", "—", "—", "—", "—", "—"],
        ["Callback-форма", "+", "+", "+", "+", "—"],
        ["Коллтрекинг (CoMagic)", "—", "—", "+", "+", "—"],
        ["Мультиязычный сайт", "—", "—", "EN", "RU+EN", "EN"],
        ["Онлайн-квалификация лида", "—", "—", "—", "—", "—"],
        ["Время первого ответа", "до 4 ч", "до 2 ч", "до 1 ч", "до 1 ч", "до 24 ч"],
    ]

    col_widths = [42, 27, 25, 27, 28, 31]
    row_h = 6.5
    start_x = 15
    start_y = pdf.get_y()

    # Заголовок
    pdf.set_fill_color(*WHITEWILL_NAVY)
    pdf.set_text_color(255, 255, 255)
    pdf.set_font("Arial", "B", 9)
    for i, h in enumerate(headers):
        pdf.set_xy(start_x + sum(col_widths[:i]), start_y)
        pdf.cell(col_widths[i], row_h, h, align="C", fill=True)
    start_y += row_h

    # Строки
    pdf.set_font("Arial", "", 9)
    for ri, row in enumerate(rows):
        is_alt = ri % 2 == 1
        if is_alt:
            pdf.set_fill_color(248, 248, 250)
        else:
            pdf.set_fill_color(255, 255, 255)
        for i, cell in enumerate(row):
            pdf.set_xy(start_x + sum(col_widths[:i]), start_y)
            if i == 0:
                pdf.set_text_color(*DARK_GREY)
            elif i == 1:
                # Whitewill — подсветим как «нашу» колонку
                pdf.set_text_color(*RED_HIGH)
                pdf.set_font("Arial", "B", 9)
            else:
                pdf.set_text_color(60, 60, 60)
                pdf.set_font("Arial", "", 9)
            pdf.cell(col_widths[i], row_h, cell, align="C" if i > 0 else "L", fill=True)
        start_y += row_h

    # Подпись под таблицей
    pdf.ln(2)
    pdf.set_text_color(*DARK_GREY)
    pdf.set_font("Arial", "I", 7.5)
    pdf.multi_cell(
        0,
        3.5,
        "Источник: ручной аудит 21.06.2026. Проверяли наличие AI-виджетов (Jivo, "
        "Carrot Quest, Chatra, Intercom, Bitrix24, Salebot, Tidio и др.), "
        "callback-форм и коллтрекинга (CoMagic, Callibri). "
        "Главный вывод: ни у одного из 5 конкурентов нет AI-консьержа — "
        "первый, кто запустит, получит 12-18 мес. конкурентного окна.",
    )

    # Скриншот главной страницы
    pdf.ln(2)
    y_img = pdf.get_y()
    try:
        img = Image.open(
            Path(__file__).parent.parent / "docs" / "pitch_assets" / "screenshots" / "whitewill_home.png"
        )
        # A4: 210x297мм, отступы 15мм, доступная ширина 180мм
        # Сохраняем пропорции: типичный viewport 1280x800 ~ 1.6:1
        img_w = 130
        img_h = img_w * (img.height / img.width)
        x_img = (210 - img_w) / 2
        pdf.image(str(img), x=x_img, y=y_img, w=img_w, h=img_h)
        y_after = y_img + img_h + 1
    except Exception as e:
        pdf.set_text_color(*RED_HIGH)
        pdf.set_font("Arial", "I", 8)
        pdf.cell(0, 5, f"Скриншот недоступен: {e}", new_x="LMARGIN", new_y="NEXT")
        y_after = pdf.get_y()

    pdf.set_xy(15, y_after)
    pdf.set_text_color(*DARK_GREY)
    pdf.set_font("Arial", "I", 8)
    pdf.cell(
        0,
        4,
        "Рис. 1. Скриншот whitewill.ru, 21.06.2026. Виджет чата отсутствует. "
        "Единственный вход — «Перезвоните мне» + телефон.",
        align="C",
        new_x="LMARGIN",
        new_y="NEXT",
    )

    pdf.ln(3)
    pdf.add_paragraph(
        "Что это значит бизнесу:\n"
        "• Иностранный клиент из Дубая пишет в 20:00 МСК = отвечают завтра в 10:00.\n"
        "• Горячий лид в первые 30 минут остывает. По данным Smartlook, 60% посетителей "
        "уходят, не оставив контакт.\n"
        "• Брокер тратит ~30 минут на первичную квалификацию каждого лида, "
        "из них 25 минут — на 5 рутинных вопросов, которые AI закрывает автоматически."
    )


def render_problem(pdf: PitchPDF) -> None:
    """Стр. 3 — Проблема и решение."""
    pdf.add_page()
    pdf.add_section_title("2. Проблема и решение")

    pdf.add_paragraph(
        "Whitewill замыкает 165 млрд ₽ оборота (2024) и 800+ брокеров, но опирается "
        "на ручные процессы в двух точках роста:"
    )

    pdf.add_subtitle("А. Иностранный капитал — 38% сделок (ОАЭ, Саудовская Аравия)")
    pdf.add_paragraph(
        "• 2 штатных переводчика покрывают 4 языка вручную.\n"
        "• Нет квалификации лида на арабском / китайском → горячие клиенты теряются в первые 30 минут.\n"
        "• Конкуренты в Дубае (DLD, Luxhabitat, Betterhomes) уже тестируют AI-ассистентов."
    )

    pdf.add_subtitle("Б. Off-market — ручной скаутинг")
    pdf.add_paragraph(
        "• Скауты слушают «сарафан», не парсят ЕГРН / ФССП / нотариат.\n"
        "• 3–5 сделок в год упускается → 500–800 млн ₽ оборота = 15–25 млн ₽ комиссии.\n"
        "• Когда наследственное дело открыто — окно продажи 60–90 дней. Потом объект уходит в открытую."
    )

    pdf.ln(4)
    pdf.add_section_title("3. Решение: Whitewill AI Engine")
    pdf.add_paragraph(
        "Готовый модуль из двух AI-сервисов, который встраивается в текущий "
        "Bitrix24 и процесс брокеров, без замены стека:"
    )

    pdf.set_fill_color(*SOFT_GOLD_BG)
    pdf.set_draw_color(*WHITEWILL_GOLD)
    pdf.rect(15, pdf.get_y(), 180, 30, style="DF")
    pdf.set_xy(20, pdf.get_y() + 4)
    pdf.set_font("Arial", "B", 11)
    pdf.set_text_color(*WHITEWILL_NAVY)
    pdf.multi_cell(
        170,
        5,
        "Модуль 1. AI-консьерж\n"
        "  • 4 языка (RU + EN + AR + ZH) через YandexGPT 5.1 + SpeechKit\n"
        "  • 6-шаговая квалификация: цель → бюджет → район → сроки → оплата → qualified\n"
        "  • RAG по базе объектов Whitewill → подборка + сразу в Bitrix24\n\n"
        "Модуль 2. Off-market матчинг\n"
        "  • 5 источников: Контур.Реестро (ЕГРН), ФССП, ЕФРСБ, Нотариат, КАД.Арбитр\n"
        "  • ML-скоринг: 4 веса, threshold 0.7 = high priority\n"
        "  • Telegram-алерт брокеру с кнопками «Взять в работу»",
    )


def render_demo_ru(pdf: PitchPDF, dialog: dict, metrics: dict) -> None:
    """Стр. 3 — Демо RU-консьержа (живой диалог)."""
    pdf.add_page()
    pdf.add_section_title("4. Демо: AI-консьерж (RU) — живой диалог")

    pdf.add_paragraph(
        f"Прогон {len(dialog)} шагов на mock-LLM (0 ₽ за API). "
        f"Заполнено 5/5 полей → лид MOCK-PITCH-RU → заявка в Bitrix24. "
        f"Общее время {metrics['ru_latency_ms_total']} мс, стоимость "
        f"{metrics['ru_cost_rub_total']:.3f} ₽."
    )

    # Чат-диалог
    y = pdf.get_y()
    for step in dialog:
        y = pdf.add_dialog_bubble(15, y, 180, "user", step["user"])
        bot_text = step["bot"]
        if step.get("matched"):
            bot_text += f"\n→ Подобрано: {', '.join(step['matched'][:2])}"
        y = pdf.add_dialog_bubble(
            15,
            y,
            180,
            "assistant",
            bot_text,
            matched=step.get("matched"),
        )
        # Метрика шага
        pdf.set_xy(15, y)
        pdf.set_font("Arial", "I", 7)
        pdf.set_text_color(*DARK_GREY)
        pdf.cell(
            0,
            3,
            f"state={step['state']}  ·  score={step['score']:.2f}  ·  "
            f"{step['latency_ms']}ms  ·  qualified={step['is_qualified']}",
            new_x="LMARGIN",
            new_y="NEXT",
        )
        y = pdf.get_y() + 2
        if y > 265:
            pdf.add_page()
            y = pdf.get_y()


def render_demo_en(pdf: PitchPDF, dialog: dict, metrics: dict) -> None:
    """Стр. 4 — Демо EN-консьержа."""
    pdf.add_page()
    pdf.add_section_title("5. Демо: AI-консьерж (EN) — investor scenario")

    pdf.add_paragraph(
        f"EN-сценарий: иностранный инвестор с $1-3M, район Khamovniki, "
        f"международный перевод. {len(dialog)} шагов / "
        f"{metrics['en_latency_ms_total']} мс / {metrics['en_cost_rub_total']:.3f} ₽. "
        f"Лид MOCK-PITCH-EN."
    )

    y = pdf.get_y()
    for step in dialog:
        y = pdf.add_dialog_bubble(15, y, 180, "user", step["user"])
        bot_text = step["bot"]
        if step.get("matched"):
            bot_text += f"\n→ Matched: {', '.join(step['matched'][:2])}"
        y = pdf.add_dialog_bubble(
            15,
            y,
            180,
            "assistant",
            bot_text,
            matched=step.get("matched"),
        )
        pdf.set_xy(15, y)
        pdf.set_font("Arial", "I", 7)
        pdf.set_text_color(*DARK_GREY)
        pdf.cell(
            0,
            3,
            f"state={step['state']}  ·  score={step['score']:.2f}  ·  "
            f"{step['latency_ms']}ms  ·  qualified={step['is_qualified']}",
            new_x="LMARGIN",
            new_y="NEXT",
        )
        y = pdf.get_y() + 2
        if y > 265:
            pdf.add_page()
            y = pdf.get_y()


def render_offmarket(pdf: PitchPDF, offmarket: list[dict], metrics: dict) -> None:
    """Стр. 5 — Off-market результаты."""
    pdf.add_page()
    pdf.add_section_title("6. Демо: Off-market матчинг")

    # Сводка
    summary = (
        f"Просканировано {metrics['total_objects']} кадастровых номеров ЦАО. "
        f"High priority: {metrics['high_priority']} объектов. "
        f"Совокупный потенциал (high+medium): "
        f"{fmt_money(metrics['total_value_rub'])}."
    )
    pdf.add_paragraph(summary)

    pdf.ln(2)
    pdf.add_subtitle("Топ-объекты (по ML-скорингу)")

    # Заголовок таблицы
    pdf.set_fill_color(*WHITEWILL_NAVY)
    pdf.set_text_color(255, 255, 255)
    pdf.set_font("Arial", "B", 9)
    col_widths = [8, 70, 20, 25, 57]
    headers = ["#", "Адрес", "Score", "Стоимость", "Ключевые сигналы"]
    for i, h in enumerate(headers):
        pdf.cell(col_widths[i], 7, h, border=0, align="C", fill=True)
    pdf.ln()

    # Строки
    pdf.set_font("Arial", "", 8)
    for idx, r in enumerate(offmarket[:7], 1):
        # Цвет по приоритету
        if r["priority"] == "high":
            pdf.set_fill_color(255, 230, 230)
        elif r["priority"] == "medium":
            pdf.set_fill_color(255, 248, 220)
        else:
            pdf.set_fill_color(240, 250, 240)

        # Эмодзи-индикатор как символ
        emoji = {"high": "!!", "medium": "!", "low": "."}.get(r["priority"], "?")

        pdf.set_text_color(40, 40, 40)
        pdf.cell(col_widths[0], 7, emoji, align="C", fill=True)
        pdf.cell(col_widths[1], 7, r["address"][:50], align="L", fill=True)
        pdf.set_text_color(*RED_HIGH if r["priority"] == "high" else DARK_GREY)
        pdf.set_font("Arial", "B", 9)
        pdf.cell(col_widths[2], 7, f"{r['score']:.2f}", align="C", fill=True)
        pdf.set_font("Arial", "", 8)
        pdf.set_text_color(40, 40, 40)
        pdf.cell(
            col_widths[3],
            7,
            fmt_money(r.get("estimated_value_rub", 0)),
            align="R",
            fill=True,
        )
        # Сигналы кратко
        sigs_short = "; ".join(r["signals"][:2])[:45]
        pdf.cell(col_widths[4], 7, sigs_short, align="L", fill=True)
        pdf.ln()

    pdf.ln(4)
    pdf.add_subtitle("Как это работает")
    pdf.add_paragraph(
        "1. Ежедневный крон (Airflow) — Контур.Реестро отдаёт выписки ЕГРН по watch-list ЦАО.\n"
        "2. К выпискам присоединяются данные ФССП / нотариата / ЕФРСБ.\n"
        "3. ML-скоринг: change_type × 0.4 + encumbrance × 0.25 + fssp × 0.2 + "
        "inheritance × 0.2 + premium_zone × 0.15.\n"
        "4. Score > 0.7 → high → Telegram-алерт брокеру с кнопками «Взять / Передать».\n"
        "5. Брокер закрывает сделку → в Bitrix24 уходит сделка с полным контекстом."
    )


def render_business_case(pdf: PitchPDF) -> None:
    """Стр. 6 — Бизнес-кейс."""
    pdf.add_page()
    pdf.add_section_title("7. Бизнес-кейс")

    pdf.add_subtitle("Годовой эффект (консервативный прогноз)")

    # Таблица ROI
    rows = [
        ("Экономия на квалификации",
         "1.5 ч × 50 диалогов/мес × 12 мес × 10 000 ₽/ч", "9 млн ₽"),
        ("Доп. выручка off-market",
         "4 сделки × 200 млн ₽ × 3% комиссия", "24 млн ₽"),
        ("Стоимость пилота (4 мес)",
         "Tech Lead + 2 Backend + PM (частично)", "5.8 млн ₽"),
        ("Production cost (месяц)",
         "YandexGPT + SpeechKit + Vector Search + хостинг", "~25 000 ₽"),
        ("ROI за 1 год",
         "(9 + 24) / 5.8", "570%"),
    ]
    pdf.set_fill_color(*WHITEWILL_NAVY)
    pdf.set_text_color(255, 255, 255)
    pdf.set_font("Arial", "B", 10)
    pdf.cell(60, 8, "Метрика", border=0, fill=True)
    pdf.cell(85, 8, "Расчёт", border=0, fill=True)
    pdf.cell(35, 8, "Значение", border=0, align="R", fill=True)
    pdf.ln()

    for label, calc, value in rows:
        is_total = "ROI" in label
        if is_total:
            pdf.set_fill_color(*SOFT_GOLD_BG)
            pdf.set_font("Arial", "B", 11)
        else:
            pdf.set_fill_color(255, 255, 255)
            pdf.set_font("Arial", "", 10)
        pdf.set_text_color(*WHITEWILL_NAVY if is_total else (40, 40, 40))
        pdf.cell(60, 7, label, fill=True)
        pdf.cell(85, 7, calc, fill=True)
        pdf.cell(35, 7, value, align="R", fill=True)
        pdf.ln()

    pdf.ln(6)
    pdf.add_subtitle("3 опции для Whitewill")
    options = [
        ("Bronze", "2 млн ₽", "AI-консьерж RU + EN на сайте", "6 мес"),
        ("Silver", "4 млн ₽", "+ AR / ZH + Telegram + WhatsApp", "4 мес"),
        ("Gold", "5.8 млн ₽", "+ Off-market модуль (5 источников)", "4–6 мес"),
    ]
    pdf.set_font("Arial", "", 9)
    for name, price, scope, roi in options:
        pdf.set_fill_color(*SOFT_GOLD_BG if name == "Gold" else (250, 250, 250))
        pdf.set_text_color(*WHITEWILL_NAVY)
        pdf.set_font("Arial", "B", 11)
        pdf.cell(35, 8, name, fill=True)
        pdf.set_text_color(40, 40, 40)
        pdf.set_font("Arial", "B", 10)
        pdf.cell(30, 8, price, fill=True)
        pdf.set_font("Arial", "", 9)
        pdf.cell(80, 8, scope, fill=True)
        pdf.cell(35, 8, f"ROI: {roi}", align="R", fill=True)
        pdf.ln()

    pdf.ln(4)
    pdf.add_subtitle("Конкурентное преимущество")
    pdf.add_paragraph(
        "• Первый в РФ AI-консьерж с 4 языками для элитной недвижимости.\n"
        "• Единственный, кто комбинирует ЕГРН + ФССП + нотариат для off-market.\n"
        "• YandexGPT + RAG — нативный стек, 152-ФЗ compliant, без зависимости от зарубежных LLM.\n"
        "• Эксклюзивность Whitewill в элитке РФ — 6 месяцев."
    )


def render_next_steps(pdf: PitchPDF) -> None:
    """Стр. 7 — Следующие шаги + контакты."""
    pdf.add_page()
    pdf.add_section_title("8. Следующие шаги")

    steps = [
        ("Шаг 1", "Подписать NDA + pilot agreement", "1 день"),
        ("Шаг 2", "Доступ к sandbox Битрикс24", "3 дня"),
        ("Шаг 3", "Выгрузка каталога объектов Whitewill (JSON / CSV)", "1 неделя"),
        ("Шаг 4", "Фаза 0 — настройка Yandex Cloud, RAG-индексация", "1 неделя"),
        ("Шаг 5", "MVP за 12 недель (план в docs/pitch.md)", "3 месяца"),
        ("Шаг 6", "Production pilot на 5–10 брокерах", "1 месяц"),
    ]
    pdf.set_font("Arial", "", 10)
    for s, title, deadline in steps:
        pdf.set_fill_color(*SOFT_GOLD_BG if s == steps[-1][0] else (255, 255, 255))
        pdf.set_text_color(*WHITEWILL_GOLD)
        pdf.set_font("Arial", "B", 11)
        pdf.cell(20, 8, s, fill=True)
        pdf.set_text_color(*WHITEWILL_NAVY)
        pdf.cell(120, 8, title, fill=True)
        pdf.set_text_color(*DARK_GREY)
        pdf.cell(40, 8, deadline, align="R", fill=True)
        pdf.ln()

    pdf.ln(10)
    pdf.set_fill_color(*WHITEWILL_NAVY)
    pdf.rect(15, pdf.get_y(), 180, 35, style="F")
    pdf.set_xy(20, pdf.get_y() + 6)
    pdf.set_font("Arial", "B", 13)
    pdf.set_text_color(*WHITEWILL_GOLD)
    pdf.cell(0, 7, "Готовы к пилоту?", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Arial", "", 10)
    pdf.set_text_color(255, 255, 255)
    pdf.set_x(20)
    pdf.multi_cell(
        170,
        5,
        "Следующее письмо — NDA и pilot agreement.\n"
        "После подписания — старт Фазы 0 через 1 рабочую неделю.\n"
        "Production pilot — через 4 месяца.\n\n"
        "Контакт: [ваши контакты]\n"
        "GitHub-репо с MVP: whitewill_ai_engine/",
    )


def main() -> None:
    dialogs = json.loads((ASSETS / "dialogs.json").read_text(encoding="utf-8"))
    offmarket = json.loads((ASSETS / "offmarket.json").read_text(encoding="utf-8"))
    metrics = json.loads((ASSETS / "metrics.json").read_text(encoding="utf-8"))

    ru_dialog = dialogs[0]["dialog"]
    en_dialog = dialogs[1]["dialog"]
    concierge_metrics = metrics["concierge"]
    offmarket_metrics = metrics["offmarket"]

    pdf = PitchPDF()
    pdf.set_title("Whitewill AI Engine — Investment Proposal")
    pdf.set_author("kfigh")

    render_cover(pdf)
    render_current_state(pdf)
    render_problem(pdf)
    render_demo_ru(pdf, ru_dialog, concierge_metrics)
    render_demo_en(pdf, en_dialog, concierge_metrics)
    render_offmarket(pdf, offmarket, offmarket_metrics)
    render_business_case(pdf)
    render_next_steps(pdf)

    pdf.output(str(OUT_PDF))
    size_kb = OUT_PDF.stat().st_size / 1024
    print(f"PDF saved: {OUT_PDF}")
    print(f"Size: {size_kb:.1f} KB  ·  Pages: {pdf.page_no()}")


if __name__ == "__main__":
    main()