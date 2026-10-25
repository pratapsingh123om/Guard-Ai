from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from backend.app.integrations.store import connection_store
from backend.app.main import app
from backend.app.security.auth import guest_quota


client = TestClient(app)


@pytest.fixture(autouse=True)
def reset_state(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("SUPABASE_URL", "https://abcdefghijklmnopqrst.supabase.co")
    monkeypatch.setenv("SUPABASE_PUBLISHABLE_KEY", "sb_publishable_public-test-key")
    monkeypatch.setenv("GUARD_API_TOKEN_SECRET", "test-personal-token-secret-with-32-characters")
    monkeypatch.delenv("GUARD_ADMIN_TOKEN", raising=False)
    connection_store.clear()
    guest_quota.clear()
    yield
    connection_store.clear()
    guest_quota.clear()


async def _fake_supabase_claims(token: str):
    if token == "signed-in.user.jwt":
        return {"sub": "user-1", "email": "owner@example.com", "is_anonymous": False}
    if token == "anonymous.user.jwt":
        return {"sub": "guest-1", "is_anonymous": True}
    if token == "second-user.access.jwt":
        return {"sub": "user-2", "email": "other@example.com", "is_anonymous": False}
    raise AssertionError(f"unexpected token: {token}")


def test_auth_config_exposes_only_browser_safe_supabase_values() -> None:
    response = client.get("/api/v1/auth/config")

    assert response.status_code == 200
    assert response.json() == {
        "configured": True,
        "supabase_url": "https://abcdefghijklmnopqrst.supabase.co",
        "supabase_publishable_key": "sb_publishable_public-test-key",
        "google_enabled": True,
        "guest_enabled": True,
    }


def test_google_user_can_mint_and_use_personal_token(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "backend.app.security.auth._decode_supabase_token",
        _fake_supabase_claims,
    )
    session_headers = {"Authorization": "Bearer signed-in.user.jwt"}

    me = client.get("/api/v1/auth/me", headers=session_headers)
    assert me.status_code == 200
    assert me.json()["email"] == "owner@example.com"
    assert me.json()["is_anonymous"] is False

    created = client.post(
        "/api/v1/auth/tokens",
        headers=session_headers,
        json={"expires_in_hours": 12},
    )
    assert created.status_code == 200
    personal_token = created.json()["token"]
    assert personal_token.startswith("gai_")

    connections = client.get(
        "/api/v1/connections",
        headers={"Authorization": f"Bearer {personal_token}"},
    )
    assert connections.status_code == 200


def test_guest_is_chat_only_and_has_a_quota(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "backend.app.security.auth._decode_supabase_token",
        _fake_supabase_claims,
    )
    monkeypatch.setenv("GUARD_GUEST_REQUEST_LIMIT", "1")
    headers = {"Authorization": "Bearer anonymous.user.jwt"}

    denied = client.get("/api/v1/connections", headers=headers)
    assert denied.status_code == 403

    first = client.post(
        "/api/v1/chat",
        headers=headers,
        json={"message": "Summarize this sentence"},
    )
    assert first.status_code == 200
    assert first.json()["guest_requests_remaining"] == 0

    exhausted = client.post(
        "/api/v1/chat",
        headers=headers,
        json={"message": "Try another request"},
    )
    assert exhausted.status_code == 429


def test_connections_are_isolated_by_supabase_subject(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "backend.app.security.auth._decode_supabase_token",
        _fake_supabase_claims,
    )
    first_headers = {"Authorization": "Bearer signed-in.user.jwt"}
    second_headers = {"Authorization": "Bearer second-user.access.jwt"}

    created = client.post(
        "/api/v1/connections",
        headers=first_headers,
        json={
            "name": "Owner database",
            "category": "database",
            "connector": "sqlite",
            "endpoint": "sqlite:///guard-ai-demo.db",
        },
    )
    assert created.status_code == 201
    assert len(client.get("/api/v1/connections", headers=first_headers).json()) == 1
    assert client.get("/api/v1/connections", headers=second_headers).json() == []
    hidden = client.get(
        f"/api/v1/connections/{created.json()['id']}",
        headers=second_headers,
    )
    assert hidden.status_code == 404
