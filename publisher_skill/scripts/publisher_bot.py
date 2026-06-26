"""
publisher_bot.py — бот-модератор @WLPostingbot для приватного канала.

Слушает Telegram Bot API через long polling. Принимает команды и inline-кнопки.
При нажатии ✅ Одобрить / ✏️ Править / ❌ Отклонить — обрабатывает
соответствующий pending-пост и публикует (или отклоняет) в приватный канал.

Запуск:
  python publisher_bot.py

Через systemd: /etc/systemd/system/wl-tg-posting.service
"""
from __future__ import annotations

import asyncio
import os
import re
import ssl
import sys
import urllib.parse
import urllib.request
import json
from pathlib import Path

# Windows console fix
try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

# Загрузить .env (publisher_skill/.env)
SKILL_ROOT = Path(__file__).resolve().parent.parent
ENV_PATH = SKILL_ROOT / ".env"

def load_env():
    if not ENV_PATH.exists():
        return
    for line in ENV_PATH.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        v = v.split("#", 1)[0].strip()  # отрезаем инлайн-комментарий «# ...»
        os.environ.setdefault(k.strip(), v)

load_env()

sys.path.insert(0, str(Path(__file__).resolve().parent))
import pending_store  # noqa: E402

# aiogram
from aiogram import Bot, Dispatcher, F
from aiogram.client.default import DefaultBotProperties
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.enums import ParseMode
from aiogram.filters import Command
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)

# MITM-bypass (если есть)
ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

# ── Конфиг ─────────────────────────────────────────────────────────
TOKEN = os.environ.get("TG_BOT_TOKEN", "").strip()
ADMIN_CHAT_ID = os.environ.get("TG_ADMIN_CHAT_ID", "").strip()
PRIVATE_CHANNEL_ID = os.environ.get("TG_CHANNEL_PRIVATE_ID", "").strip()
PROXY_URL = os.environ.get("TELEGRAM_PROXY_URL", "").strip()

if not TOKEN:
    sys.exit("❌ TG_BOT_TOKEN не задан в .env")
if not ADMIN_CHAT_ID:
    sys.exit("❌ TG_ADMIN_CHAT_ID не задан в .env")
if not PRIVATE_CHANNEL_ID:
    sys.exit("❌ TG_CHANNEL_PRIVATE_ID не задан в .env")


# ── Команды ────────────────────────────────────────────────────────

async def cmd_start(message: Message) -> None:
    """Приветствие для админа."""
    if str(message.chat.id) != ADMIN_CHAT_ID:
        # Чужой — отвечаем нейтрально
        await message.answer(
            "Я бот-модератор Лаборатории желаний. "
            "Если у тебя есть права админа — напиши @kednet.",
        )
        return
    pending_count = len(pending_store.list_pending())
    text = (
        "👋 <b>Привет!</b>\n\n"
        "Я бот-модератор @WLPostingbot для приватного канала "
        "«Лаборатория желаний pulab.ru».\n\n"
        f"📋 В очереди на модерацию: <b>{pending_count}</b> пост(а/ов)\n\n"
        "<b>Команды:</b>\n"
        "/pending — список постов в очереди\n"
        "/help — подробная справка\n\n"
        "Когда ты получаешь превью с inline-кнопками — нажми одну из них:\n"
        "✅ Одобрить — пост уходит в приватный канал\n"
        "✏️ Править — напиши мне новый текст, я применю правки\n"
        "❌ Отклонить — отмена, в канал не идёт"
    )
    await message.answer(text, parse_mode=ParseMode.HTML)


async def cmd_pending(message: Message) -> None:
    """Список pending-постов."""
    if str(message.chat.id) != ADMIN_CHAT_ID:
        return
    pending = pending_store.list_pending()
    if not pending:
        await message.answer("📋 Очередь пуста — модерация не требуется.")
        return
    lines = [f"📋 <b>В очереди: {len(pending)}</b>\n"]
    for p in pending:
        title = p.get("source_title", "—")[:80]
        ts = p.get("created_at", "")[:19].replace("T", " ")
        lines.append(f"• <code>{p['id']}</code> — {title} ({ts})")
    await message.answer("\n".join(lines), parse_mode=ParseMode.HTML)


