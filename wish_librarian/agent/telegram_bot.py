"""
Telegram-бот для WishLibrarian.

Команды:
  /start, /help    — справка
  /add <URL>       — добавить книгу в обработку
  /status          — что в процессе
  /list [N]        — последние N обработанных книг
  /search <запрос> — поиск по библиотеке
  /book <название> — открыть summary.md
  /export <fmt>    — экспортировать книгу (txt/html)
  /doctor          — диагностика
  /cancel          — отменить текущую задачу

Запуск:
    export TELEGRAM_BOT_TOKEN=123:abc
    python -m agent.telegram_bot
"""
from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path
from typing import Optional

# Windows: переключаем stdout на UTF-8, чтобы эмодзи в print() не падали
try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

# Загружаем .env ДО первого чтения env-переменных, чтобы TELEGRAM_BOT_TOKEN
# из .env был виден через os.environ.get()
try:
    from dotenv import load_dotenv
    _PROJECT_ROOT = Path(__file__).resolve().parent.parent
    load_dotenv(_PROJECT_ROOT / ".env", override=False)
except ImportError:
    pass  # python-dotenv не установлен — пользователь сам экспортирует

from aiogram import Bot, Dispatcher, F
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import Command
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)
from aiogram.exceptions import TelegramNetworkError, TelegramRetryAfter
try:
    from aiohttp import ClientError as AiohttpClientError
except ImportError:  # pragma: no cover
    AiohttpClientError = Exception

from agent.config import get_settings
from agent.librarian import WishLibrarian
from agent.utils.logger import get_logger, setup_logging
from agent.export import export_book
from agent.detector import (
    QUESTIONS as DETECTOR_QUESTIONS,
    DetectorSession,
    format_intro as detector_format_intro,
    format_question as detector_format_question,
    format_result as detector_format_result,
)


logger = get_logger()


# ── Хранилище состояния чата ────────────────────────────────────────
# key = chat_id, value = dict(processing: bool, current_url: str, librarian: WL, detector: DetectorSession)
_chat_state: dict[int, dict] = {}


def _get_librarian(chat_id: int) -> WishLibrarian:
    if chat_id not in _chat_state:
        _chat_state[chat_id] = {
            "processing": False,
            "current_url": None,
            "librarian": WishLibrarian(),
            "detector": None,  # DetectorSession | None
        }
    return _chat_state[chat_id]["librarian"]


def _get_detector(chat_id: int) -> DetectorSession:
    """Создаёт или возвращает сессию детектора для чата."""
    if chat_id not in _chat_state:
        _chat_state[chat_id] = {
            "processing": False,
            "current_url": None,
            "librarian": WishLibrarian(),
            "detector": None,
        }
    if _chat_state[chat_id]["detector"] is None:
        _chat_state[chat_id]["detector"] = DetectorSession(user_id=chat_id)
    return _chat_state[chat_id]["detector"]


def _reset_detector(chat_id: int) -> None:
    if chat_id in _chat_state:
        _chat_state[chat_id]["detector"] = None


# ── Форматирование длинных сообщений ────────────────────────────────
def _split_message(text: str, max_len: int = 4000) -> list[str]:
    if len(text) <= max_len:
        return [text]
    chunks = []
    while text:
        if len(text) <= max_len:
            chunks.append(text)
            break
        # Режем по переводу строки
        cut = text.rfind("\n", 0, max_len)
        if cut == -1:
            cut = max_len
        chunks.append(text[:cut])
        text = text[cut:].lstrip("\n")
    return chunks


