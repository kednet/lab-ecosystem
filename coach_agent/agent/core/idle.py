"""
Idle-timer: 15 минут без ответа → S_IDLE_SAVED.

Реализован через asyncio.create_task per session_id, cancel + reschedule.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable

from agent.utils import get_logger

log = get_logger("idle")


class IdleTimer:
    """
    Управляет per-session idle-таймерами.

    arm() — отменить предыдущий (если был) и поставить новый.
    disarm() — отменить без вызова callback.
    """

    def __init__(self, timeout_sec: int = 900) -> None:  # 15 мин
        self._timeout = timeout_sec
        self._tasks: dict[int, asyncio.Task] = {}

    @property
    def timeout_sec(self) -> int:
        return self._timeout

    def arm(
        self,
        session_id: int,
        on_timeout: Callable[[], Awaitable[None]],
    ) -> None:
        """Запустить/перезапустить таймер для сессии."""
        self.disarm(session_id)
        loop = asyncio.get_running_loop()

        async def _wait_then_call() -> None:
            try:
                await asyncio.sleep(self._timeout)
                log.info("idle.timeout_fired", session_id=session_id)
                await on_timeout()
            except asyncio.CancelledError:
                log.debug("idle.cancelled", session_id=session_id)
                raise

        task = loop.create_task(_wait_then_call())

        def _cleanup(_t: asyncio.Task) -> None:
            # удаляем из реестра, когда таска завершилась (любым способом)
            self._tasks.pop(session_id, None)

        task.add_done_callback(_cleanup)
        self._tasks[session_id] = task
        log.debug("idle.armed", session_id=session_id, timeout=self._timeout)

    def disarm(self, session_id: int) -> None:
        """Отменить таймер (если был)."""
        task = self._tasks.pop(session_id, None)
        if task and not task.done():
            task.cancel()

    def is_armed(self, session_id: int) -> bool:
        return session_id in self._tasks

    async def shutdown(self) -> None:
        """Отменить все таймеры (при остановке приложения)."""
        for sid in list(self._tasks.keys()):
            self.disarm(sid)


__all__ = ["IdleTimer"]
