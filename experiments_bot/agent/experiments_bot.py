"""
experiments_bot: Telegram-бот «Поделиться экспериментом» для Лаборатории желаний.

Стратегия community-first: читатели = главные герои, бот — ещё один канал сбора историй
помимо /my-experiment/ формы.

Сценарий (FSM, 5 шагов):
  1. /start         → приветствие + кнопка «🧪 Поделиться экспериментом»
  2. Имя/псевдоним  → текст или «Пропустить»
  3. Откуда идея    → текст или «Пропустить» (книга, подкаст, разговор, ситуация, что угодно)
  4. Что пробовали  → текст 30..1000 знаков
  5. Что получилось → текст 30..1000 знаков
  6. Согласие       → «Опубликовать» / «Не публиковать»
  → POST /api/experiments на API Лаборатории → ответ с ID

Запуск:
    python -m agent.experiments_bot
"""
from __future__ import annotations

import asyncio
import logging
import os
import sys
from pathlib import Path
from typing import Optional

# Windows UTF-8 fix (для локального теста)
try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

# Загружаем .env ДО первого импорта aiogram/aiogram.client
try:
    from dotenv import load_dotenv
    _PROJECT_ROOT = Path(__file__).resolve().parent.parent
    load_dotenv(_PROJECT_ROOT / ".env", override=False)
except ImportError:
    pass

import aiohttp
from aiogram import Bot, Dispatcher, F
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)


# ── Конфиг ──────────────────────────────────────────────────────────
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
TELEGRAM_PROXY_URL = os.environ.get("TELEGRAM_PROXY_URL", "").strip()
TELEGRAM_PROXY_URL_BACKUP = os.environ.get("TELEGRAM_PROXY_URL_BACKUP", "").strip()
PROXY_FAILOVER_THRESHOLD = int(os.environ.get("PROXY_FAILOVER_THRESHOLD", "3"))
EXPERIMENTS_API_URL = os.environ.get("EXPERIMENTS_API_URL", "https://api.pulab.online").rstrip("/")
BOOKS_API_URL = os.environ.get("BOOKS_API_URL", "https://app.pulab.ru").rstrip("/")
LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO").upper()

# Community-first: человек может делиться ЛЮБЫМ опытом — книга, подкаст,
# жизненная ситуация, разговор, своя мысль. Каталог книг больше не ограничивает.

DID_MIN, DID_MAX = 30, 1000
GOT_MIN, GOT_MAX = 30, 1000
NAME_MAX = 60
SOURCE_MAX = 200  # откуда идея (книга, подкаст, жизнь, что угодно)

# ── Логирование ─────────────────────────────────────────────────────
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL, logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("experiments_bot")


# ── FSM ─────────────────────────────────────────────────────────────
class ExperimentForm(StatesGroup):
    name = State()        # опц.
    source = State()      # опц. — откуда идея (книга, подкаст, жизнь, что угодно)
    did = State()         # что пробовали
    got = State()         # что получилось
    publish = State()     # согласие на публикацию


# ── Клавиатуры ──────────────────────────────────────────────────────
def kb_start() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🧪 Поделиться экспериментом", callback_data="exp:start")],
        [InlineKeyboardButton(text="🧪 К подборкам", url=f"{BOOKS_API_URL}/experiments/")],
    ])


def kb_skip_name() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⏭ Пропустить", callback_data="exp:skip_name")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data="exp:cancel")],
    ])


def kb_skip_source() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⏭ Пропустить", callback_data="exp:skip_source")],
        [InlineKeyboardButton(text="❌ Отмена", callback_data="exp:cancel")],
    ])


def kb_publish() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Опубликовать", callback_data="exp:pub:yes"),
            InlineKeyboardButton(text="⛔ Не публиковать", callback_data="exp:pub:no"),
        ],
        [InlineKeyboardButton(text="❌ Отмена", callback_data="exp:cancel")],
    ])


def kb_done() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🧪 К подборкам", url=f"{BOOKS_API_URL}/experiments/")],
        [InlineKeyboardButton(text="✏️ Ещё один эксперимент", callback_data="exp:start")],
    ])


