"""
Async-зеркало sync storage client.

Тот же контракт, что и D1Client (sync), но работает через aiosqlite
для локального режима или через httpx.AsyncClient для D1.
"""

from __future__ import annotations

from typing import Any

import httpx

from agent.config import settings
from agent.storage.d1_client import D1Client, D1Error, log
from agent.utils import get_logger

_log = get_logger("d1_client_async")


class D1ClientAsync:
    """Async storage client. Контракт как у sync D1Client."""

    def __init__(self) -> None:
        self._backend = settings.storage_backend
        if self._backend == "sqlite_local":
            self._init_sqlite()
        elif self._backend == "d1":
            self._init_d1()
        elif self._backend == "postgres":
            raise NotImplementedError(
                "PostgreSQL backend ещё не реализован. "
                "Используйте storage_backend='d1' или 'sqlite_local'."
            )
        else:
            raise ValueError(f"Unknown storage_backend: {self._backend!r}")

    # ── SQLite async ────────────────────────────────────────────

    def _init_sqlite(self) -> None:
        # Lazy import — aiosqlite опциональный, добавим в pyproject.toml
        import aiosqlite  # type: ignore[import-not-found]

        from pathlib import Path

        db_path = Path(settings.sqlite_path).expanduser().resolve()
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self._sqlite_path = str(db_path)
        self._aiosqlite_module = aiosqlite
        # Миграции выполнит sync D1Client (singleton), если ещё не выполнялись
        _ = D1Client  # noqa: F841 — ensures module loaded

    # ── D1 async ────────────────────────────────────────────────

    def _init_d1(self) -> None:
        if not all(
            [settings.cf_account_id, settings.cf_d1_database_id, settings.cf_api_token]
        ):
            _log.warning(
                "d1_async.unconfigured",
                hint="CF_* переменные пусты — async D1 будет недоступна",
            )
        self._headers = {
            "Authorization": f"Bearer {settings.cf_api_token}",
            "Content-Type": "application/json",
        }
        proxies: str | None = settings.socks5_proxy if settings.socks5_proxy else None
        self._client = httpx.AsyncClient(
            base_url=settings.d1_base_url,
            headers=self._headers,
            timeout=httpx.Timeout(30.0, connect=10.0),
            verify=settings.verify_ssl,
            proxy=proxies,
        )

    async def close(self) -> None:
        if self._backend == "d1":
            await self._client.aclose()

    async def __aenter__(self) -> D1ClientAsync:
        return self

    async def __aexit__(self, *exc: Any) -> None:
        await self.close()

    # ── Универсальный интерфейс ─────────────────────────────────

    async def execute(
        self, sql: str, params: list[Any] | None = None
    ) -> list[dict[str, Any]]:
        if self._backend == "sqlite_local":
            return await self._execute_sqlite(sql, params)
        return await self._execute_d1(sql, params)

    async def _execute_sqlite(
        self, sql: str, params: list[Any] | None
    ) -> list[dict[str, Any]]:
        import aiosqlite  # type: ignore[import-not-found]

        try:
            async with aiosqlite.connect(self._sqlite_path) as db:
                db.row_factory = aiosqlite.Row
                await db.execute("PRAGMA journal_mode=WAL")
                await db.execute("PRAGMA foreign_keys=ON")
                if params:
                    async with db.execute(sql, params) as cur:
                        if cur.description is None:
                            await db.commit()
                            return []
                        rows = await cur.fetchall()
                        await db.commit()
                        return [dict(row) for row in rows]
                else:
                    await db.executescript(sql)
                    return []
        except Exception as e:
            _log.exception("storage.sqlite_async_error", sql=sql[:100])
            raise D1Error(f"SQLite async ошибка: {e}") from e

    async def _execute_d1(
        self, sql: str, params: list[Any] | None
    ) -> list[dict[str, Any]]:
        if not all(
            [settings.cf_account_id, settings.cf_d1_database_id, settings.cf_api_token]
        ):
            raise D1Error("D1 не сконфигурирована (CF_* переменные пусты)")
        body: dict[str, Any] = {"sql": sql}
        if params is not None:
            body["params"] = params
        try:
            r = await self._client.post("/query", json=body)
        except httpx.HTTPError as e:
            _log.error("d1_async.network_error", error=str(e), sql=sql[:100])
            raise D1Error(f"Сеть D1: {e}") from e
        if r.status_code != 200:
            _log.error(
                "d1_async.http_error",
                status=r.status_code,
                body=r.text[:500],
                sql=sql[:100],
            )
            raise D1Error(f"D1 вернул {r.status_code}: {r.text[:200]}")
        data = r.json()
        if not data.get("success"):
            errors = data.get("errors", [])
            _log.error("d1_async.sql_error", errors=errors, sql=sql[:100])
            raise D1Error(f"SQL ошибка: {errors}")
        result_payload = data.get("result", [])
        out: list[dict[str, Any]] = []
        for stmt in result_payload:
            if "results" in stmt:
                out.extend(stmt["results"])
            else:
                out.append(stmt)
        return out

    async def fetch_all(
        self, sql: str, params: list[Any] | None = None
    ) -> list[dict[str, Any]]:
        return await self.execute(sql, params)

    async def fetch_one(
        self, sql: str, params: list[Any] | None = None
    ) -> dict[str, Any] | None:
        rows = await self.fetch_all(sql, params)
        return rows[0] if rows else None

    async def exec_script(self, sql_script: str) -> None:
        statements = [s.strip() for s in sql_script.split(";") if s.strip()]
        for i, stmt in enumerate(statements, 1):
            _log.info("storage.async_exec", n=i, total=len(statements), preview=stmt[:60])
            await self.execute(stmt)


_default_async: D1ClientAsync | None = None


def get_d1_async() -> D1ClientAsync:
    """Singleton (создаётся в lifespan FastAPI)."""
    global _default_async
    if _default_async is None:
        _default_async = D1ClientAsync()
    return _default_async


async def close_d1_async() -> None:
    """Закрыть singleton (вызывается в shutdown)."""
    global _default_async
    if _default_async is not None:
        await _default_async.close()
        _default_async = None


__all__ = ["D1ClientAsync", "get_d1_async", "close_d1_async", "D1Error"]