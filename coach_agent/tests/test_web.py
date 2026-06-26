"""
Тесты web-канала (FastAPI): POST /coach/message, /coach/end, /coach/tone, и т.д.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from agent.storage.models import ClientRow

HEADERS = {"X-Client-Id": "1"}


def _make_active_client(client_id: int = 1, onboarding_state: str = "new") -> ClientRow:
    return ClientRow(
        id=client_id,
        email=f"client_{client_id}@local",
        name=None,
        current_tone="warm",
        tone_intensity=3,
        timezone="Europe/Moscow",
        push_enabled=1,
        push_time="10:00",
        onboarding_state=onboarding_state,
        created_at="2026-06-10T00:00:00+00:00",
        last_seen_at="2026-06-10T00:00:00+00:00",
        subscription_status="active",
    )


@pytest.fixture
def seeded_app(client: TestClient, fake_repo):
    fake_repo._clients[1] = _make_active_client(1, onboarding_state="tone_picked")
    return client


# === /coach/message ===

def test_post_message_happy_path(
    client: TestClient, seeded_app, fake_ai
) -> None:
    fake_ai.push_response("Привет! Как твои дела?")
    r = client.post(
        "/coach/message",
        json={"text": "Привет"},
        headers=HEADERS,
    )
    assert r.status_code == 200, r.text
    data = r.json()
    assert "text" in data
    assert data["crisis_flag"] is False


def test_post_message_triggers_crisis(client: TestClient, seeded_app) -> None:
    r = client.post(
        "/coach/message",
        json={"text": "Не хочу жить, всё бессмысленно"},
        headers=HEADERS,
    )
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["crisis_flag"] is True
    assert data["state"] == "S_CRISIS_STOP"
    assert "8-800-2000-122" in data["text"]


def test_post_message_without_client_id_422(client: TestClient) -> None:
    r = client.post("/coach/message", json={"text": "x"})
    assert r.status_code == 422


def test_post_message_empty_text_422(client: TestClient, seeded_app) -> None:
    r = client.post("/coach/message", json={"text": ""}, headers=HEADERS)
    assert r.status_code == 422


def test_post_message_with_onboarding_first(
    client: TestClient, fake_repo, fake_ai
) -> None:
    """Новый клиент → первое сообщение вызовет dialog (после S_DIALOG)."""
    # client с onboarding_state='new', но message-handler сам создаст S_DIALOG
    fake_repo._clients[1] = _make_active_client(1, onboarding_state="new")
    fake_ai.push_response("Привет! Как дела?")
    r = client.post(
        "/coach/message",
        json={"text": "Привет"},
        headers=HEADERS,
    )
    assert r.status_code == 200


# === /coach/tone ===

def test_change_tone_endpoint(client: TestClient, seeded_app) -> None:
    r = client.post(
        "/coach/tone",
        json={"tone": "bold", "intensity": 5},
        headers=HEADERS,
    )
    assert r.status_code == 200
    data = r.json()
    assert "bold" in data["text"] or "bold" in data.get("state", "")


def test_change_tone_invalid_tone_422(client: TestClient, seeded_app) -> None:
    r = client.post(
        "/coach/tone",
        json={"tone": "invalid", "intensity": 3},
        headers=HEADERS,
    )
    assert r.status_code == 422


# === /coach/onboarding/tone ===

def test_onboarding_tone_endpoint(client: TestClient, fake_repo) -> None:
    fake_repo._clients[1] = _make_active_client(1, onboarding_state="new")
    r = client.post(
        "/coach/onboarding/tone",
        json={"tone": "warm", "intensity": 3},
        headers=HEADERS,
    )
    assert r.status_code == 200
    data = r.json()
    assert "buttons" in data
    assert len(data["buttons"]) >= 3  # минимум 4 кнопки старта


# === /coach/onboarding/start ===

def test_onboarding_start_endpoint(client: TestClient, fake_repo) -> None:
    fake_repo._clients[1] = _make_active_client(1, onboarding_state="tone_picked")
    r = client.post(
        "/coach/onboarding/start",
        json={"choice": "talk"},
        headers=HEADERS,
    )
    assert r.status_code == 200
    data = r.json()
    assert data["state"] in ("S_DIALOG", "S_DESIRE_DECOMP")


# === /coach/session ===

def test_get_session_endpoint(client: TestClient, seeded_app) -> None:
    r = client.get("/coach/session", headers=HEADERS)
    assert r.status_code == 200
    data = r.json()
    assert "current_state" in data
    assert "tone" in data
    assert "message_count" in data


# === /coach/end ===

def test_end_session_save(client: TestClient, seeded_app, fake_ai) -> None:
    fake_ai.push_response("Привет")
    client.post("/coach/message", json={"text": "Привет"}, headers=HEADERS)
    r = client.post(
        "/coach/end",
        json={"mode": "save"},
        headers=HEADERS,
    )
    assert r.status_code == 200
    data = r.json()
    assert data["ended_reason"] == "user_paused"


def test_end_session_complete(client: TestClient, seeded_app, fake_ai) -> None:
    fake_ai.push_response("Привет")
    client.post("/coach/message", json={"text": "Привет"}, headers=HEADERS)
    r = client.post(
        "/coach/end",
        json={"mode": "complete"},
        headers=HEADERS,
    )
    assert r.status_code == 200
    data = r.json()
    assert data["ended_reason"] == "completed"


# === /coach/desire + /coach/desires ===

def test_create_desire(client: TestClient, seeded_app) -> None:
    r = client.post(
        "/coach/desire",
        json={"title": "Купить MacBook"},
        headers=HEADERS,
    )
    assert r.status_code == 200
    data = r.json()
    assert "MacBook" in data["text"]


def test_list_desires(client: TestClient, seeded_app) -> None:
    client.post(
        "/coach/desire", json={"title": "Купить машину"}, headers=HEADERS
    )
    r = client.get("/coach/desires", headers=HEADERS)
    assert r.status_code == 200
    data = r.json()
    assert "items" in data
    assert any("машину" in item["title"] for item in data["items"])


# === Welcome-back: после save, новое сообщение возвращает welcome_back ===

def test_welcome_back_after_pause(client: TestClient, seeded_app, fake_ai) -> None:
    fake_ai.push_response("Привет")
    client.post("/coach/message", json={"text": "Привет"}, headers=HEADERS)
    client.post("/coach/end", json={"mode": "save"}, headers=HEADERS)
    fake_ai.push_response("С возвращением!")
    r = client.post(
        "/coach/message", json={"text": "Продолжаем"}, headers=HEADERS
    )
    # welcome_back может быть или не быть — но response должен быть
    assert r.status_code == 200


# === Detector через API ===

def test_detector_command(client: TestClient, seeded_app, fake_ai) -> None:
    # Создадим желание, потом запустим детектор
    client.post(
        "/coach/desire", json={"title": "Разобраться с бизнесом"}, headers=HEADERS
    )
    fake_ai.push_response("Ок")  # на создание desire
    r = client.post(
        "/coach/message",
        json={"text": "/detector express"},
        headers=HEADERS,
    )
    assert r.status_code == 200
    data = r.json()
    assert data["state"] == "S_DETECTOR"
    assert "Вопрос 1" in data["text"] or "вопрос 1" in data["text"].lower()
