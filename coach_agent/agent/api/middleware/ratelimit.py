"""
RateLimitMiddleware — простой in-memory token-bucket per (client_id, ip).

Phase 8: защита от случайного/злонамеренного спама на /coach/*.
Лимиты:
  - 30 req/min per X-Client-Id
  - 5 req/min per IP (для запросов без X-Client-Id — например, /admin/*)

Endpoints в whitelist (rate-limit не применяется):
  - /health* (для k8s/Render)
  - /docs, /openapi.json, /redoc (Swagger UI)
  - /admin/* (требует X-Admin-Token, отдельная защита)

In-memory: при multi-pod нужен Redis (Phase 9+).
"""

from __future__ import annotations

import time
from collections import defaultdict, deque

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from agent.utils import get_logger

log = get_logger("ratelimit")


# === Лимиты (настраиваются через env в Phase 9+) ===

PER_CLIENT_LIMIT = 30       # req/min per X-Client-Id
PER_IP_LIMIT = 5            # req/min per IP (когда нет X-Client-Id)
WINDOW_SEC = 60.0           # скользящее окно 1 минута

# Префиксы, которые всегда пропускаются
WHITELIST_PREFIXES = (
    "/health",
    "/docs",
    "/openapi.json",
    "/redoc",
    "/admin",
)


class RateLimitMiddleware(BaseHTTPMiddleware):
    """In-memory sliding-window rate limiter per (client_id, ip).

    NB: process-local dict — не синхронизирован между workers/pods.
    Для multi-pod нужен Redis (Phase 9+).
    """

    def __init__(self, app) -> None:
        super().__init__(app)
        # key -> deque[float] (timestamps)
        self._hits: dict[str, deque[float]] = defaultdict(deque)

    def _prune(self, bucket: deque[float], now: float) -> None:
        """Удалить timestamps старше WINDOW_SEC."""
        cutoff = now - WINDOW_SEC
        while bucket and bucket[0] < cutoff:
            bucket.popleft()

    def _check(self, key: str, limit: int) -> tuple[bool, int]:
        """Проверить лимит для key. Возвращает (allowed, retry_after_sec)."""
        now = time.monotonic()
        bucket = self._hits[key]
        self._prune(bucket, now)
        if len(bucket) >= limit:
            # Сколько секунд до освобождения слота
            retry_after = max(1, int(WINDOW_SEC - (now - bucket[0])))
            return False, retry_after
        bucket.append(now)
        return True, 0

    @staticmethod
    def _client_ip(request: Request) -> str:
        """Получить IP клиента (учитываем X-Forwarded-For от reverse-proxy)."""
        xff = request.headers.get("x-forwarded-for")
        if xff:
            return xff.split(",")[0].strip()
        return request.client.host if request.client else "unknown"

    def _is_whitelisted(self, path: str) -> bool:
        return any(path.startswith(p) for p in WHITELIST_PREFIXES)

    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        if self._is_whitelisted(path):
            return await call_next(request)

        client_id = request.headers.get("x-client-id")
        if client_id:
            key = f"cid:{client_id}"
            limit = PER_CLIENT_LIMIT
        else:
            ip = self._client_ip(request)
            key = f"ip:{ip}"
            limit = PER_IP_LIMIT

        allowed, retry_after = self._check(key, limit)
        if not allowed:
            log.warning(
                "ratelimit.blocked",
                key=key,
                path=path,
                retry_after=retry_after,
            )
            return JSONResponse(
                status_code=429,
                content={
                    "detail": "Too many requests",
                    "retry_after": retry_after,
                },
                headers={"Retry-After": str(retry_after)},
            )
        return await call_next(request)


__all__ = ["RateLimitMiddleware", "PER_CLIENT_LIMIT", "PER_IP_LIMIT", "WINDOW_SEC"]
