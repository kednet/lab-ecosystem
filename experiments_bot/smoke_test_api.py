"""
Smoke-тест experiments_bot API-клиента.

Имитирует финальный шаг FSM (`cb_publish`) — собирает payload из «грязных» данных
(с эмодзи, `&`-символами, кавычками, переводами строк, длинными текстами) и
шлёт в /api/experiments. Печатает ID + проверяет, что текст на сервере
(через /api/experiments с токеном) совпадает байт-в-байт.

Запуск:
    python smoke_test_api.py

Зачем:
    • Подтверждает, что aiogram-код (который мы тестируем) корректно работает с API.
    • Ловит 2 типа багов до прода:
        1. Mojibake — Windows cp1252/curl-конвертация ломает UTF-8 → пишем явно.
        2. HTML/JSON escape — `&`, `<`, `>` в тексте не должны ломать JSON.

Без зависимостей от TG: вызываем напрямую submit_experiment().
"""
import asyncio
import os
import sys
from pathlib import Path

# ── Setup ────────────────────────────────────────────────────────────
sys.path.insert(0, str(Path(__file__).resolve().parent))

# Загружаем .env (если есть), но не валимся — для теста нам нужен только API URL
try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).resolve().parent / ".env", override=False)
except ImportError:
    pass

from agent.experiments_bot import submit_experiment  # noqa: E402

API_URL = os.environ.get("EXPERIMENTS_API_URL", "https://api.pulab.online").rstrip("/")
ADMIN_TOKEN = os.environ.get("ADMIN_TOKEN", "").strip()


async def fetch_record(rec_id: str) -> dict:
    """GET /api/experiments/:id (с токеном) — чтобы сверить, что прислал бот."""
    import aiohttp
    url = f"{API_URL}/api/experiments"
    headers = {"X-Admin-Token": ADMIN_TOKEN}
    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers=headers) as r:
            data = await r.json()
            for item in data.get("items", []):
                if item["id"] == rec_id:
                    return item
            return {}


async def main():
    print(f"[smoke] API = {API_URL}")
    print(f"[smoke] ADMIN_TOKEN set = {bool(ADMIN_TOKEN)}")

    # Грязные данные — проверяем, что не сломаются
    payload = {
        "name": "Анна-Тест",
        "source": "Книга «Золотая ветка» & подкаст 🎙",
        "did": (
            "Каждое утро 30 дней писала в блокнот 3 благодарности. "
            "Без & и <html> спецсимволов, с эмодзи ✨ и переносами:\n"
            "строка1\nстрока2\nстрока3. И ещё кавычки «ёлочки»."
        ),
        "got": "Через 2 недели стало меньше тревоги. Лучший эффект — высыпаюсь.",
        "allowPublish": False,  # спам-проверка: модератору видно, на ленту НЕ идёт
    }

    print("[smoke] Submitting…")
    ok, result = await submit_experiment(payload)
    print(f"[smoke] submit ok={ok}, result={result!r}")

    if not ok:
        print("[FAIL] submit_experiment вернул ошибку")
        sys.exit(1)

    rec_id = result
    print(f"[smoke] rec_id = {rec_id}")

    # Сверим с сервером
    if not ADMIN_TOKEN:
        print("[smoke] ADMIN_TOKEN не задан — пропускаю верификацию по KV")
        print(f"[OK] submit_experiment работает (id={rec_id})")
        return

    rec = await fetch_record(rec_id)
    if not rec:
        print(f"[FAIL] запись {rec_id} не найдена в /api/experiments")
        sys.exit(1)

    print(f"[smoke] fetched record:")
    for k in ("name", "source", "did", "got"):
        v = rec.get(k, "<MISSING>")
        print(f"   {k}: {v!r}")

    # Байт-в-байт сравнение кириллицы
    fails = []
    for k in ("name", "source", "did", "got"):
        if rec.get(k) != payload[k]:
            fails.append(f"{k!r}: ожидалось {payload[k]!r}, получено {rec.get(k)!r}")
    if fails:
        print("[FAIL] данные на сервере НЕ совпадают с отправленными:")
        for f in fails:
            print(f"   - {f}")
        sys.exit(1)

    print(f"[OK] всё совпало, id={rec_id}")
    print(f"[note] Эта запись сохранена со статусом 'new' (allowPublish=false), удали вручную из /admin/experiments/")


if __name__ == "__main__":
    asyncio.run(main())
