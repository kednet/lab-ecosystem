"""
Бот WishLibrarian для сообщества ВКонтакте.

Использует Long Poll API (не требует веб-сервера) — слушаем новые сообщения
от пользователей и отвечаем.

Команды (сообщения, начинающиеся с "/"):
  /start, /help    — справка
  /add <URL>       — добавить книгу в обработку
  /status          — что в процессе
  /list [N]        — последние N обработанных книг
  /search <запрос> — поиск по библиотеке
  /book <название> — открыть summary.md (отправляет файлом)
  /export <fmt>    — экспортировать книгу (txt/html)
  /doctor          — диагностика

Запуск:
    # 1. Создайте сообщество VK: https://vk.com/groups → Создать сообщество
    # 2. Настройки сообщества → Работа с API → Создать ключ
    #    Включите: Разрешить отправку сообщений, Long Poll API
    # 3. В .env:
    #    VK_GROUP_TOKEN=vk1.a....    # токен сообщества
    #    VK_GROUP_ID=123456789         # числовой ID сообщества
    # 4. python -m agent.vk_bot
"""
from __future__ import annotations

import os
import re
import sys
import time
from pathlib import Path
from typing import Dict, Optional

try:
    from dotenv import load_dotenv
    _PROJECT_ROOT = Path(__file__).resolve().parent.parent
    load_dotenv(_PROJECT_ROOT / ".env", override=False)
except ImportError:
    pass

import vk_api
from vk_api.longpoll import VkEventType, VkLongPoll

from agent.config import get_settings
from agent.librarian import WishLibrarian
from agent.detector import (
    QUESTIONS as DETECTOR_QUESTIONS,
    DetectorSession,
    format_intro as detector_format_intro,
    format_question as detector_format_question,
    format_result as detector_format_result,
)
from agent.utils.logger import get_logger, setup_logging
from agent.export import export_book


logger = get_logger()


# ── Хранилище состояния диалога ─────────────────────────────────────
# key = user_id, value = {processing, current_url, librarian, last_help}
_user_state: Dict[int, dict] = {}


# ── Хелперы отправки ────────────────────────────────────────────────
def _vk_session(token: str) -> tuple[vk_api.vk_api.VkApiMethod, vk_api.VkApi]:
    """Создать VK-сессию по токену сообщества.

    Управляющие переменные окружения:
      VK_VERIFY_SSL=false  — отключить TLS-проверку (корпоративный MITM)
      VK_NO_TRUST_ENV=true — игнорировать системные HTTP/SOCKS-прокси
      VK_PROXY_URL=<url>   — пробросить свой прокси в requests.Session
                             (например, ``socks5://127.0.0.1:10808``)

    Если ничего не задано — используется ``requests.Session()`` с
    ``trust_env=True``, и подхватываются системные прокси Windows
    (WinINET/ProxyEnable). Для SOCKS-схемы требуется пакет ``PySocks``
    (добавьте ``PySocks`` в ``requirements.txt``).
    """
    if not token:
        raise RuntimeError("VK_GROUP_TOKEN не задан в .env")
    import requests

    session = requests.Session()
    # Если пользователь явно задал VK_PROXY_URL — используем его и
    # подхватываем системные (могут пригодиться). Иначе — отключаем
    # trust_env по умолчанию, потому что иначе SOCKS/HTTP-прокси из
    # системных env (HTTP_PROXY, SOCKS_PROXY, реестр Windows) ломают
    # все запросы с "Missing dependencies for SOCKS support" /
    # `OSError: [WinError 121]` на мёртвом localhost:10808.
    proxy_url = (
        os.environ.get("VK_PROXY_URL", "").strip()
        or os.environ.get("VK_PROXY", "").strip()
    )
    no_trust_env_raw = os.environ.get("VK_NO_TRUST_ENV", "").strip().lower()
    if proxy_url:
        no_trust_env = no_trust_env_raw in ("true", "1", "yes", "on")
    else:
        # Дефолт: НЕ подхватывать системные прокси, если явно не попросили.
        no_trust_env = no_trust_env_raw not in ("false", "0", "no", "off")
    if no_trust_env:
        session.trust_env = False
        logger.info("🔧 VK: trust_env отключён (системные прокси игнорируются)")

    verify_env = (
        os.environ.get("VK_VERIFY_SSL", "").strip().lower()
        or os.environ.get("GIGACHAT_VERIFY_SSL", "").strip().lower()
    )
    if verify_env in ("false", "0", "no", "off"):
        session.verify = False
        import warnings
        from urllib3.exceptions import InsecureRequestWarning
        warnings.filterwarnings("ignore", category=InsecureRequestWarning)
        logger.warning("⚠️ VK: проверка TLS отключена (корпоративный MITM)")

    proxy_url = (
        os.environ.get("VK_PROXY_URL", "").strip()
        or os.environ.get("VK_PROXY", "").strip()
    )
    if proxy_url:
        if "://" not in proxy_url:
            proxy_url = "socks5://" + proxy_url
        session.proxies = {"http": proxy_url, "https": proxy_url}
        logger.info("🌐 VK через прокси: {}://***", proxy_url.split("://", 1)[0])

    vk_session = vk_api.VkApi(token=token, session=session)
    return vk_session.get_api(), vk_session