async def cmd_help(message: Message) -> None:
    if str(message.chat.id) != ADMIN_CHAT_ID:
        return
    await message.answer(
        "🛠 <b>Справка по модератору</b>\n\n"
        "<b>Команды:</b>\n"
        "/start — приветствие\n"
        "/pending — список постов в очереди\n"
        "/help — эта справка\n\n"
        "<b>Inline-кнопки на превью:</b>\n"
        "✅ <b>Одобрить</b> — пост публикуется в приватный канал как есть\n"
        "✏️ <b>Править</b> — я жду твоё следующее сообщение, оно заменит текст поста. "
        "Затем покажу обновлённое превью с кнопками заново\n"
        "❌ <b>Отклонить</b> — отмена, в канал не идёт\n\n"
        "<b>Сценарий публикации:</b>\n"
        "1. На локалке: <code>python post_channels.py --content detector --channels tg,private</code>\n"
        "2. В публичный @pulabru пост уходит сразу\n"
        "3. В личку прилетает превью с кнопками\n"
        "4. Ты нажимаешь ✅/✏️/❌\n"
        "5. Пост уходит (или не уходит) в приватный",
        parse_mode=ParseMode.HTML,
    )


# ── Обработка inline-кнопок ────────────────────────────────────────

# Хранилище «что бот ждёт от пользователя»: post_id → "edit"
PENDING_EDIT: dict[str, str] = {}


async def cb_approve(callback: CallbackQuery) -> None:
    if str(callback.message.chat.id) != ADMIN_CHAT_ID:
        await callback.answer("⛔ Не для тебя", show_alert=True)
        return
    post_id = callback.data.split(":", 2)[2]
    pending = pending_store.get(post_id)
    if not pending:
        await callback.answer("⚠ Пост не найден (возможно, уже отмодерирован)", show_alert=True)
        return
    if pending["status"] != "pending":
        await callback.answer(f"⚠ Этот пост уже в статусе: {pending['status']}", show_alert=True)
        return

    # Публикуем в канал
    text = pending.get("edited_text") or pending["text"]
    image_path = pending.get("image_path")
    ok, info = await _publish_to_private(callback.bot, text, image_path)

    if ok:
        pending_store.update(post_id, status="approved")
        await callback.message.edit_text(
            f"✅ <b>Опубликовано</b> в приватный канал (msg_id={info})\n\n"
            f"<i>post_id: {post_id}</i>",
            parse_mode=ParseMode.HTML,
        )
        await callback.answer("Опубликовано ✓")
    else:
        await callback.message.edit_text(
            f"❌ <b>Ошибка публикации</b>\n\n{info}\n\n<i>post_id: {post_id}</i>",
            parse_mode=ParseMode.HTML,
        )
        await callback.answer("Ошибка", show_alert=True)


async def cb_edit(callback: CallbackQuery) -> None:
    if str(callback.message.chat.id) != ADMIN_CHAT_ID:
        await callback.answer("⛔ Не для тебя", show_alert=True)
        return
    post_id = callback.data.split(":", 2)[2]
    pending = pending_store.get(post_id)
    if not pending:
        await callback.answer("⚠ Пост не найден", show_alert=True)
        return
    if pending["status"] != "pending":
        await callback.answer(f"⚠ Этот пост уже в статусе: {pending['status']}", show_alert=True)
        return

    PENDING_EDIT[post_id] = "edit"
    await callback.message.edit_text(
        f"✏️ <b>Режим правки</b>\n\n"
        f"Пришли мне новый текст для этого поста (можно в HTML — поддерживаю).\n"
        f"Я заменю оригинал и покажу обновлённое превью с кнопками.\n\n"
        f"<i>post_id: {post_id}</i>\n"
        f"⏳ Жду твоё сообщение…",
        parse_mode=ParseMode.HTML,
    )
    await callback.answer("Жду новый текст")


async def cb_reject(callback: CallbackQuery) -> None:
    if str(callback.message.chat.id) != ADMIN_CHAT_ID:
        await callback.answer("⛔ Не для тебя", show_alert=True)
        return
    post_id = callback.data.split(":", 2)[2]
    pending = pending_store.get(post_id)
    if not pending:
        await callback.answer("⚠ Пост не найден", show_alert=True)
        return

    pending_store.update(post_id, status="rejected")
    await callback.message.edit_text(
        f"❌ <b>Отклонено</b>\n\n<i>post_id: {post_id}</i>",
        parse_mode=ParseMode.HTML,
    )
    await callback.answer("Отклонено")
    # Удаляем файл через 5 секунд (чтобы можно было посмотреть что отклонил)
    await asyncio.sleep(5)
    pending_store.delete(post_id)


