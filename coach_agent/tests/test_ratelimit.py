"""
Тесты для Phase 8: RateLimitMiddleware — in-memory sliding window per (client_id, ip).
"""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from agent.api.middleware.ratelimit import (
    PER_CLIENT_LIMIT,
    PER_IP_LIMIT,
    RateLimitMiddleware,
)


@pytest.fixture
def app() -> FastAPI:
    """Чистый FastAPI app с одним GET /ping без rate-limit на /health (для тестов)."""
    a = FastAPI()
    a.add_middleware(RateLimitMiddleware)

    @a.get("/ping")
    async def ping() -> dict[str, str]:
        return {"pong": "ok"}

    return a


@pytest.fixture
def client(app: FastAPI) -> TestClient:
    return TestClient(app)


def test_rate_limit_blocks_per_client_id(client: TestClient) -> None:
    """30 запросов OK, 31-й — 429."""
    headers = {"X-Client-Id": "test-1"}
    for i in range(PER_CLIENT_LIMIT):
        r = client.get("/ping", headers=headers)
        assert r.status_code == 200, f"req {i+1} should be 200, got {r.status_code}"
    # 31-й блокируется
    r = client.get("/ping", headers=headers)
    assert r.status_code == 429
    assert "Retry-After" in r.headers
    body = r.json()
    assert "retry_after" in body


def test_rate_limit_separate_clients(client: TestClient) -> None:
    """Разные X-Client-Id имеют независимые счётчики."""
    h1 = {"X-Client-Id": "client-A"}
    h2 = {"X-Client-Id": "client-B"}
    # Исчерпываем client-A
    for _ in range(PER_CLIENT_LIMIT):
        client.get("/ping", headers=h1)
    r = client.get("/ping", headers=h1)
    assert r.status_code == 429
    # client-B — свежий
    r = client.get("/ping", headers=h2)
    assert r.status_code == 200


def test_rate_limit_ip_fallback(client: TestClient) -> None:
    """Без X-Client-Id — лимит по IP (PER_IP_LIMIT)."""
    # TestClient использует testclient как host → все запросы с одного IP
    for _ in range(PER_IP_LIMIT):
        r = client.get("/ping")
        assert r.status_code == 200
    r = client.get("/ping")
    assert r.status_code == 429


def test_rate_limit_whitelist_health(client: TestClient) -> None:
    """/health и /docs НЕ подвержены rate-limit (whitelist)."""
    # 100 запросов — все должны быть 200 (404 на /ping-аналоге, но rate-limit
    # смотрит на /health — whitelist).
    a = FastAPI()
    a.add_middleware(RateLimitMiddleware)

    @a.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @a.get("/docs")
    async def docs() -> dict[str, str]:
        return {"docs": "ok"}

    c = TestClient(a)
    for _ in range(PER_CLIENT_LIMIT * 3):
        r = c.get("/health")
        assert r.status_code == 200
    # /docs тоже whitelist
    r = c.get("/docs")
    assert r.status_code == 200
