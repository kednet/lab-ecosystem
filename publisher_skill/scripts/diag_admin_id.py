"""
diag_admin_id.py — диагностика TG_ADMIN_CHAT_ID.

Сканирует getUpdates, ищет последние сообщения от пользователей,
печатает их chat.id, username, имя, текст.

Запуск:
  python diag_admin_id.py
"""
import os
import sys
import ssl
import json
import urllib.request

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

TOKEN = os.environ.get("TG_BOT_TOKEN", "TG_BOT_TOKEN_REDACTED")
ENV_ADMIN = os.environ.get("TG_ADMIN_CHAT_ID", "779991878")
PROXY = os.environ.get("TELEGRAM_PROXY_URL", "socks5://oyqAWo:pSD478@212.102.145.155:9264")

api = f"https://api.telegram.org/bot{TOKEN}"

print(f"🔍 TG_ADMIN_CHAT_ID в .env: {ENV_ADMIN}")
print(f"🔍 Прокси: {PROXY}")
print()

# SOCKS5 opener
import socks  # PySocks

def _http_get_via_socks(url, proxy_url, timeout=15):
    """HTTP GET через SOCKS5 (PySocks + urllib)."""
    from urllib.parse import urlparse
    pu = urlparse(proxy_url)
    su = urlparse(url)
    sn = socks.socksocket()
    sn.set_proxy(
        socks.SOCKS5,
        pu.hostname,
        pu.port,
        username=pu.username,
        password=pu.password,
        rdns=True,
    )
    sn.settimeout(timeout)
    sn.connect((su.hostname, su.port or 443))
    if su.scheme == "https":
        sn = ctx.wrap_socket(sn, server_hostname=su.hostname)
    req = urllib.request.Request(url)
    r = urllib.request.urlopen(req, timeout=timeout, context=ctx)  # noqa
    return r

# Читаем последние 100 апдейтов
api_url = f"{api}/getUpdates?limit=100&timeout=5"
try:
    r = _http_get_via_socks(api_url, PROXY, timeout=20)
    data = json.loads(r.read().decode("utf-8"))
except Exception as e:
    print(f"❌ Ошибка getUpdates: {e}")
    sys.exit(1)

if not data.get("ok"):
    print(f"❌ Telegram ответил: {data}")
    sys.exit(1)

updates = data.get("result", [])
print(f"📥 Получено апдейтов: {len(updates)}")
print()

if not updates:
    print("⚠ Нет ни одного апдейта. Напиши боту @WLPostingbot что-нибудь (хоть /start),")
    print("  и снова запусти скрипт через 5 секунд.")
    sys.exit(0)

# Собираем уникальных пользователей, которые писали боту
users = {}
for u in updates:
    msg = u.get("message") or u.get("edited_message")
    if not msg:
        continue
    chat = msg.get("chat", {})
    chat_id = chat.get("id")
    if chat.get("type") != "private":
        continue
    users[chat_id] = {
        "id": chat_id,
        "username": chat.get("username", "—"),
        "first_name": chat.get("first_name", ""),
        "last_name": chat.get("last_name", ""),
        "last_text": msg.get("text", "")[:60],
        "last_date": msg.get("date"),
    }

if not users:
    print("⚠ Не нашёл ни одного личного сообщения боту в последних 100 апдейтах.")
    print("  Напиши @WLPostingbot что-нибудь (хоть /start) и перезапусти.")
    sys.exit(0)

print("👤 Кто писал @WLPostingbot в личку (последние 100 апдейтов):\n")
for u in users.values():
    from datetime import datetime
    dt = datetime.fromtimestamp(u["last_date"]).strftime("%Y-%m-%d %H:%M:%S") if u["last_date"] else "—"
    name = (u["first_name"] + " " + u["last_name"]).strip() or "—"
    marker = " ← совпадает с .env" if str(u["id"]) == str(ENV_ADMIN) else ""
    print(f"  • chat.id = {u['id']:>15}  username: @{u['username']:<20}  имя: {name}{marker}")
    print(f"    последнее: «{u['last_text']}»  ({dt})")
    print()

# Сводка
if str(ENV_ADMIN) in [str(u["id"]) for u in users.values()]:
    print("✅ Всё ок: твой chat.id есть в списке и совпадает с .env")
    print("   Проблема в чём-то другом (например, ты писала с другого аккаунта).")
else:
    print(f"❌ Твой chat.id ({ENV_ADMIN}) НЕ найден среди тех, кто писал боту в личку.")
    print()
    print("   Варианты:")
    print("   1) Ты писала боту с ДРУГОГО аккаунта (не с @kednet).")
    print(f"      Тогда в .env TG_ADMIN_CHAT_ID надо поменять на: {list(users.keys())[-1]}")
    print(f"   2) Ты писала не в личку, а в группу/канал (там другой chat.id).")
    print(f"   3) Бот писал тебе, а ты ему — нет. Просто напиши ему /start и перезапусти.")