def _send_message(api, user_id: int, text: str, **kwargs) -> None:
    """Отправить текстовое сообщение. Делит длинное на чанки по 4000 симв."""
    max_len = 4000
    for i in range(0, max(len(text), 1), max_len):
        chunk = text[i : i + max_len]
        if not chunk:
            continue
        try:
            api.messages.send(
                user_id=user_id,
                message=chunk,
                random_id=int(time.time() * 1000) + i,
                **kwargs,
            )
        except Exception as e:
            logger.error("VK send error: {}", e)


def _send_doc(api, user_id: int, file_path: Path, title: str) -> None:
    """Отправить файл как документ сообщества."""
    if not file_path.exists() or file_path.stat().st_size == 0:
        _send_message(api, user_id, f"⚠️ Файл пустой: {title}")
        return
    try:
        # Сначала загружаем файл
        upload = vk_api.VkUpload(vk_api.VkApi(token=os.environ.get("VK_GROUP_TOKEN", "")))
        doc = upload.document_message(
            file_path=str(file_path),
            title=title,
            peer_id=user_id,
        )
        owner_id = doc[0]["owner_id"]
        doc_id = doc[0]["id"]
        api.messages.send(
            user_id=user_id,
            message=f"📎 {title}",
            attachment=f"doc{owner_id}_{doc_id}",
            random_id=int(time.time() * 1000),
        )
    except Exception as e:
        logger.exception("Ошибка отправки файла {}: {}", file_path, e)
        _send_message(api, user_id, f"⚠️ Не удалось отправить файл: {e}")


# ── Команды ─────────────────────────────────────────────────────────
def cmd_start(api, user_id: int) -> None:
    _send_message(
        api, user_id,
        "📚 <b>WishLibrarian Bot (ВКонтакте)</b>\n\n"
        "Я обрабатываю книги с koob.ru, LiveLib, Лабиринта, Литреса и др.\n"
        "Скиньте URL — я сделаю конспект, воркбук и подберу отзывы.\n\n"
        "<b>Команды:</b>\n"
        "/add &lt;URL&gt; — добавить книгу по URL\n"
        "/books — список книг в books_input/\n"
        "/process &lt;имя&gt; — обработать локальный файл\n"
        "/list — последние книги\n"
        "/search &lt;запрос&gt; — поиск\n"
        "/book &lt;название&gt; — открыть summary\n"
        "/export &lt;txt|html&gt; — экспорт\n"
        "/detector — мини-тест «Навязанное или твоё?»\n"
        "/doctor — диагностика",
    )


def cmd_doctor(api, user_id: int) -> None:
    from agent.doctor import (
        _check_python, _check_sites, _check_ai, _check_books,
    )
    py_v, _ = _check_python()
    n_sites, _ = _check_sites()
    ai_name, ai_st, ai_model = _check_ai()
    n_books, _ = _check_books()
    _send_message(
        api, user_id,
        f"🩺 <b>WishLibrarian — диагностика</b>\n\n"
        f"🐍 Python: {py_v}\n"
        f"📋 Карт парсера: {n_sites}\n"
        f"🤖 AI: {ai_name} ({ai_model}) — {ai_st}\n"
        f"📚 Книг обработано: {n_books}\n",
    )


