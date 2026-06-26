"""
CrisisFollowup — фоновый сервис, ставит аудит-метку `followed_up_at=now()`
на crisis_log старше 24 часов.

Phase 8: «мягкий follow-up» = НЕ сообщение клиенту, а аудит-метка для оператора
(чтобы знать, что crisis-лог уже «обработан» в смысле мониторинга). Это
избегает re-traumatization (не пишем клиенту «как ты?» после кризиса).

Запускается в lifespan FastAPI; цикл — 1 час.

Использование:
    cf = CrisisFollowup(repo)
    cf.start()  # неблокирующий — стартует asyncio task в фоне
    ...
    await cf.stop()  # graceful shutdown
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

from agent.utils import get_logger

if TYPE_CHECKING:
    from agent.storage.repository import Repository

log = get_logger("crisis_followup")

# Crisis-лог считается «обработанным» через 24ч
FOLLOWUP_AFTER = timedelta(hours=24)

# Интервал сканирования — 1 час
SCAN_INTERVAL_SEC = 3600.0

# Лимит за один проход (защита от наплыва старых логов)
BATCH_LIMIT = 50


class CrisisFollowup:
    """Background-сервис: раз в час помечает crisis_log.followed_up_at."""

    def __init__(self, repository: Repository) -> None:
        self._repo = repository
        self._task: asyncio.Task | None = None
        self._stop_event: asyncio.Event | None = None

    def start(self) -> None:
        """Стартует фоновый цикл. Неблокирующий. Безопасно вызывать один раз."""
        if self._task is not None and not self._task.done():
            log.warning("crisis_followup.already_running")
            return
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            log.error("crisis_followup.no_running_loop")
            return
        self._stop_event = asyncio.Event()
        self._task = loop.create_task(self._loop(), name="crisis-followup")
        log.info("crisis_followup.started", interval_sec=SCAN_INTERVAL_SEC)

    async def stop(self) -> None:
        """Graceful shutdown: досчитать текущую итерацию и выйти."""
        if self._stop_event is not None:
            self._stop_event.set()
        if self._task is not None and not self._task.done():
            try:
                await asyncio.wait_for(self._task, timeout=5.0)
            except (TimeoutError, asyncio.CancelledError):
                self._task.cancel()
        log.info("crisis_followup.stopped")

    async def _loop(self) -> None:
        """Главный цикл: спим SCAN_INTERVAL_SEC, сканируем."""
        assert self._stop_event is not None
        try:
            while not self._stop_event.is_set():
                try:
                    await self.run_once(self._repo)
                except Exception:
                    log.exception("crisis_followup.run_failed")
                # Ждём либо stop, либо интервал
                try:
                    await asyncio.wait_for(
                        self._stop_event.wait(), timeout=SCAN_INTERVAL_SEC
                    )
                except TimeoutError:
                    pass  # нормальный путь — пора сканировать снова
        except asyncio.CancelledError:
            log.info("crisis_followup.cancelled")
            raise

    async def run_once(self, repo: Repository) -> int:
        """Один проход: выбрать старые crisis_log, поставить followed_up_at.

        Возвращает количество обработанных логов.
        """
        cutoff = (datetime.now(UTC) - FOLLOWUP_AFTER).isoformat()
        try:
            old_logs = await repo.list_old_unfollowed_crisis(
                before_iso=cutoff, limit=BATCH_LIMIT
            )
        except Exception:
            log.exception("crisis_followup.list_failed")
            return 0
        if not old_logs:
            log.debug("crisis_followup.nothing_to_do")
            return 0
        marked = 0
        for row in old_logs:
            try:
                await repo.mark_crisis_followed_up(row.id)
                marked += 1
            except Exception:
                log.exception(
                    "crisis_followup.mark_failed", log_id=row.id
                )
        log.info(
            "crisis_followup.batch_done",
            marked=marked,
            cutoff=cutoff,
        )
        return marked


__all__ = ["CrisisFollowup", "FOLLOWUP_AFTER", "SCAN_INTERVAL_SEC", "BATCH_LIMIT"]
