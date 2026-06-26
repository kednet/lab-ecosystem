"""
diag_admin_id_aiogram.py — диагностика TG_ADMIN_CHAT_ID через aiogram.
Слушает 1 update и завершается.
"""
import asyncio
import os
import sys
from aiogram import Bot, Dispatcher, F
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.types import Message

TOKEN = os.environ.get("TG_BOT_TOKEN", "TG_BOT_TOKEN_REDACTED")
ENV_ADMIN = os.environ.get("TG_ADMIN_CHAT_ID", "779991878")
PROXY = os.environ.get("TELEGRAM_PROXY_URL", "socks5://oyqAWo:pSD478@212.102.145.155:9264")

print(f"chat_id в .env: {ENV_ADMIN}")
print(f"Прокси: {PROXY}")
print()
print("Жду следующее сообщение от ЛЮБОГО пользователя в личку боту...")
print("(напиши @WLPostingbot что-нибудь с того аккаунта, который должен быть админом)")
print()

received = []

async def handle(message: Message):
    if message.chat.type != "private":
        return
    u = message.from_user
    print(f"\n✅ Получил от: chat.id={message.chat.id}  username=@{u.username if u else '—'}  имя={u.first_name if u else '—'}")
    print(f"   текст: «{message.text}»")
    if str(message.chat.id) == str(ENV_ADMIN):
        print(f"   ✅ Совпадает с TG_ADMIN_CHAT_ID в .env — всё ок")
    else:
        print(f"   ❌ НЕ совпадает с TG_ADMIN_CHAT_ID в .env ({ENV_ADMIN})")
        print(f"   → Впиши в .env: TG_ADMIN_CHAT_ID={message.chat.id}")
    received.append(message)
    await message.answer(
        f"🔍 Диагностика: твой chat.id = {message.chat.id}\n"
        f"В .env: {ENV_ADMIN}\n"
        + ("Совпадает ✓" if str(message.chat.id) == str(ENV_ADMIN) else f"НЕ совпадает. Поправь .env: TG_ADMIN_CHAT_ID={message.chat.id}")
    )

async def main():
    session = AiohttpSession(proxy=PROXY)
    bot = Bot(token=TOKEN, session=session)
    dp = Dispatcher()
    dp.message.register(handle, F.text)

    try:
        # Слушаем 1 сообщение максимум 60 секунд
        polling_task = asyncio.create_task(dp.start_polling(bot, allowed_updates=["message"]))
        await asyncio.wait_for(received.append if False else asyncio.sleep(60), timeout=60)
        if not received:
            print("⏱ Таймаут 60с — никто не написал. Перезапусти и напиши боту.")
        polling_task.cancel()
    finally:
        await bot.session.close()

if __name__ == "__main__":
    asyncio.run(main())
