"""
Storage backend для WishCoach.

Поддерживает два бэкенда (выбираются через settings.storage_backend):
- `d1`         — Cloudflare D1 через REST API (httpx)
- `sqlite_local` — локальный SQLite-файл (stdlib sqlite3)

D1 и SQLite разделяют один диалект SQL (D1 = SQLite 3.x),
поэтому repository.py и migrations.py работают с обоими без изменений.

ВАЖНО:
- D1-режим требует CF_ACCOUNT_ID / CF_D1_DATABASE_ID / CF_API_TOKEN в env.
- sqlite_local создаёт файл по пути settings.sqlite_path (default `.data/wishcoach.db`).
- При первом запуске sqlite_local **сам** вызывает apply_migrations()
  (D1-режим требует ручного wrangler d1 migrations apply).
"""

from __future__ import annotations

import sqlite3
import threading
from pathlib import Path
from typing import Any, Optional

import httpx

from agent.config import settings
from agent.utils import get_logger

log = get_logger("d1_client")


class D1Error(RuntimeError):
    """Ошибка хранилища (сетевая или SQL)."""


# ──────────────────────────────────────────────────────────────────
# Sync client
# ──────────────────────────────────────────────────────────────────


class D1Client:
    """Sync storage client. Контракт одинаков для D1 и SQLite:
    - execute(sql, params) -> list[dict]
    - fetch_one(sql, params) -> dict | None
    - fetch_all(sql, params) -> list[dict]
    - exec_script(sql_script) -> None  (для миграций)
    """

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

    # ── SQLite (локальный) ──────────────────────────────────────

    def _init_sqlite(self) -> None:
        db_path = Path(settings.sqlite_path).expanduser().resolve()
        db_path.parent.mkdir(parents=True, exist_ok=True)
        # check_same_thread=False — нам ок, мы защищаемся локом
        self._sqlite_path = str(db_path)
        self._sqlite_lock = threading.Lock()
        self._sqlite_conn: Optional[sqlite3.Connection] = None
        # WAL = лучше для concurrent reads, не блокирует writer
        log.info("storage.sqlite_init", path=self._sqlite_path)
        # Миграции НЕ выполняются здесь автоматически —
        # вызывающий код (lifespan FastAPI) делает это явно через apply_migrations(get_d1()).

    def _sqlite_get_conn(self) -> sqlite3.Connection:
        """Возвращает живое соединение (одно на поток, через атрибут)."""
        if self._sqlite_conn is None:
            conn = sqlite3.connect(
                self._sqlite_path,
                detect_types=sqlite3.PARSE_DECLTYPES,
                check_same_thread=False,
                # ВАЖНО: НЕ ставим isolation_level=None (autocommit),
                # иначе executescript() ломает CREATE TABLE внутри скрипта
                # (теряются таблицы без ошибки). Держим дефолтный deferred.
            )
            conn.row_factory = sqlite3.Row
            # conn.execute("PRAGMA journal_mode=WAL")  # WAL вызывает проблемы с видимостью в нашем wrapper — отключено
            conn.execute("PRAGMA foreign_keys=ON")
            conn.execute("PRAGMA busy_timeout=5000")
            self._sqlite_conn = conn
        return self._sqlite_conn

    def _apply_migrations_if_needed(self) -> None:
        """Применить миграции при первом старте (или если schema_meta пуста)."""
        # Lazy import — migrations.py импортирует этот модуль
        from agent.storage.migrations import SCHEMA_VERSION, apply_migrations

        applied = self.fetch_one(
            "SELECT value FROM schema_meta WHERE key = 'schema_version'"
        )
        if applied and applied.get("value") == SCHEMA_VERSION:
            log.info("storage.migrations_up_to_date", version=SCHEMA_VERSION)
            return
        log.info("storage.migrations_apply", version=SCHEMA_VERSION)
        # Применяем все миграции (apply_migrations берёт все MIGRATION_NNN)
        result = apply_migrations(client=self)
        log.info("storage.migrations_done", result=result)

    def _execute_sqlite(self, sql: str, params: list[Any] | None) -> list[dict[str, Any]]:
        conn = self._sqlite_get_conn()
        with self._sqlite_lock:
            try:
                # Если переданы params — execute с placeholder'ами.
                # Иначе (миграции через exec_script, INSERT без params) — execute
                # без params. Он умеет multi-statement через `;` (т.к. это sqlite3
                # execute, не executescript — execute игнорирует дополнительные
                # statements в строке? НЕТ: он выполняет только первый, остальные
                # теряет).
                #
                # Правильный путь: execute без params, если в SQL ЕСТЬ `;` —
                # это многостэйтмент скрипт, его через executescript.
                # Иначе — обычный execute.
                if ";" in sql.strip().rstrip(";"):
                    # Многостэйтмент (миграция, multi-statement скрипт)
                    conn.executescript(sql)
                    conn.commit()
                    return []
                if params:
                    cur = conn.execute(sql, params)
                else:
                    cur = conn.execute(sql)
                if cur.description is None:
                    conn.commit()
                    return []
                rows = [dict(row) for row in cur.fetchall()]
                conn.commit()
                return rows
            except sqlite3.Error as e:
                conn.rollback()
                log.exception("storage.sqlite_error", sql=sql[:100])
                raise D1Error(f"SQLite ошибка: {e}") from e

    # ── D1 (Cloudflare REST) ────────────────────────────────────

    def _init_d1(self) -> None:
        if not all(
            [settings.cf_account_id, settings.cf_d1_database_id, settings.cf_api_token]
        ):
            log.warning(
                "d1_client.unconfigured",
                hint="CF_ACCOUNT_ID / CF_D1_DATABASE_ID / CF_API_TOKEN не заполнены",
            )
        self._headers = {
            "Authorization": f"Bearer {settings.cf_api_token}",
            "Content-Type": "application/json",
        }
        # В проде (Render) корпоративного SOCKS5 нет → не передаём proxy
        proxies: str | None = (
            settings.socks5_proxy
            if settings.socks5_proxy and not settings.is_production
            else None
        )
        self._client = httpx.Client(
            base_url=settings.d1_base_url,
            headers=self._headers,
            timeout=httpx.Timeout(30.0, connect=10.0),
            verify=settings.verify_ssl,
            proxy=proxies,
        )

    def _execute_d1(self, sql: str, params: list[Any] | None) -> list[dict[str, Any]]:
        if not all(
            [settings.cf_account_id, settings.cf_d1_database_id, settings.cf_api_token]
        ):
            raise D1Error("D1 не сконфигурирована (CF_* переменные пусты)")
        body: dict[str, Any] = {"sql": sql}
        if params is not None:
            body["params"] = params
        try:
            r = self._client.post("/query", json=body)
        except httpx.HTTPError as e:
            log.exception("d1_client.network_error", sql=sql[:100])
            raise D1Error(f"Сеть D1: {e}") from e
        if r.status_code != 200:
            log.error(
                "d1_client.http_error",
                status=r.status_code,
                body=r.text[:500],
                sql=sql[:100],
            )
            raise D1Error(f"D1 вернул {r.status_code}: {r.text[:200]}")
        data = r.json()
        if not data.get("success"):
            errors = data.get("errors", [])
            log.error("d1_client.sql_error", errors=errors, sql=sql[:100])
            raise D1Error(f"SQL ошибка: {errors}")
        result_payload = data.get("result", [])
        out: list[dict[str, Any]] = []
        for stmt in result_payload:
            if "results" in stmt:
                out.extend(stmt["results"])
            else:
                out.append(stmt)
        return out

    # ── Универсальный интерфейс ─────────────────────────────────

    def execute(self, sql: str, params: list[Any] | None = None) -> list[dict[str, Any]]:
        """Выполнить SQL и вернуть результат.
        - SELECT → list[dict] (rows)
        - INSERT/UPDATE/DDL → [] (empty)
        """
        if self._backend == "sqlite_local":
            return self._execute_sqlite(sql, params)
        return self._execute_d1(sql, params)

    def fetch_all(
        self, sql: str, params: list[Any] | None = None
    ) -> list[dict[str, Any]]:
        return self.execute(sql, params)

    def fetch_one(
        self, sql: str, params: list[Any] | None = None
    ) -> dict[str, Any] | None:
        rows = self.fetch_all(sql, params)
        return rows[0] if rows else None

    def exec_script(self, sql_script: str) -> None:
        """Выполнить многострочный SQL-скрипт (миграцию)."""
        # И D1, и SQLite принимают несколько statement через `;`
        statements = [s.strip() for s in sql_script.split(";") if s.strip()]
        for i, stmt in enumerate(statements, 1):
            log.info("storage.exec", n=i, total=len(statements), preview=stmt[:60])
            self.execute(stmt)

    def close(self) -> None:
        if self._backend == "sqlite_local" and self._sqlite_conn is not None:
            try:
                self._sqlite_conn.close()
            except sqlite3.Error:
                pass
            self._sqlite_conn = None
        elif self._backend == "d1":
            self._client.close()

    def __enter__(self) -> D1Client:
        return self

    def __exit__(self, *exc: Any) -> None:
        self.close()


# ──────────────────────────────────────────────────────────────────
# Singleton
# ──────────────────────────────────────────────────────────────────

_default_client: D1Client | None = None


def get_d1() -> D1Client:
    """Singleton sync storage client."""
    global _default_client
    if _default_client is None:
        _default_client = D1Client()
    return _default_client


__all__ = ["D1Client", "D1Error", "get_d1"]