def cmd_list(api, user_id: int, args: str) -> None:
    limit = 10
    if args.strip().isdigit():
        limit = min(50, int(args.strip()))
    out = get_settings().output_dir
    if not out.exists():
        _send_message(api, user_id, "📂 Библиотека пуста")
        return
    folders = sorted(
        [f for f in out.iterdir() if f.is_dir() and (f / "summary.md").exists()],
        key=lambda p: p.stat().st_mtime, reverse=True,
    )[:limit]
    if not folders:
        _send_message(api, user_id, "📂 Пока ничего не обработано")
        return
    lines = ["📚 <b>Последние книги:</b>\n"]
    for i, f in enumerate(folders, start=1):
        title = f.name.replace("_", " ")
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
        lines.append(f"{i}. <b>{title}</b>{author}\n   <i>{f.name}</i>")
    _send_message(api, user_id, "\n\n".join(lines))


def cmd_search(api, user_id: int, args: str) -> None:
    from agent.search import search_library
    query = args.strip()
    if not query:
        _send_message(api, user_id, "⚠️ Использование: /search <запрос>")
        return
    results = search_library(query, get_settings().output_dir, max_results=15)
    if not results:
        _send_message(api, user_id, f"🔍 По запросу «{query}» ничего не найдено")
        return
    lines = [f"🔍 <b>«{query}»</b> — найдено: {len(results)}\n"]
    for i, (folder, score, _snip) in enumerate(results, start=1):
        title = folder.name.replace("_", " ")
        lines.append(f"{i}. <b>{title}</b>  (score={score})")
    _send_message(api, user_id, "\n".join(lines))


def cmd_book(api, user_id: int, args: str) -> None:
    needle = args.strip().lower()
    if not needle:
        _send_message(api, user_id, "⚠️ Использование: /book <название>")
        return
    out = get_settings().output_dir
    for folder in sorted(out.iterdir(), reverse=True):
        if not folder.is_dir():
            continue
        if needle in folder.name.lower():
            summary = folder / "summary.md"
            if not summary.exists():
                continue
            # Если файл больше 50 КБ — отдаём как документ
            if summary.stat().st_size > 50_000:
                _send_doc(api, user_id, summary, f"{folder.name} — summary.md")
            else:
                text = summary.read_text(encoding="utf-8", errors="ignore")
                _send_message(api, user_id, text)
            return
    _send_message(api, user_id, f"❌ Не нашёл книгу с «{needle}»")


def cmd_export(api, user_id: int, args: str) -> None:
    parts = args.strip().split(maxsplit=1)
    if len(parts) < 2:
        _send_message(api, user_id, "⚠️ Использование: /export <txt|html> <название>")
        return
    fmt, needle = parts[0].strip().lower(), parts[1].strip().lower()
    if fmt not in ("txt", "html", "pdf"):
        _send_message(api, user_id, f"❌ Формат «{fmt}» не поддерживается. Используйте txt, html, pdf")
        return
    out = get_settings().output_dir
    for folder in sorted(out.iterdir(), reverse=True):
        if not folder.is_dir():
            continue
        if needle in folder.name.lower():
            files = export_book(folder, [fmt])
            if not files:
                _send_message(api, user_id, f"❌ Не удалось экспортировать в {fmt}")
                return
            for f in files:
                _send_doc(api, user_id, f, f.name)
            return
    _send_message(api, user_id, f"❌ Книга с «{needle}» не найдена")