# ── Приём правки текста ────────────────────────────────────────────

async def handle_edit_text(message: Message) -> None:
    """Если пользователь в режиме правки — принимаем новый текст."""
    if str(message.chat.id) != ADMIN_CHAT_ID:
        return
    if not PENDING_EDIT:
        return
    # Берём самый «свежий» ожидающий
    post_id = next(iter(PENDING_EDIT))
    del PENDING_EDIT[post_id]

    pending = pending_store.get(post_id)
    if not pending:
        await message.answer("⚠ Пост не найден")
        return

    new_text = message.text or message.caption or ""
    if not new_text.strip():
        await message.answer("⚠ Пустой текст, отмена правки")
        return

    pending_store.update(post_id, edited_text=new_text, status="pending")

    # Показываем обновлённое превью
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Одобрить",  callback_data=f"moderate:approve:{post_id}"),
            InlineKeyboardButton(text="✏️ Править",  callback_data=f"moderate:edit:{post_id}"),
        ],
        [
            InlineKeyboardButton(text="❌ Отклонить", callback_data=f"moderate:reject:{post_id}"),
        ],
    ])
    preview = (
        f"📋 <b>ПРЕВЬЮ (с правкой)</b>\n"
        f"<i>post_id: {post_id}</i>\n"
        f"{'━' * 30}\n\n"
        f"{new_text[:3500]}"
    )
    await message.answer(preview, parse_mode=ParseMode.HTML, reply_markup=keyboard)


# ── Публикация в приватный канал ───────────────────────────────────

async def _publish_to_private(bot: Bot, text: str, image_path: str | None) -> tuple[bool, str | int]:
    """Опубликовать в приватный канал. Возвращает (ok, msg_id_or_error).
    Использует aiogram-сессию бота (с SOCKS5 прокси), а не urllib — иначе
    на VPS РФ-блокировка api.telegram.org роняет отправку.
    """
    try:
        if image_path and Path(image_path).exists():
            from aiogram.types import InputFile
            photo = InputFile(image_path, filename="image.jpg")
            sent = await bot.send_photo(
                chat_id=PRIVATE_CHANNEL_ID,
                photo=photo,
                caption=text[:1024],
                parse_mode=ParseMode.HTML,
            )
        else:
            sent = await bot.send_message(
                chat_id=PRIVATE_CHANNEL_ID,
                text=text[:4096],
                parse_mode=ParseMode.HTML,
                disable_web_page_preview=False,
            )
        return True, sent.message_id
    except Exception as e:
        # Экранируем HTML в тексте ошибки, чтобы edit_text не упал на парсинге тегов
        import html as _html
        safe = _html.escape(f"{type(e).__name__}: {e}")
        return False, safe


def _sync_urlopen(req, timeout):
    """Синхронный urlopen в отдельном потоке. Больше не используется —
    оставлено на случай возврата к urllib."""
    return urllib.request.urlopen(req, context=ctx, timeout=timeout).read()


# ── Точка входа ─────────────────────────────────────────────────────

async def main() -> None:
    if PROXY_URL:
        session = AiohttpSession(proxy=PROXY_URL)
        bot = Bot(token=TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML), session=session)
        print(f"🤖 @WLPostingbot: прокси={PROXY_URL}")
    else:
        bot = Bot(token=TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
        print("🤖 @WLPostingbot: без прокси")

    dp = Dispatcher()
    dp.message.register(cmd_start, Command("start", "help"))
    dp.message.register(cmd_pending, Command("pending"))
    dp.message.register(cmd_help, Command("help"))
    dp.message.register(handle_edit_text, F.text)

    dp.callback_query.register(cb_approve, F.data.startswith("moderate:approve:"))
    dp.callback_query.register(cb_edit,    F.data.startswith("moderate:edit:"))
    dp.callback_query.register(cb_reject,  F.data.startswith("moderate:reject:"))

    print("📋 Запущен. Жду превью для модерации. Ctrl+C для остановки.")
    await dp.start_polling(bot)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        print("\n👋 Бот остановлен")