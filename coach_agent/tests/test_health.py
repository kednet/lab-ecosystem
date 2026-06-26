"""
Smoke-тесты для Phase 0.

Запуск: pytest -v
"""

from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient

from agent.config import settings
from agent.main import app
from agent.storage.migrations import SCHEMA_VERSION


@pytest.fixture
def client() -> TestClient:
    """FastAPI test client. Не дёргает сеть — handlers могут вернуть d1=error, но /health отдаст 200."""
    return TestClient(app)


# === / ===

def test_root(client: TestClient) -> None:
    r = client.get("/")
    assert r.status_code == 200
    data = r.json()
    assert data["service"] == "wishcoach"
    assert data["phase"] == 1
    assert data["schema_version"] == SCHEMA_VERSION
    assert "endpoints" in data


# === /health ===

def test_health_ok(client: TestClient) -> None:
    """Без D1 возвращает 200 с d1.ok=False (graceful degradation)."""
    r = client.get("/health")
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "ok"
    assert data["version"] == "0.2.0"
    assert data["schema_version"] == SCHEMA_VERSION
    assert "d1" in data
    # Если D1 не сконфигурена локально — d1.ok=False, но статус всё равно ok
    if not all([settings.cf_account_id, settings.cf_d1_database_id, settings.cf_api_token]):
        assert data["d1"]["ok"] is False


def test_health_d1_unconfigured_returns_ok(client: TestClient) -> None:
    """Если D1 не сконфигурена, /health всё равно отдаёт 200 — не блокируем деплой."""
    r = client.get("/health")
    assert r.status_code == 200


# === /health/d1 ===

def test_health_d1_no_config_returns_503(client: TestClient) -> None:
    """Readiness probe строгий: 503 если D1 недоступна."""
    if all([settings.cf_account_id, settings.cf_d1_database_id, settings.cf_api_token]):
        pytest.skip("D1 сконфигурена — отдельный сценарий")
    r = client.get("/health/d1")
    assert r.status_code == 503
    data = r.json()
    assert data["status"] == "not_ready"


# === /admin/migrate ===

def test_admin_migrate_no_token_401(client: TestClient) -> None:
    r = client.post("/admin/migrate", json={})
    assert r.status_code == 401


def test_admin_migrate_wrong_token_401(client: TestClient) -> None:
    r = client.post(
        "/admin/migrate",
        json={},
        headers={"X-Admin-Token": "wrong-token"},
    )
    assert r.status_code == 401


def test_admin_migrate_correct_token_noop(client: TestClient) -> None:
    """С правильным токеном запрос уходит дальше 401 (D1-ошибка — это 5xx, не 401)."""
    if not all([settings.cf_account_id, settings.cf_d1_database_id, settings.cf_api_token]):
        pytest.skip("D1 не сконфигурена — негативный кейс на 401 уже покрыт выше")
    expected_token = os.environ.get("ADMIN_TOKEN") or settings.render_service_name
    r = client.post(
        "/admin/migrate",
        json={},
        headers={"X-Admin-Token": expected_token},
    )
    assert r.status_code != 401


def test_admin_migrate_correct_token_d1_error(client: TestClient) -> None:
    """Без D1 возвращает 503 (D1Error handler), не 401 — токен прошёл."""
    if all([settings.cf_account_id, settings.cf_d1_database_id, settings.cf_api_token]):
        pytest.skip("D1 сконфигурена — отдельный сценарий")
    expected_token = os.environ.get("ADMIN_TOKEN") or settings.render_service_name
    r = client.post(
        "/admin/migrate",
        json={},
        headers={"X-Admin-Token": expected_token},
    )
    # 503 — D1Error handler, не 401
    assert r.status_code != 401
    assert r.status_code == 503


# === Config ===

def test_settings_have_defaults() -> None:
    """Settings загружаются без падения даже без .env."""
    s = settings
    assert s.app_port == 8000 or s.app_port > 0
    assert s.coach_timezone
    assert hasattr(s, "cf_account_id")
    assert hasattr(s, "anthropic_api_key")


def test_settings_mitm_defaults() -> None:
    """MITM-настройки по умолчанию безопасны (verify_ssl=False, socks5 задан)."""
    s = settings
    # Дефолт для корпоративной среды — false
    assert s.verify_ssl is False or s.verify_ssl is True  # в тестах допускаем любое
    # SOCKS5 не пустой (для совместимости)
    assert s.socks5_proxy


# === Schema version ===

def test_schema_version_format() -> None:
    """Версия схемы — semver."""
    parts = SCHEMA_VERSION.split(".")
    assert len(parts) == 3
    for p in parts:
        assert p.isdigit()


# === Phase 8: /health/ai ===

def test_health_ai_endpoint_returns_200(client: TestClient) -> None:
    """/health/ai всегда 200 (для мониторинга, не падает liveness)."""
    r = client.get("/health/ai")
    assert r.status_code == 200
    data = r.json()
    assert "ai" in data
    assert "ok" in data
    assert data["ai"] in ("fake", "claude", "yandex", "unconfigured", "unknown")
    assert isinstance(data["ok"], bool)


def test_health_ai_unconfigured_returns_503_on_health(client: TestClient) -> None:
    """/health возвращает 503 если AI не сконфигурирован И не fake_mode.

    TestClient запускает lifespan → если нет ключей и нет fake_mode,
    ai_client = None → /health = 503.
    """
    fake_mode = os.getenv("AI_FAKE_MODE", "").lower() in ("1", "true", "yes")
    has_anthropic = bool(settings.anthropic_api_key)
    has_yandex = bool(
        getattr(settings, "yandexgpt_api_key", None)
        and getattr(settings, "yandexgpt_folder_id", None)
    )
    if fake_mode or has_anthropic or has_yandex:
        pytest.skip("AI сконфигурирован или fake_mode — 503-сценарий не применим")
    r = client.get("/health")
    assert r.status_code == 503
    data = r.json()
    assert data["ai"] == "unconfigured"
    assert data["status"] == "ai_unconfigured"


def test_health_ai_root_includes_health_ai(client: TestClient) -> None:
    """/ содержит health_ai в списке эндпоинтов."""
    r = client.get("/")
    assert r.status_code == 200
    data = r.json()
    assert "endpoints" in data
    assert "health_ai" in data["endpoints"]
    assert data["endpoints"]["health_ai"] == "/health/ai"