def cmd_add(api, user_id: int, args: str) -> None:
    """Запустить обработку книги."""
    url = args.strip()
    if not url:
        _send_message(api, user_id, "⚠️ Использование: /add <URL>")
        return
    if not url.startswith(("http://", "https://")):
        _send_message(api, user_id, "❌ URL должен начинаться с http:// или https://")
        return

    state = _user_state.setdefault(user_id, {})
    if state.get("processing"):
        _send_message(
            api, user_id,
            f"⚠️ Уже обрабатываю: {state.get('current_url')}. Дождитесь",
        )
        return

    state["processing"] = True
    state["current_url"] = url
    librarian: WishLibrarian = state.get("librarian")
    if librarian is None:
        librarian = WishLibrarian()
        state["librarian"] = librarian

    _send_message(api, user_id, f"⏳ Обрабатываю:\n{url}\n\nЭто может занять 1–3 минуты…")

    # Запускаем в отдельном потоке (Long Poll синхронный)
    import threading

    def _run():
        try:
            result = librarian.process_book(url, force=False, parse_only=False)
            book = result.book
            if result.errors:
                _send_message(
                    api, user_id,
                    f"❌ <b>Ошибка</b>\n\n"
                    f"Книга: <i>{book.title or '—'}</i>\n"
                    f"Ошибка: <code>{result.errors[0][:500]}</code>",
                )
                return
            folder_name = Path(result.folder).name if result.folder else "—"
            _send_message(
                api, user_id,
                f"✅ <b>Готово!</b>\n\n"
                f"📖 <b>{book.title}</b>\n"
                f"✍️ {book.author}\n"
                f"📅 {book.year or '—'}\n"
                f"📁 <i>{folder_name}</i>\n\n"
                f"📝 Summary: {'✅' if result.summary_path else '—'}\n"
                f"✍️ Workbook: {'✅' if result.workbook_path else '—'}\n"
                f"💡 Tips: {'✅' if result.tips_path else '—'}\n"
                f"💬 Reviews: {'✅' if result.reviews_path else '—'}\n\n"
                f"📥 Команды:\n"
                f"/book <b>{book.title[:30]}</b> — открыть summary\n"
                f"/export txt <b>{book.title[:20]}</b> — экспорт",
            )
        except Exception as e:
            logger.exception("VK bot: ошибка обработки {}: {}", url, e)
            _send_message(api, user_id, f"💥 <b>Ошибка:</b> <code>{e}</code>")
        finally:
            state["processing"] = False
            state["current_url"] = None

    t = threading.Thread(target=_run, daemon=True)
    t.start()


def cmd_cancel(api, user_id: int) -> None:
    state = _user_state.get(user_id, {})
    if state.get("processing"):
        state["processing"] = False
        state["current_url"] = None
        _send_message(api, user_id, "🛑 Текущая обработка прервана")
    else:
        _send_message(api, user_id, "ℹ️ Нечего отменять")


# ── /process — обработка локального файла ──────────────────────────
_VK_BOOKS_DIR = Path("books_input")


def cmd_books_list(api, user_id: int, args: str) -> None:
    """Показать файлы в books_input/."""
    from agent.book_reader import list_books
    books = list_books(_VK_BOOKS_DIR)
    if not books:
        _send_message(
            api, user_id,
            f"📂 Папка <code>{_VK_BOOKS_DIR}/</code> пуста.\n\n"
            f"Положите туда файл .txt/.fb2/.epub/.pdf и напишите:\n"
            f"/process &lt;имя_файла&gt;",
        )
        return
    lines = [f"📚 <b>Книги в {_VK_BOOKS_DIR}/</b>\n"]
    for i, p in enumerate(books, start=1):
        size_kb = p.stat().st_size / 1024
        lines.append(f"{i}. <code>{p.name}</code>  ({size_kb:.0f} КБ)")
    lines.append(f"\nЧтобы обработать:\n<code>/process {books[0].name}</code>")
    _send_message(api, user_id, "\n".join(lines))


def cmd_process(api, user_id: int, args: str) -> None:
    """Обработать локальный файл: /process <имя_файла>."""
    name = args.strip()
    if not name:
        _send_message(
            api, user_id,
            "⚠️ Использование: <code>/process &lt;имя_файла&gt;</code>\n"
            "Сначала <code>/books</code> — посмотреть, что в папке.",
        )
        return
    _VK_BOOKS_DIR.mkdir(parents=True, exist_ok=True)
    target = _VK_BOOKS_DIR / name
    if not target.exists():
        # Подсказка
        from agent.book_reader import list_books
        books = list_books(_VK_BOOKS_DIR)
        hint = ""
        if books:
            hint = "\n\nДоступно:\n" + "\n".join(f"• <code>{p.name}</code>" for p in books[:5])
        _send_message(
            api, user_id,
            f"❌ Файл <code>{name}</code> не найден в <code>{_VK_BOOKS_DIR}/</code>.{hint}",
        )
        return

    state = _user_state.setdefault(user_id, {})
    if state.get("processing"):
        _send_message(api, user_id, f"⚠️ Уже обрабатываю: {state.get('current_url')}")
        return

    state["processing"] = True
    state["current_url"] = str(target)
    librarian: WishLibrarian = state.get("librarian")
    if librarian is None:
        librarian = WishLibrarian()
        state["librarian"] = librarian

    _send_message(api, user_id, f"⏳ Обрабатываю локальный файл:\n<code>{name}</code>\n\nЭто займёт 1–3 минуты…")

    import threading

    def _run():
        try:
            result = librarian.process_local_file(target)
            if result.errors:
                _send_message(
                    api, user_id,
                    f"❌ <b>Ошибка</b>\n\n"
                    f"Книга: <i>{result.book.title or '—'}</i>\n"
                    f"Ошибка: <code>{result.errors[0][:500]}</code>",
                )
                return
            folder_name = Path(result.folder).name if result.folder else "—"
            _send_message(
                api, user_id,
                f"✅ <b>Готово (локальный файл)!</b>\n\n"
                f"📖 <b>{result.book.title}</b>\n"
                f"✍️ {result.book.author}\n"
                f"📁 <i>{folder_name}</i>\n\n"
                f"📝 Summary: {'✅' if result.summary_path else '—'}\n"
                f"✍️ Workbook: {'✅' if result.workbook_path else '—'}\n"
                f"💡 Tips: {'✅' if result.tips_path else '—'}\n\n"
                f"/book <b>{result.book.title[:30]}</b> — открыть summary",
            )
        except Exception as e:
            logger.exception("VK bot: ошибка обработки {}: {}", target, e)
            _send_message(api, user_id, f"💥 <b>Ошибка:</b> <code>{e}</code>")
        finally:
            state["processing"] = False
            state["current_url"] = None

    t = threading.Thread(target=_run, daemon=True)
    t.start()