# ── Обработка одной книги ───────────────────────────────────────────
async def _process_url(chat_id: int, url: str, message: Message) -> None:
    state = _chat_state.setdefault(chat_id, {})
    state["processing"] = True
    state["current_url"] = url
    librarian: WishLibrarian = state.get("librarian") or _get_librarian(chat_id)

    status_msg = await message.answer(f"⏳ Обрабатываю:\n{url}")

    try:
        # Запускаем в executor, чтобы не блокировать event loop
        loop = asyncio.get_event_loop()
        # Если юзер выбрал шаблон через /template — применяем его
        result = await loop.run_in_executor(
            None,
            lambda: librarian.process_book(
                url,
                force=False, parse_only=False,
                template=state.get("template"),
                template_summary=state.get("template_summary"),
                template_workbook=state.get("template_workbook"),
            ),
        )
        book = result.book
        if result.errors:
            err = result.errors[0][:500]
            await status_msg.edit_text(
                f"❌ <b>Ошибка</b>\n\n"
                f"Книга: <i>{book.title or '—'}</i>\n"
                f"Ошибка: <code>{err}</code>",
                parse_mode=ParseMode.HTML,
            )
            return

        # Успех
        from agent.config import get_settings as _gs
        out = _gs().output_dir
        folder_name = Path(result.folder).name if result.folder else "—"
        text = (
            f"✅ <b>Готово!</b>\n\n"
            f"📖 <b>{book.title}</b>\n"
            f"✍️ {book.author}\n"
            f"📅 {book.year or '—'}\n"
            f"📁 <code>{folder_name}</code>\n\n"
            f"🤖 AI: {result.metadata_path and 'см. metadata.json'}\n"
            f"🖼 Обложка: {'✅' if result.cover_path else '—'}\n"
            f"📝 Summary: {'✅' if result.summary_path else '—'}\n"
            f"✍️  Workbook: {'✅' if result.workbook_path else '—'}\n"
            f"💡 Tips: {'✅' if result.tips_path else '—'}\n"
            f"💬 Reviews: {'✅' if result.reviews_path else '—'}\n"
            f"🔬 Science: {'✅' if result.scientific_path else '—'}\n"
        )
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="📝 Summary", callback_data=f"book:summary:{folder_name}"),
                InlineKeyboardButton(text="✍️ Workbook", callback_data=f"book:workbook:{folder_name}"),
            ],
            [
                InlineKeyboardButton(text="💡 Tips", callback_data=f"book:tips:{folder_name}"),
                InlineKeyboardButton(text="📄 Всё в .txt", callback_data=f"export:txt:{folder_name}"),
            ],
        ])
        await status_msg.edit_text(text, parse_mode=ParseMode.HTML, reply_markup=kb)
    except Exception as e:
        logger.exception("Ошибка обработки {}: {}", url, e)
        await status_msg.edit_text(f"💥 <b>Ошибка:</b> <code>{e}</code>", parse_mode=ParseMode.HTML)
    finally:
        state["processing"] = False
        state["current_url"] = None


# ── Хендлеры команд ─────────────────────────────────────────────────
async def cmd_start(message: Message) -> None:
    """Приветствие зависит от роли бота (определяется через sys.argv --role=)."""
    role = _parse_role()
    if role == "detector":
        # Разбираем deep-link: /start, /start site, /start site_result
        text = (message.text or "").strip()
        payload = ""
        if text.startswith("/start"):
            payload = text[len("/start"):].strip()

        if payload == "site":
            # Пользователь пришёл с интро /detector/ — уже видел CTA
            await message.answer(
                "🔍 <b>Детектор желаний в Telegram</b>\n\n"
                "Ты только что был на сайте — теперь пройди тест здесь, "
                "в один клик.\n\n"
                "5 вопросов · 2 минуты · мгновенный результат.\n\n"
                "💎 <i>Полный разбор (20 вопросов) + AI-коуч — "
                "<a href=\"https://app.pulab.ru/pricing/\">премиум</a></i>",
                parse_mode=ParseMode.HTML,
                reply_markup=_detector_intro_kb(),
            )
        elif payload == "site_result":
            # Пользователь пришёл после прохождения теста на сайте
            await message.answer(
                "🔍 <b>Сохрани результат и продолжай</b>\n\n"
                "Твой результат уже на сайте. Здесь ты можешь:\n"
                "• пройти тест <b>ещё раз</b> с другим желанием\n"
                "• получить <b>полный разбор</b> 20 вопросов\n"
                "• <b>сохранить</b> историю результатов\n\n"
                "<b>Команды:</b>\n"
                "/detector — пройти / повторить\n"
                "/help — помощь\n\n"
                "💎 <i>Подписка WishCoach — "
                "<a href=\"https://app.pulab.ru/pricing/\">премиум</a></i>",
                parse_mode=ParseMode.HTML,
                reply_markup=_detector_intro_kb(),
            )
        else:
            # Обычный /start — без источника
            await message.answer(
                "🔍 <b>Лаборатория желаний — мини-детектор</b>\n\n"
                "Помогаю отличить <b>твои истинные желания</b> от <b>навязанных</b> "
                "(чужих «надо», стыда, страхов).\n\n"
                "За 1 минуту ты получишь:\n"
                "• 5 коротких вопросов\n"
                "• результат: «у тебя X% навязанных желаний»\n"
                "• 3 персональных совета\n\n"
                "<b>Команды:</b>\n"
                "/detector — пройти тест\n"
                "/help — помощь\n\n"
                "💎 <i>Полный разбор от AI-коуча + библиотекарь — "
                "<a href=\"https://app.pulab.ru/pricing/\">премиум</a></i>",
                parse_mode=ParseMode.HTML,
                reply_markup=_detector_intro_kb(),
            )
    else:
        await message.answer(
            "📚 <b>WishLibrarian Bot</b>\n\n"
            "Я обрабатываю книги с koob.ru, LiveLib, Лабиринта, Литрес и др.\n"
            "Скиньте URL — я сделаю конспект, воркбук и подберу отзывы.\n"
            "Или пришлите файл .txt/.fb2/.epub/.pdf — обработаю как книгу.\n\n"
            "<b>Команды:</b>\n"
            "/add &lt;URL&gt; — добавить книгу по URL\n"
            "/process &lt;file_id&gt; — обработать локальный файл\n"
            "/list — последние книги\n"
            "/search &lt;запрос&gt; — поиск\n"
            "/book &lt;название&gt; — открыть summary\n"
            "/template &lt;name&gt; — выбрать шаблон конспекта/воркбука\n"
            "/export &lt;txt|html&gt; — экспорт\n"
            "/doctor — диагностика\n"
            "/cancel — отменить обработку",
            parse_mode=ParseMode.HTML,
            reply_markup=_channel_kb(),
        )


