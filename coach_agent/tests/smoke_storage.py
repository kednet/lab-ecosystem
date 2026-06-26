"""
Smoke-test для storage_backend=sqlite_local.
"""
import asyncio
import os
import shutil
import sys
from pathlib import Path

# === cp1252 fix для Windows (см. agent/utils.py — там же патч) ===
try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except (AttributeError, OSError):
    pass

# Используем локальный backend (по умолчанию), БД в ./tests/.data
os.environ["STORAGE_BACKEND"] = "sqlite_local"
os.environ["SQLITE_PATH"] = "./tests/.data/smoke.db"
# Чистим прошлый прогон
test_db = Path("./tests/.data/smoke.db")
if test_db.exists():
    test_db.unlink()
test_db.parent.mkdir(parents=True, exist_ok=True)


# === 1. Sync D1Client ===
from agent.storage.d1_client import D1Client, get_d1  # noqa: E402

print("=== 1. Sync D1Client (sqlite_local) ===")
client = get_d1()
print(f"backend = sqlite_local (file: {client._sqlite_path})")

# В smoke-тесте миграции вызываем явно (в проде это делает lifespan FastAPI).
from agent.storage.migrations import apply_migrations  # noqa: E402

apply_migrations(client=client)

# Проверим что миграции прошли (запрос к schema_meta)
row = client.fetch_one("SELECT value FROM schema_meta WHERE key='schema_version'")
assert row is not None, "schema_meta не создана — миграции не применились!"
print(f"schema_version = {row['value']}  OK")

# === 2. SELECT/INSERT/UPDATE через repository ===
print()
print("=== 2. Repository (sync) ===")
from agent.storage.repository import Repository  # noqa: E402

repo = Repository.__new__(Repository)
repo._d1 = client  # bypass async client


# Async helpers для теста
async def smoke_async():
    from agent.storage.d1_client_async import get_d1_async

    async_d1 = get_d1_async()
    async_repo = Repository(async_d1)

    # Тест 1: upsert_client (ON CONFLICT — id сохраняется; tone обновляется)
    c1 = await async_repo.upsert_client(
        email="smoke@test.local", name="Smoke", current_tone="warm"
    )
    print(f"upsert_client #1: id={c1.id}, email={c1.email}, tone={c1.current_tone}  OK")
    c2 = await async_repo.upsert_client(
        email="smoke@test.local", name="Smoke 2", current_tone="bold"
    )
    print(f"upsert_client #2 (same email): id={c2.id}, tone={c2.current_tone}  OK")
    assert c1.id == c2.id, "ON CONFLICT должен возвращать ту же запись"
    assert c2.current_tone == "bold", "ON CONFLICT должен обновить current_tone"

    # Тест 2: create_session + messages
    s = await async_repo.create_session(client_id=c1.id, tone="warm", tone_intensity=3)
    print(f"create_session: id={s.id}, state={s.current_state}  OK")
    m = await async_repo.append_message(
        session_id=s.id, role="user", content="Привет, мир! 👋"
    )
    print(f"append_message: id={m.id}, content={m.content!r}  OK")

    # Тест 3: create_desire с JSON
    d = await async_repo.create_desire(
        client_id=c1.id,
        title="Научиться готовить",
        kind="true",
        score=0.8,
        verdict_label="mostly_true",
        module_scores={"m1": 0.8, "m2": 0.7},
        detector_depth="express",
    )
    print(f"create_desire: id={d.id}, title={d.title!r}  OK")

    # Тест 4: получить обратно
    d_back = await async_repo.get_desire_by_id(d.id)
    assert d_back is not None
    import json

    ms = json.loads(d_back.module_scores)
    assert ms["m1"] == 0.8, "JSON round-trip"
    print(f"get_desire_by_id + JSON parse  OK")

    # Тест 5: list_steps пустой
    steps = await async_repo.list_steps(d.id)
    assert steps == []
    print(f"list_steps (empty)  OK")

    print()
    print("ALL OK")


asyncio.run(smoke_async())

# Cleanup
client.close()
shutil.rmtree("./tests/.data", ignore_errors=True)
print("\n[smoke_storage.py] ALL PASSED")
sys.exit(0)