# ── API клиент ──────────────────────────────────────────────────────
async def submit_experiment(payload: dict) -> tuple[bool, str]:
    """POST на /api/experiments. Возвращает (ok, message_or_id)."""
    url = f"{EXPERIMENTS_API_URL}/api/experiments"
    try:
        timeout = aiohttp.ClientTimeout(total=20)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.post(url, json=payload) as r:
                if r.status == 200:
                    data = await r.json()
                    return True, data.get("id", "")
                # API вернул ошибку
                try:
                    err = await r.json()
                    msg = err.get("message", f"HTTP {r.status}")
                except Exception:
                    msg = f"HTTP {r.status}"
                return False, msg
    except aiohttp.ClientError as e:
        logger.error("submit_experiment network error: %s", e)
        return False, "Не удалось связаться с сервером. Попробуйте позже."
    except Exception as e:
        logger.exception("submit_experiment unexpected error")
        return False, f"Ошибка: {e}"


# ── Хендлеры ────────────────────────────────────────────────────────
WELCOME = (
    "👋 <b>Привет! Это бот «Лаборатории желаний».</b>\n\n"
    "Здесь можно поделиться тем, что вы попробовали в жизни — "
    "<i>из любой книги, подкаста, или просто ситуации</i>.\n\n"
    "Получилось или нет — неважно, важен сам опыт.\n\n"
    "Лучшие истории попадают в ежемесячную подборку на сайте.\n"
    "Формат: <b>5 коротких шагов</b>, 2–3 минуты."
)

HELP = (
    "ℹ️ <b>Как пользоваться</b>\n\n"
    "1. Жмите <b>«🧪 Поделиться экспериментом»</b>\n"
    "2. Укажите имя (или пропустите) → откуда идея (или пропустите)\n"
    "3. Расскажите, что пробовали и что получилось\n"
    "4. Решите, можно ли публиковать\n\n"
    "Все данные уходят на сайт <code>app.pulab.ru</code> "
    "и попадают админу сообщества. Без спама, без рассылок."
)