# ── Детектор желаний (TG-версия) ───────────────────────────────────

def _detector_question_kb(q_idx: int) -> InlineKeyboardMarkup:
    """Inline-кнопки 1-4 для вопроса q_idx (1..5). callback_data='det:q:<idx>:<choice>'."""
    buttons = []
    for i in range(4):
        buttons.append(
            [InlineKeyboardButton(text=str(i + 1), callback_data=f"det:q:{q_idx}:{i}")]
        )
    buttons.append(
        [InlineKeyboardButton(text="❌ Отменить", callback_data="det:cancel")]
    )
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def _detector_intro_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="▶️ Начать тест", callback_data="det:start")],
            [InlineKeyboardButton(text="↗ Открыть на сайте", url="https://app.pulab.ru/detector/")],
            [InlineKeyboardButton(text="📢 Наш канал", url="https://t.me/pulabru")],
        ]
    )


# Ссылка на основной TG-канал «Лаборатория желаний» (@pulabru)
# Используется в /start обоих ботов (DetectorBot и Bibliobot)
CHANNEL_URL = "https://t.me/pulabru"
CHANNEL_HANDLE = "@pulabru"


def _channel_kb() -> InlineKeyboardMarkup:
    """Inline-кнопка-ссылка на основной TG-канал."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=f"📢 Наш канал {CHANNEL_HANDLE}", url=CHANNEL_URL)],
        ]
    )


def _detector_result_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🔁 Пройти ещё раз", callback_data="det:restart")],
            [
                InlineKeyboardButton(text="↗ Поделиться результатом", url="https://app.pulab.ru/detector/"),
            ],
            [
                InlineKeyboardButton(
                    text="🎯 Полный разбор от AI-коуча",
                    url="https://app.pulab.ru/pricing/",
                ),
            ],
        ]
    )


async def cmd_detector(message: Message) -> None:
    """Показывает интро детектора. Callback det:start запускает квиз."""
    chat_id = message.chat.id
    _reset_detector(chat_id)  # свежая сессия
    await message.answer(
        detector_format_intro(),
        parse_mode=ParseMode.HTML,
        reply_markup=_detector_intro_kb(),
    )


async def cb_detector_start(callback: CallbackQuery) -> None:
    await callback.answer()
    chat_id = callback.message.chat.id
    session = _get_detector(chat_id)
    # Отправляем первый вопрос
    q = DETECTOR_QUESTIONS[0]
    await callback.message.answer(
        detector_format_question(q),
        parse_mode=ParseMode.HTML,
        reply_markup=_detector_question_kb(1),
    )


async def cb_detector_answer(callback: CallbackQuery) -> None:
    """det:q:<q_idx>:<choice_index> — записать ответ и показать следующий вопрос или результат."""
    if callback.data is None:
        return
    await callback.answer()
    parts = callback.data.split(":")
    if len(parts) != 4:
        return
    _, _, q_idx_s, choice_s = parts
    try:
        q_idx = int(q_idx_s)        # 1..5
        choice = int(choice_s)      # 0..3
    except ValueError:
        return

    if not (1 <= q_idx <= len(DETECTOR_QUESTIONS) and 0 <= choice <= 3):
        return

    chat_id = callback.message.chat.id
    session = _get_detector(chat_id)
    q = DETECTOR_QUESTIONS[q_idx - 1]
    weight = q.options[choice][1]
    session.record(weight)

    if session.is_finished:
        verdict, imposed_pct = session.compute()
        await callback.message.answer(
            detector_format_result(verdict, imposed_pct),
            parse_mode=ParseMode.HTML,
            reply_markup=_detector_result_kb(),
        )
        # Шарим ссылку на сайт с теми же вопросами — для расшаривания в сторис
        _reset_detector(chat_id)
    else:
        next_q = DETECTOR_QUESTIONS[session.step]
        await callback.message.answer(
            detector_format_question(next_q),
            parse_mode=ParseMode.HTML,
            reply_markup=_detector_question_kb(q_idx + 1),
        )


async def cb_detector_cancel(callback: CallbackQuery) -> None:
    await callback.answer("Тест отменён")
    chat_id = callback.message.chat.id
    _reset_detector(chat_id)
    await callback.message.answer("Окей, отменила. Можешь вернуться когда угодно — /detector")


async def cb_detector_restart(callback: CallbackQuery) -> None:
    await callback.answer()
    chat_id = callback.message.chat.id
    _reset_detector(chat_id)
    await callback.message.answer(
        detector_format_intro(),
        parse_mode=ParseMode.HTML,
        reply_markup=_detector_intro_kb(),
    )


async def cmd_add(message: Message) -> None:
    if message.text is None:
        return
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2 or not parts[1].strip():
        await message.answer("⚠️ Укажите URL: <code>/add https://www.koob.ru/zeland/level1</code>", parse_mode=ParseMode.HTML)
        return
    url = parts[1].strip()
    if not url.startswith(("http://", "https://", "file://")):
        await message.answer("❌ URL должен начинаться с http://, https:// или file://")
        return
    state = _chat_state.setdefault(message.chat.id, {})
    if state.get("processing"):
        await message.answer(f"⚠️ Уже обрабатываю: {state.get('current_url')}. Дождитесь или /cancel")
        return
    await _process_url(message.chat.id, url, message)


async def cmd_cancel(message: Message) -> None:
    state = _chat_state.get(message.chat.id, {})
    if state.get("processing"):
        state["processing"] = False
        state["current_url"] = None
        await message.answer("🛑 Текущая обработка прервана")
    else:
        await message.answer("ℹ️ Нечего отменять")


async def cmd_list(message: Message) -> None:
    parts = (message.text or "").split()
    limit = 10
    if len(parts) > 1 and parts[1].isdigit():
        limit = min(50, int(parts[1]))
    out = get_settings().output_dir
    if not out.exists():
        await message.answer("📂 Библиотека пуста")
        return
    folders = sorted(
        [f for f in out.iterdir() if f.is_dir() and (f / "summary.md").exists()],
        key=lambda p: p.stat().st_mtime, reverse=True,
    )[:limit]
    if not folders:
        await message.answer("📂 Пока ничего не обработано")
        return
    lines = ["📚 <b>Последние книги:</b>\n"]
    for i, f in enumerate(folders, start=1):
        title = f.name.replace("_", " ")
        # Попробуем достать нормальное название из metadata
        meta = f / "metadata.json"
        author = ""
        if meta.exists():
            try:
                import json
                md = json.loads(meta.read_text(encoding="utf-8"))
                title = md.get("title") or title
                author = f" — {md.get('author', '')}"
            except (OSError, ValueError):
                pass
        lines.append(f"{i}. <b>{title}</b>{author}\n   <code>{f.name}</code>")
    await message.answer("\n\n".join(lines), parse_mode=ParseMode.HTML)


async def cmd_template(message: Message) -> None:
    """
    /template — показать или сменить шаблон для текущего чата.

    Без аргумента: показать текущее значение и список доступных шаблонов.
    С аргументом: установить имя шаблона, который будет использован
    для следующих /add (и для summary, и для workbook).
    Поддерживаются отдельные флаги:
        /template summary=NAME   — только summary
        /template workbook=NAME  — только workbook
    """
    parts = (message.text or "").split(maxsplit=1)
    state = _chat_state.setdefault(message.chat.id, {})

    if len(parts) < 2 or not parts[1].strip():
        # Показать текущее состояние
        cur_sum = state.get("template_summary") or state.get("template") or "(по умолчанию)"
        cur_wb = state.get("template_workbook") or state.get("template") or "(по умолчанию)"
        # Список доступных шаблонов
        from agent.templates import TemplateRegistry
        from agent.config import PROJECT_ROOT
        try:
            reg = TemplateRegistry(project_root=PROJECT_ROOT)
            all_t = reg.list()
        except Exception:
            all_t = []
        lines = [
            "📐 <b>Шаблоны</b>\n",
            f"Текущий (summary): <code>{cur_sum}</code>",
            f"Текущий (workbook): <code>{cur_wb}</code>\n",
            "<b>Доступные:</b>",
        ]
        for tpl in all_t:
            lines.append(
                f"  • <code>{tpl.name}</code> ({tpl.kind}, v{tpl.version}) — "
                f"{tpl.description[:50]}"
            )
        lines.append(
            "\n<b>Использование:</b>\n"
            "<code>/template &lt;name&gt;</code> — оба сразу\n"
            "<code>/template summary=&lt;name&gt; workbook=&lt;name&gt;</code>\n"
            "<code>/template default</code> — сбросить на .env-дефолт"
        )
        await message.answer("\n".join(lines), parse_mode=ParseMode.HTML)
        return

    arg = parts[1].strip()
    if arg.lower() in ("default", "reset"):
        state.pop("template", None)
        state.pop("template_summary", None)
        state.pop("template_workbook", None)
        await message.answer("📐 Шаблон сброшен на .env-дефолт", parse_mode=ParseMode.HTML)
        return

    # Разбираем token=NAME пары
    tpl = state.get("template")
    tpl_sum = state.get("template_summary")
    tpl_wb = state.get("template_workbook")
    for token in arg.split():
        if "=" in token:
            k, _, v = token.partition("=")
            k = k.strip().lower()
            v = v.strip()
            if k in ("summary", "summary_v2", "s"):
                tpl_sum = v
            elif k in ("workbook", "wb", "w"):
                tpl_wb = v
        else:
            tpl = token
    state["template"] = tpl
    state["template_summary"] = tpl_sum
    state["template_workbook"] = tpl_wb

    msg = "📐 Шаблон обновлён:\n"
    if tpl:
        msg += f"  • default: <code>{tpl}</code>\n"
    if tpl_sum:
        msg += f"  • summary: <code>{tpl_sum}</code>\n"
    if tpl_wb:
        msg += f"  • workbook: <code>{tpl_wb}</code>\n"
    await message.answer(msg, parse_mode=ParseMode.HTML)


async def cmd_search(message: Message) -> None:
    from agent.search import search_library
    parts = (message.text or "").split(maxsplit=1)
    if len(parts) < 2:
        await message.answer("⚠️ Укажите запрос: <code>/search привычки</code>", parse_mode=ParseMode.HTML)
        return
    query = parts[1].strip()
    results = search_library(query, get_settings().output_dir, max_results=15)
    if not results:
        await message.answer(f"🔍 По запросу «{query}» ничего не найдено")
        return
    lines = [f"🔍 <b>«{query}»</b> — найдено: {len(results)}\n"]
    for i, (folder, score, _snip) in enumerate(results, start=1):
        title = folder.name.replace("_", " ")
        lines.append(f"{i}. <b>{title}</b>  (score={score})")
    await message.answer("\n".join(lines), parse_mode=ParseMode.HTML)


async def cmd_book(message: Message) -> None:
    """Найти книгу по подстроке и прислать её summary.md."""
    parts = (message.text or "").split(maxsplit=1)
    if len(parts) < 2:
        await message.answer("⚠️ Укажите название: <code>/book трансерфинг</code>", parse_mode=ParseMode.HTML)
        return
    needle = parts[1].strip().lower()
    out = get_settings().output_dir
    for folder in sorted(out.iterdir(), reverse=True):
        if not folder.is_dir():
            continue
        if needle in folder.name.lower():
            summary = folder / "summary.md"
            if not summary.exists():
                continue
            text = summary.read_text(encoding="utf-8", errors="ignore")
            for chunk in _split_message(text, 4000):
                await message.answer(chunk)
            return
    await message.answer(f"❌ Не нашёл книгу с «{needle}»")


async def cmd_export(message: Message) -> None:
    """Экспорт конкретной книги в указанный формат."""
    parts = (message.text or "").split(maxsplit=2)
    if len(parts) < 3:
        await message.answer("⚠️ Использование: <code>/export txt название</code>", parse_mode=ParseMode.HTML)
        return
    fmt, needle = parts[1].strip().lower(), parts[2].strip().lower()
    if fmt not in ("txt", "html", "pdf", "epub", "docx"):
        await message.answer(f"❌ Формат «{fmt}» не поддерживается. Используйте txt, html, pdf, epub, docx")
        return
    out = get_settings().output_dir
    for folder in sorted(out.iterdir(), reverse=True):
        if not folder.is_dir():
            continue
        if needle in folder.name.lower():
            files = export_book(folder, [fmt])
            if not files:
                await message.answer(f"❌ Не удалось экспортировать в {fmt} (попробуйте txt или html)")
                return
            for f in files:
                if f.stat().st_size < 50_000_000:  # Telegram limit 50MB
                    await message.answer_document(document=f.open("rb"), caption=f.name)
                else:
                    await message.answer(f"⚠️ Файл слишком большой: {f}")
            return
    await message.answer(f"❌ Книга с «{needle}» не найдена")


# ── /process <file_id>  и приём файлов от пользователя ─────────────
_BOOKS_DIR = Path("books_input")


async def cmd_process_local(message: Message) -> None:
    """Обработать локальный файл: /process <file_id>."""
    if message.text is None:
        return
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2 or not parts[1].strip():
        await message.answer(
            "⚠️ Использование:\n"
            "• Перешлите боту файл .txt/.fb2/.epub/.pdf\n"
            "• Или: <code>/process &lt;file_id&gt;</code>",
            parse_mode=ParseMode.HTML,
        )
        return
    file_id = parts[1].strip()
    _BOOKS_DIR.mkdir(parents=True, exist_ok=True)
    target = _BOOKS_DIR / file_id
    if not target.exists():
        await message.answer(f"❌ Файл <code>{file_id}</code> не найден в <code>{_BOOKS_DIR}/</code>", parse_mode=ParseMode.HTML)
        return
    state = _chat_state.setdefault(message.chat.id, {})
    if state.get("processing"):
        await message.answer(f"⚠️ Уже обрабатываю: {state.get('current_url')}")
        return
    await _process_local_file(message.chat.id, target, message)


async def handle_document(message: Message) -> None:
    """Пользователь прислал файл — сохраняем в books_input/ и обрабатываем."""
    if not message.document:
        return
    doc = message.document
    name = doc.file_name or "book"
    if not name.lower().endswith((".txt", ".fb2", ".epub", ".pdf")):
        await message.answer(f"⚠️ Поддерживаются .txt/.fb2/.epub/.pdf, получила: <code>{name}</code>", parse_mode=ParseMode.HTML)
        return
    _BOOKS_DIR.mkdir(parents=True, exist_ok=True)
    target = _BOOKS_DIR / name
    try:
        bot_file = await message.bot.get_file(doc.file_id)
        await message.bot.download_file(bot_file.file_path, destination=target)
    except Exception as e:
        await message.answer(f"❌ Не удалось скачать файл: <code>{e}</code>", parse_mode=ParseMode.HTML)
        return
    state = _chat_state.setdefault(message.chat.id, {})
    if state.get("processing"):
        await message.answer(f"⚠️ Уже обрабатываю: {state.get('current_url')}. Файл сохранён, обработаю позже.")
        return
    await _process_local_file(message.chat.id, target, message)


async def _process_local_file(chat_id: int, path: Path, message: Message) -> None:
    state = _chat_state.setdefault(chat_id, {})
    state["processing"] = True
    state["current_url"] = str(path)
    librarian: WishLibrarian = state.get("librarian") or _get_librarian(chat_id)
    status_msg = await message.answer(f"⏳ Обрабатываю локальный файл:\n<code>{path.name}</code>", parse_mode=ParseMode.HTML)
    try:
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(None, librarian.process_local_file, path)
        if result.errors:
            err = result.errors[0][:500]
            await status_msg.edit_text(f"❌ <b>Ошибка</b>\n\nКнига: <i>{result.book.title or '—'}</i>\nОшибка: <code>{err}</code>", parse_mode=ParseMode.HTML)
            return
        folder_name = Path(result.folder).name if result.folder else "—"
        text = (
            f"✅ <b>Готово (локальный файл)!</b>\n\n"
            f"📖 <b>{result.book.title}</b>\n"
            f"✍️ {result.book.author}\n"
            f"📁 <code>{folder_name}</code>\n\n"
            f"📝 Summary: {'✅' if result.summary_path else '—'}\n"
            f"✍️ Workbook: {'✅' if result.workbook_path else '—'}\n"
            f"💡 Tips: {'✅' if result.tips_path else '—'}\n"
            f"💬 Reviews: {'✅' if result.reviews_path else '—'}\n\n"
            f"/book <b>{result.book.title[:30]}</b> — открыть summary"
        )
        await status_msg.edit_text(text, parse_mode=ParseMode.HTML)
    except Exception as e:
        logger.exception("Ошибка обработки {}: {}", path, e)
        await status_msg.edit_text(f"💥 <b>Ошибка:</b> <code>{e}</code>", parse_mode=ParseMode.HTML)
    finally:
        state["processing"] = False
        state["current_url"] = None


async def cmd_doctor(message: Message) -> None:
    from agent.doctor import run_doctor
    # Перенаправляем stdout в буфер и отдаём результат как сообщение
    import io
    from rich.console import Console as RichConsole
    buf = io.StringIO()
    rich = RichConsole(file=buf, force_terminal=False, width=80)
    # Просто вызываем логику doctor и собираем print
    from agent.doctor import (
        _check_python, _check_deps, _check_sites, _check_ai,
        _check_disk, _check_books,
    )
    py_v, _ = _check_python()
    n_sites, _ = _check_sites()
    ai_name, ai_st, ai_model = _check_ai()
    n_books, _ = _check_books()
    text = (
        f"🩺 <b>WishLibrarian — диагностика</b>\n\n"
        f"🐍 Python: {py_v}\n"
        f"📋 Карт парсера: {n_sites}\n"
        f"🤖 AI: {ai_name} ({ai_model}) — {ai_st}\n"
        f"📚 Книг обработано: {n_books}\n"
    )
    # Детали по зависимостям
    deps = _check_deps()
    missing = [pkg for pkg, st, _ in deps if "❌" in st]
    if missing:
        text += f"\n⚠️ Не установлены: <code>{', '.join(missing)}</code>"
    else:
        text += "\n✅ Все зависимости на месте"
    await message.answer(text, parse_mode=ParseMode.HTML)


# ── Inline-кнопки (Callback) ────────────────────────────────────────
async def cb_book_part(callback: CallbackQuery) -> None:
    """Открыть конкретную часть книги (summary / workbook / tips)."""
    _, part, folder_name = callback.data.split(":", 2)
    folder = get_settings().output_dir / folder_name
    fname = {"summary": "summary.md", "workbook": "workbook.md", "tips": "practical_tips.md"}.get(part)
    if not fname:
        await callback.answer("❓ Неизвестная часть")
        return
    p = folder / fname
    if not p.exists():
        await callback.answer("Файл не найден")
        return
    text = p.read_text(encoding="utf-8", errors="ignore")
    for chunk in _split_message(text, 4000):
        await callback.message.answer(chunk)
    await callback.answer()


async def cb_export(callback: CallbackQuery) -> None:
    """Экспорт в .txt через inline-кнопку."""
    _, fmt, folder_name = callback.data.split(":", 2)
    folder = get_settings().output_dir / folder_name
    files = export_book(folder, [fmt])
    if not files:
        await callback.answer("Ошибка экспорта")
        return
    for f in files:
        try:
            await callback.message.answer_document(document=f.open("rb"), caption=f.name)
        except Exception as e:
            await callback.message.answer(f"⚠️ {e}")
    await callback.answer()


# ── Свободный текст — URL ───────────────────────────────────────────
async def handle_url_text(message: Message) -> None:
    """Если пользователь прислал URL без /add — обработать как /add."""
    if message.text is None:
        return
    url = message.text.strip()
    if url.startswith(("http://", "https://", "file://")):
        # Подменяем на /add
        message.text = f"/add {url}"
        await cmd_add(message)
    else:
        await message.answer(
            "ℹ️ Пришлите URL книги или используйте /help для списка команд"
        )


# ── Прокси-хелперы ────────────────────────────────────────────────
def _build_proxy_connector(proxy_url: str):
    """
    Вернуть aiohttp-коннектор для SOCKS5/HTTP прокси.
    Возвращает None, если прокси не задан.
    Поддерживает:
      - socks5://[user:pass@]host:port
      - socks4://[user@]host:port
      - http://[user:pass@]host:port
      - https://[user:pass@]host:port
    """
    if not proxy_url:
        return None
    try:
        from aiohttp_socks import ProxyConnector
    except ImportError:
        logger.error(
            "❌ aiohttp-socks не установлен. "
            "Установите: pip install aiohttp-socks"
        )
        return None

    parsed = proxy_url.strip()
    if "://" not in parsed:
        # Голый host:port → добавляем socks5://
        parsed = "socks5://" + parsed

    scheme = parsed.split("://", 1)[0].lower()
    if scheme not in ("socks5", "socks4", "http", "https"):
        logger.warning("⚠️  Неизвестная схема прокси: {}, использую socks5", scheme)
        scheme = "socks5"

    logger.info("🌐 Telegram через прокси: {}://***", scheme)
    # ProxyConnector.from_url требует запущенного event loop
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        # Вне event loop (например, в обычном .py-скрипте) — создаём лёгкий loop
        return _build_proxy_connector_sync(parsed)
    return ProxyConnector.from_url(parsed)


def _build_proxy_connector_sync(parsed: str):
    """Создать коннектор вне активного event loop (например, в синхронном коде)."""
    from aiohttp_socks import ProxyConnector
    # Если уже есть running loop (например, вызов из async-контекста) — выполняем сразу
    try:
        asyncio.get_running_loop()
        return ProxyConnector.from_url(parsed)
    except RuntimeError:
        pass
    # Синхронный контекст: запускаем loop, вызываем from_url внутри корутины,
    # чтобы aiohttp увидел running loop.
    loop = asyncio.new_event_loop()
    try:
        async def _build():
            return ProxyConnector.from_url(parsed)
        return loop.run_until_complete(_build())
    finally:
        # НЕ закрываем loop — коннектор привязан к нему
        pass


# ── Failover между primary/backup прокси ───────────────────────────
# Если primary-прокси N раз подряд вернул сетевую ошибку — закрываем
# текущую сессию, пересоздаём бота с backup-прокси и продолжаем polling.
# Возврата обратно нет (избегаем ping-pong): считаем backup стабильным.

_FAILOVER_NETWORK_ERRORS: tuple = (
    TelegramNetworkError,
    TelegramRetryAfter,
    AiohttpClientError,
    asyncio.TimeoutError,
    ConnectionError,
    OSError,
)


async def _start_polling_with_failover(
    bot: Bot,
    dp: Dispatcher,
    primary_proxy: str,
    backup_proxy: str,
    threshold: int = 3,
) -> None:
    """
    Запускает polling с автоматическим переключением primary → backup.

    Логика:
      • consecutive_failures++ при любой сетевой ошибке
      • если consecutive_failures >= threshold и backup задан — переключаемся
      • переключение = закрыть bot.session, создать новый AiohttpSession(proxy=backup)
      • при успехе (любой getUpdates ответ) — сбрасываем счётчик
    """
    consecutive_failures = 0
    switched = False  # чтобы не переключаться повторно
    last_log_ts = 0.0

    while True:
        try:
            logger.info(
                "📡 Polling start (proxy={})",
                backup_proxy if switched else primary_proxy or "—",
            )
            # allowed_updates по умолчанию None — бот получает все типы
            await dp.start_polling(bot, handle_signals=False)
            # start_polling завершился без исключения — выход
            return
        except _FAILOVER_NETWORK_ERRORS as e:
            consecutive_failures += 1
            err_short = type(e).__name__ + ": " + str(e)[:120]
            logger.warning(
                "⚠️ Сетевая ошибка #{}/{}: {}",
                consecutive_failures, threshold, err_short,
            )

            # Решение: переключаться ли
            should_switch = (
                not switched
                and backup_proxy
                and backup_proxy.strip()
                and consecutive_failures >= threshold
            )

            if should_switch:
                logger.warning(
                    "🔁 Переключаюсь с primary на BACKUP-прокси: {}",
                    backup_proxy,
                )
                try:
                    await bot.session.close()
                except Exception:
                    pass
                switched = True
                consecutive_failures = 0
                # Пересоздаём бота с backup-прокси
                from aiogram.client.session.aiohttp import AiohttpSession
                bot.session = AiohttpSession(proxy=backup_proxy.strip())
                # Маленькая пауза, чтобы не зациклиться
                await asyncio.sleep(2)
                continue

            # Иначе — экспоненциальный backoff
            backoff = min(30, 2 ** consecutive_failures)
            logger.info("⏳ Retry через {} сек", backoff)
            await asyncio.sleep(backoff)
            continue


# ── Точка входа ─────────────────────────────────────────────────────
def _parse_role() -> str:
    """Парсим --role=detector|librarian из sys.argv. По умолчанию — librarian."""
    for arg in sys.argv[1:]:
        if arg.startswith("--role="):
            return arg.split("=", 1)[1].strip().lower()
    return "librarian"


async def main() -> None:
    setup_logging()
    settings = get_settings()
    role = _parse_role()
    logger.info("🤖 Роль бота: {}", role)

    # Выбор токена по роли
    if role == "detector":
        token = (
            settings.telegram_bot_token_detector.strip()
            or os.environ.get("TELEGRAM_BOT_TOKEN_DETECTOR", "").strip()
            or settings.telegram_bot_token.strip()
        )
    else:  # librarian (по умолчанию)
        token = (
            settings.telegram_bot_token_librarian.strip()
            or os.environ.get("TELEGRAM_BOT_TOKEN_LIBRARIAN", "").strip()
            or settings.telegram_bot_token.strip()
        )
    if not token:
        print(
            "❌ TELEGRAM_BOT_TOKEN не задан.\n"
            "Заполните TELEGRAM_BOT_TOKEN в .env или экспортируйте:\n"
            "  Windows: set TELEGRAM_BOT_TOKEN=...\n"
            "  Linux/Mac: export TELEGRAM_BOT_TOKEN=...",
            file=sys.stderr,
        )
        sys.exit(1)

    # Сессия: с прокси или без (aiogram 3.29 принимает proxy= напрямую)
    proxy_url = settings.telegram_proxy_url.strip() or os.environ.get("TELEGRAM_PROXY_URL", "")
    bot_props = DefaultBotProperties(parse_mode=ParseMode.HTML)
    if proxy_url:
        from aiogram.client.session.aiohttp import AiohttpSession
        session = AiohttpSession(proxy=proxy_url)
        bot = Bot(token=token, default=bot_props, session=session)
        logger.info("🤖 Telegram-бот запущен (прокси={})", proxy_url)
    else:
        bot = Bot(token=token, default=bot_props)
        logger.info("🤖 Telegram-бот запущен (без прокси)")
    dp = Dispatcher()

    # Команды (фильтруем по роли)
    if role == "detector":
        # DetectorBot: только старт + детектор. Никаких /add, /book, /list.
        dp.message.register(cmd_start, Command("start", "help"))
        dp.message.register(cmd_detector, Command("detector"))
        # Inline-кнопки только детектора
        dp.callback_query.register(cb_detector_start, F.data == "det:start")
        dp.callback_query.register(cb_detector_answer, F.data.startswith("det:q:"))
        dp.callback_query.register(cb_detector_cancel, F.data == "det:cancel")
        dp.callback_query.register(cb_detector_restart, F.data == "det:restart")
    else:
        # WLBBibliobot: полный набор книжных команд
        dp.message.register(cmd_start, Command("start", "help"))
        dp.message.register(cmd_add, Command("add"))
        dp.message.register(cmd_cancel, Command("cancel"))
        dp.message.register(cmd_list, Command("list"))
        dp.message.register(cmd_search, Command("search"))
        dp.message.register(cmd_book, Command("book"))
        dp.message.register(cmd_export, Command("export"))
        dp.message.register(cmd_doctor, Command("doctor"))
        dp.message.register(cmd_process_local, Command("process"))
        dp.message.register(cmd_template, Command("template"))
        # Документы от пользователя (файлы книг)
        dp.message.register(handle_document, F.document)
        # Свободный текст (только если сообщение похоже на URL)
        dp.message.register(handle_url_text, F.text)

        # Inline-кнопки книг
        dp.callback_query.register(cb_book_part, F.data.startswith("book:"))
        dp.callback_query.register(cb_export, F.data.startswith("export:"))

    print(f"🤖 {role.capitalize()} Bot is running. Press Ctrl+C to stop.")
    # Failover primary → backup при сетевых ошибках
    backup_proxy = (
        settings.telegram_proxy_url_backup.strip()
        or os.environ.get("TELEGRAM_PROXY_URL_BACKUP", "").strip()
    )
    threshold = settings.proxy_failover_threshold
    try:
        await _start_polling_with_failover(
            bot=bot,
            dp=dp,
            primary_proxy=proxy_url,
            backup_proxy=backup_proxy,
            threshold=threshold,
        )
    finally:
        try:
            await bot.session.close()
        except Exception:
            pass


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        print("\n👋 Бот остановлен")