# ── Маршрутизация сообщений ────────────────────────────────────────
# В ВК нет callback-кнопок как в TG, поэтому ответы идут текстом: /1, /2, /3, /4
# Состояние сессии детектора хранится в _user_state[user_id]["detector"]


def _vk_detector_get_session(user_id: int) -> Optional[DetectorSession]:
    return _user_state.get(user_id, {}).get("detector")


def _vk_detector_set_session(user_id: int, session: Optional[DetectorSession]) -> None:
    state = _user_state.setdefault(user_id, {})
    state["detector"] = session


def _vk_detector_send_question(api, user_id: int) -> None:
    session = _vk_detector_get_session(user_id)
    if session is None:
        return
    q = DETECTOR_QUESTIONS[session.step]
    lines = [detector_format_question(q), "", "Ответьте числом 1-4:"]
    _send_message(api, user_id, "\n".join(lines))


def cmd_detector(api, user_id: int) -> None:
    """Показать интро и сбросить сессию."""
    _vk_detector_set_session(user_id, None)
    _send_message(api, user_id, detector_format_intro() + "\n\nНапишите /start_test чтобы начать.")


def cmd_detector_start(api, user_id: int) -> None:
    """Запустить квиз (отдельная команда, потому что в ВК /1..4 не команда бота)."""
    session = DetectorSession(user_id=user_id)
    _vk_detector_set_session(user_id, session)
    _vk_detector_send_question(api, user_id)


def cmd_detector_cancel(api, user_id: int) -> None:
    _vk_detector_set_session(user_id, None)
    _send_message(api, user_id, "Окей, отменила. Вернуться — /detector")


def cmd_detector_answer(api, user_id: int, choice: int) -> None:
    """Обработать ответ /1..4 в активной сессии."""
    if not (0 <= choice <= 3):
        _send_message(api, user_id, "⚠ Ответьте 1, 2, 3 или 4")
        return
    session = _vk_detector_get_session(user_id)
    if session is None:
        _send_message(api, user_id, "Сначала /detector, потом отвечайте")
        return
    q = DETECTOR_QUESTIONS[session.step]
    weight = q.options[choice][1]
    session.record(weight)
    if session.is_finished:
        verdict, imposed_pct = session.compute()
        _send_message(api, user_id, detector_format_result(verdict, imposed_pct))
        _send_message(
            api,
            user_id,
            "Пройти ещё раз: /detector\n"
            "Полный разбор от AI-коуча: https://app.pulab.ru/pricing/",
        )
        _vk_detector_set_session(user_id, None)
    else:
        _vk_detector_send_question(api, user_id)