async def cmd_start(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer(
        WELCOME,
        parse_mode=ParseMode.HTML,
        reply_markup=kb_start(),
    )


async def cmd_help(message: Message) -> None:
    await message.answer(HELP, parse_mode=ParseMode.HTML)


async def cb_cancel(call: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await call.message.edit_text("❌ Отменено. Если захотите — нажмите /start.")
    await call.answer()


async def cb_start_form(call: CallbackQuery, state: FSMContext) -> None:
    """Старт сценария: спрашиваем имя."""
    await state.set_state(ExperimentForm.name)
    await call.message.edit_text(
        "Как вас подписать в истории?\n"
        "Можно имя, ник, или оставить пустым.",
        reply_markup=kb_skip_name(),
    )
    await call.answer()


async def cb_skip_name(call: CallbackQuery, state: FSMContext) -> None:
    """Имя пропущено → спрашиваем источник идеи."""
    await state.update_data(name="")
    await state.set_state(ExperimentForm.source)
    await call.message.edit_text(
        "💡 <b>Откуда идея?</b>\n\n"
        "Книга, подкаст, разговор, жизненная ситуация, "
        "собственная мысль — что угодно. Можно пропустить.",
        parse_mode=ParseMode.HTML,
        reply_markup=kb_skip_source(),
    )
    await call.answer()


async def cb_skip_source(call: CallbackQuery, state: FSMContext) -> None:
    """Источник пропущен → переход к «что пробовали»."""
    await state.update_data(source="")
    await state.set_state(ExperimentForm.did)
    await call.message.edit_text(
        "🧪 <b>Что вы пробовали?</b>\n\n"
        f"Коротко, что именно делали. От {DID_MIN} до {DID_MAX} знаков.\n\n"
        f"<i>Например: «попробовала технику 5 почему на желании сменить работу».</i>",
        parse_mode=ParseMode.HTML,
    )
    await call.answer()


async def fsm_name(message: Message, state: FSMContext) -> None:
    """FSM: получили имя → спрашиваем источник идеи."""
    name = (message.text or "").strip()[:NAME_MAX]
    await state.update_data(name=name)
    await state.set_state(ExperimentForm.source)
    await message.answer(
        f"👤 <b>{name or 'участник сообщества'}</b>, спасибо!\n\n"
        f"💡 <b>Откуда идея?</b>\n\n"
        f"Книга, подкаст, разговор, жизненная ситуация, "
        f"собственная мысль — что угодно. До {SOURCE_MAX} знаков, можно пропустить.",
        parse_mode=ParseMode.HTML,
        reply_markup=kb_skip_source(),
    )


async def fsm_source(message: Message, state: FSMContext) -> None:
    """FSM: получили источник идеи → переход к «что пробовали»."""
    text = (message.text or "").strip()[:SOURCE_MAX]
    await state.update_data(source=text)
    await state.set_state(ExperimentForm.did)
    source_label = f"💡 <b>{text}</b>\n\n" if text else ""
    await message.answer(
        f"{source_label}🧪 <b>Что вы пробовали?</b>\n\n"
        f"Коротко, что именно делали. От {DID_MIN} до {DID_MAX} знаков.\n\n"
        f"<i>Например: «попробовала технику 5 почему на желании сменить работу».</i>",
        parse_mode=ParseMode.HTML,
    )


async def fsm_did(message: Message, state: FSMContext) -> None:
    """FSM: получили «что пробовали» → переход к «что получилось»."""
    text = (message.text or "").strip()
    if len(text) < DID_MIN:
        await message.answer(
            f"Слишком коротко — минимум {DID_MIN} знаков. "
            f"Сейчас {len(text)}. Расскажите чуть подробнее."
        )
        return
    if len(text) > DID_MAX:
        await message.answer(f"Слишком длинно — максимум {DID_MAX} знаков. Сократите, пожалуйста.")
        return
    await state.update_data(did=text)
    await state.set_state(ExperimentForm.got)
    await message.answer(
        f"✅ Принято ({len(text)} знаков).\n\n"
        f"📝 <b>Что получилось?</b>\n"
        f"Честно: успех, провал, «ничего», «удивило». От {GOT_MIN} до {GOT_MAX} знаков.",
        parse_mode=ParseMode.HTML,
    )


async def fsm_got(message: Message, state: FSMContext) -> None:
    """FSM: получили «что получилось» → переход к согласию."""
    text = (message.text or "").strip()
    if len(text) < GOT_MIN:
        await message.answer(
            f"Слишком коротко — минимум {GOT_MIN} знаков. "
            f"Сейчас {len(text)}. Расскажите чуть подробнее."
        )
        return
    if len(text) > GOT_MAX:
        await message.answer(f"Слишком длинно — максимум {GOT_MAX} знаков. Сократите, пожалуйста.")
        return
    await state.update_data(got=text)
    await state.set_state(ExperimentForm.publish)
    await message.answer(
        f"✅ Принято ({len(text)} знаков).\n\n"
        f"📢 <b>Можно ли публиковать?</b>\n\n"
        f"Если «✅ Опубликовать» — история попадёт в подборку на "
        f"<code>{BOOKS_API_URL}/experiments/</code> и в каналы сообщества (ВК, Telegram).\n"
        f"Если «⛔ Не публиковать» — её увижу только я.",
        parse_mode=ParseMode.HTML,
        reply_markup=kb_publish(),
    )


async def cb_publish(call: CallbackQuery, state: FSMContext) -> None:
    """FSM: согласие → отправка в API."""
    allow_publish = call.data.endswith(":yes")
    await state.update_data(allow_publish=allow_publish)

    data = await state.get_data()
    await call.message.edit_text("⏳ Отправляю на сервер…")
    await call.answer()

    payload = {
        "name": data.get("name", ""),
        "source": data.get("source", ""),
        "did": data.get("did", ""),
        "got": data.get("got", ""),
        "allowPublish": allow_publish,
    }

    ok, result = await submit_experiment(payload)

    if ok:
        exp_id = result
        await call.message.edit_text(
            f"🎉 <b>Спасибо!</b> Эксперимент #{exp_id} сохранён.\n\n"
            f"{'✅ Будет опубликован' if allow_publish else '⛔ Только для админа'} — "
            f"Лаборатория увидит вашу историю.\n\n"
            f"Если захотите — на сайте уже есть подборки:",
            parse_mode=ParseMode.HTML,
            reply_markup=kb_done(),
        )
        logger.info(
            "experiment submitted: id=%s user=%s source=%s allow_publish=%s",
            exp_id, payload["name"], payload["source"], allow_publish,
        )
    else:
        await call.message.edit_text(
            f"❌ <b>Не получилось отправить.</b>\n\n{result}\n\n"
            f"Попробуйте ещё раз через /start",
            parse_mode=ParseMode.HTML,
        )
        logger.warning("experiment submit failed: %s", result)

    await state.clear()


# ── Failover: авто-переключение primary → backup SOCKS5 ───────────
from aiogram.exceptions import TelegramNetworkError, TelegramRetryAfter

# Сетевые ошибки, при которых считаем сбой прокси
_FAILOVER_NETWORK_ERRORS = (
    TelegramNetworkError,
    TelegramRetryAfter,
    aiohttp.ClientError,
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
      • возврата на primary НЕТ (избегаем ping-pong)
    """
    consecutive_failures = 0
    switched = False  # чтобы не переключаться повторно

    while True:
        try:
            logger.info(
                "📡 Polling start (proxy=%s)",
                backup_proxy if switched else primary_proxy or "—",
            )
            await dp.start_polling(bot, handle_signals=False)
            return
        except _FAILOVER_NETWORK_ERRORS as e:
            consecutive_failures += 1
            err_short = type(e).__name__ + ": " + str(e)[:120]
            logger.warning(
                "⚠️ Сетевая ошибка #%s/%s: %s",
                consecutive_failures, threshold, err_short,
            )

            should_switch = (
                not switched
                and backup_proxy
                and backup_proxy.strip()
                and consecutive_failures >= threshold
            )

            if should_switch:
                logger.warning(
                    "🔁 Переключаюсь с primary на BACKUP-прокси: %s",
                    backup_proxy,
                )
                try:
                    await bot.session.close()
                except Exception:
                    pass
                switched = True
                consecutive_failures = 0
                from aiogram.client.session.aiohttp import AiohttpSession
                bot.session = AiohttpSession(proxy=backup_proxy.strip())
                await asyncio.sleep(2)
                continue

            backoff = min(30, 2 ** consecutive_failures)
            logger.info("⏳ Retry через %s сек", backoff)
            await asyncio.sleep(backoff)
            continue


# ── Точка входа ─────────────────────────────────────────────────────
async def main() -> None:
    if not TELEGRAM_BOT_TOKEN:
        print("[FATAL] TELEGRAM_BOT_TOKEN is empty. Set it in .env or env vars.", file=sys.stderr)
        sys.exit(1)

    session: Optional[AiohttpSession] = None
    if TELEGRAM_PROXY_URL:
        # aiohttp-socks уже в requirements.txt — AiohttpSession сам разберётся с SOCKS5
        session = AiohttpSession(proxy=TELEGRAM_PROXY_URL)
        safe = TELEGRAM_PROXY_URL.split("@")[-1] if "@" in TELEGRAM_PROXY_URL else TELEGRAM_PROXY_URL
        logger.info("Using proxy: %s", safe)
    else:
        logger.warning("No TELEGRAM_PROXY_URL — direct connection (won't work from RU)")

    bot = Bot(
        token=TELEGRAM_BOT_TOKEN,
        session=session,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = Dispatcher()

    # Команды
    dp.message.register(cmd_start, Command("start"))
    dp.message.register(cmd_help, Command("help"))

    # FSM (порядок важен — обработчики без состояния должны быть ПОСЛЕ)
    dp.message.register(fsm_name, ExperimentForm.name)
    dp.message.register(fsm_source, ExperimentForm.source)
    dp.message.register(fsm_did, ExperimentForm.did)
    dp.message.register(fsm_got, ExperimentForm.got)

    # Callback-кнопки
    dp.callback_query.register(cb_start_form, F.data == "exp:start")
    dp.callback_query.register(cb_cancel, F.data == "exp:cancel")
    dp.callback_query.register(cb_skip_name, F.data == "exp:skip_name")
    dp.callback_query.register(cb_skip_source, F.data == "exp:skip_source")
    dp.callback_query.register(cb_publish, F.data.startswith("exp:pub:"))

    logger.info(
        "experiments_bot starting (api=%s, books=%s, proxy_primary=%s, proxy_backup=%s, threshold=%s)",
        EXPERIMENTS_API_URL, BOOKS_API_URL,
        TELEGRAM_PROXY_URL or "—",
        TELEGRAM_PROXY_URL_BACKUP or "—",
        PROXY_FAILOVER_THRESHOLD,
    )
    try:
        await _start_polling_with_failover(
            bot=bot,
            dp=dp,
            primary_proxy=TELEGRAM_PROXY_URL,
            backup_proxy=TELEGRAM_PROXY_URL_BACKUP,
            threshold=PROXY_FAILOVER_THRESHOLD,
        )
    finally:
        await bot.session.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("experiments_bot stopped")