def handle_message(api, user_id: int, text: str) -> None:
    """Главный диспетчер. Текст может быть командой или URL."""
    text = text.strip()
    if not text:
        return

    # Короткий ответ на детектор (/1..4) — если активна сессия
    if text in ("/1", "/2", "/3", "/4"):
        session = _vk_detector_get_session(user_id)
        if session is not None and not session.is_finished:
            cmd_detector_answer(api, user_id, int(text[1]) - 1)
            return
        # иначе — обычная команда

    # Команда?
    if text.startswith("/"):
        parts = text.split(maxsplit=1)
        cmd = parts[0].lower().split("@", 1)[0]  # /cmd@bot → /cmd
        args = parts[1] if len(parts) > 1 else ""
        route = {
            "/start": cmd_start,
            "/help": cmd_start,
            "/add": cmd_add,
            "/cancel": cmd_cancel,
            "/list": cmd_list,
            "/books": cmd_books_list,
            "/process": cmd_process,
            "/search": cmd_search,
            "/book": cmd_book,
            "/export": cmd_export,
            "/doctor": cmd_doctor,
            "/detector": cmd_detector,
            "/start_test": cmd_detector_start,
            "/detector_cancel": cmd_detector_cancel,
        }.get(cmd)
        if route is None:
            _send_message(api, user_id, f"❓ Неизвестная команда: {cmd}\n/help для списка")
            return
        # Маршруты с дополнительными аргументами
        if cmd in ("/add", "/list", "/search", "/book", "/export", "/books", "/process"):
            route(api, user_id, args)
        else:
            route(api, user_id)
        return

    # Свободный текст = URL?
    if text.startswith(("http://", "https://")):
        cmd_add(api, user_id, text)
        return

    _send_message(api, user_id, "ℹ️ Пришлите URL книги или /help")


# ── Точка входа ─────────────────────────────────────────────────────
def main() -> None:
    setup_logging()
    settings = get_settings()
    # Приоритет: settings → os.environ
    token = (
        settings.vk_group_token.strip()
        or os.environ.get("VK_GROUP_TOKEN", "").strip()
    )
    if not token:
        print(
            "❌ VK_GROUP_TOKEN не задан.\n"
            "Создайте сообщество VK → Настройки → Работа с API → Создать ключ.\n"
            "Включите: Long Poll API + Сообщения.\n"
            "Затем в .env:\n"
            "  VK_GROUP_TOKEN=vk1.a....\n"
            "  VK_GROUP_ID=123456789",
            file=sys.stderr,
        )
        sys.exit(1)

    try:
        api, vk_session = _vk_session(token)
    except Exception as e:
        print(f"❌ Не удалось подключиться к VK: {e}", file=sys.stderr)
        sys.exit(2)

    # Проверка: токен валидный? Группа доступна?
    try:
        group_info = api.groups.getById()
        gid = group_info[0]["id"] if group_info else 0
        gname = group_info[0]["name"] if group_info else "?"
        logger.info("✅ Подключен к сообществу: {} (id={})", gname, gid)
    except Exception as e:
        print(f"❌ Токен невалиден или сообщество недоступно: {e}", file=sys.stderr)
        sys.exit(3)

    # Long Poll
    # `wait=25` явно: иначе vk_api трактует 2-й позиционный аргумент как wait
    # и при `group_id=237295798` таймаут сокета переполняет timeval.
    longpoll = VkLongPoll(vk_session, wait=25, mode=234, group_id=gid)
    # ВАЖНО: Long Poll создаёт собственный `requests.Session` внутри
    # `vk_api`, у которого `trust_env=True` по умолчанию. Если в системе
    # задан SOCKS-прокси (WinINET/реестр), `requests` пытается его
    # использовать и падает с "Missing dependencies for SOCKS support".
    # Отключаем подхват системных прокси, если пользователь явно не задал
    # `VK_PROXY_URL` / `VK_NO_TRUST_ENV`.
    if not (settings.vk_proxy_url or os.environ.get("VK_PROXY_URL", "").strip()):
        longpoll.session.trust_env = False
        logger.debug("🔧 VK LongPoll: trust_env отключён")
    logger.info("🌐 VK-бот запущен (Long Poll, прокси={})",
                "✅" if settings.vk_proxy_url else "—")
    print(f"🤖 WishLibrarian VK Bot is running. Группа: {gname} (id={gid})")
    print("Нажмите Ctrl+C для остановки.")

    for event in longpoll.listen():
        if event.type != VkEventType.MESSAGE_NEW:
            continue
        if event.to_me:  # только входящие ЛС
            user_id = event.user_id
            text = event.text or ""
            logger.info("💬 {} → {}", user_id, text[:80])
            try:
                handle_message(api, user_id, text)
            except Exception as e:
                logger.exception("Ошибка обработки сообщения: {}", e)
                _send_message(api, user_id, f"💥 Ошибка: {e}")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n👋 Бот остановлен")
