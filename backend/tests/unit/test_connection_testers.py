from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from uuid import uuid4

import httpx

from backend.app.integrations.models import ConnectionCategory, ConnectionStatus
from backend.app.integrations.store import ConnectionRecord
from backend.app.integrations.testers import verify_connection_record


def _record(*, connector: str, endpoint: str, api_key: str = "demo-secret") -> ConnectionRecord:
    now = datetime.now(timezone.utc)
    if connector == "openrouter":
        category = ConnectionCategory.AI_PROVIDER
    elif connector == "guard_demo":
        category = ConnectionCategory.API
    else:
        category = ConnectionCategory.DATABASE
    return ConnectionRecord(
        id=uuid4(),
        name="Test connection",
        category=category,
        connector=connector,
        endpoint=endpoint,
        settings={},
        credentials={"api_key": api_key},
        status=ConnectionStatus.CONFIGURED,
        created_at=now,
        updated_at=now,
    )


def test_openrouter_verifier_uses_current_key_endpoint() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert str(request.url) == "https://openrouter.ai/api/v1/key"
        assert request.headers["Authorization"] == "Bearer demo-secret"
        return httpx.Response(200, json={"data": {"label": "not-inspected"}})

    outcome = asyncio.run(
        verify_connection_record(
            _record(connector="openrouter", endpoint="https://openrouter.ai/api/v1"),
            transport=httpx.MockTransport(handler),
        )
    )

    assert outcome.status is ConnectionStatus.VERIFIED
    assert outcome.network_checked is True
    assert outcome.network_reachable is True
    assert outcome.verification_method == "openrouter_current_key"


def test_supabase_verifier_uses_apikey_only() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert str(request.url) == (
            "https://abcdefghijklmnopqrst.supabase.co/auth/v1/health"
        )
        assert request.headers["apikey"] == "demo-secret"
        assert "Authorization" not in request.headers
        return httpx.Response(200, json={"name": "GoTrue"})

    outcome = asyncio.run(
        verify_connection_record(
            _record(
                connector="supabase",
                endpoint="https://abcdefghijklmnopqrst.supabase.co",
            ),
            transport=httpx.MockTransport(handler),
        )
    )

    assert outcome.status is ConnectionStatus.VERIFIED
    assert outcome.network_checked is True
    assert outcome.network_reachable is True
    assert outcome.verification_method == "supabase_auth_health"


def test_verifier_rejects_non_allowlisted_openrouter_endpoint() -> None:
    def should_not_run(_request: httpx.Request) -> httpx.Response:
        raise AssertionError("unsafe endpoint must not receive a request")

    outcome = asyncio.run(
        verify_connection_record(
            _record(connector="openrouter", endpoint="https://example.com/api/v1"),
            transport=httpx.MockTransport(should_not_run),
        )
    )

    assert outcome.status is ConnectionStatus.FAILED
    assert outcome.configuration_valid is False
    assert outcome.network_checked is False
    assert outcome.error == "unsafe_openrouter_endpoint"


def test_authentication_failure_is_sanitized() -> None:
    secret = "do-not-return-this-secret"

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, text=f"invalid key: {secret}")

    outcome = asyncio.run(
        verify_connection_record(
            _record(
                connector="supabase",
                endpoint="https://abcdefghijklmnopqrst.supabase.co",
                api_key=secret,
            ),
            transport=httpx.MockTransport(handler),
        )
    )

    assert outcome.status is ConnectionStatus.FAILED
    assert outcome.network_reachable is True
    assert outcome.error == "supabase_authentication_failed"
    assert secret not in outcome.message


def test_guard_demo_verifier_checks_live_database_health() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert str(request.url) == "https://guard-ai-secure-mcp.vercel.app/api/v1/demo/health"
        return httpx.Response(
            200,
            json={
                "service": "guard-ai-demo",
                "status": "healthy",
                "database": "ready",
                "records": 7,
            },
        )

    outcome = asyncio.run(
        verify_connection_record(
            _record(
                connector="guard_demo",
                endpoint="https://guard-ai-secure-mcp.vercel.app/api/v1/demo",
            ),
            transport=httpx.MockTransport(handler),
        )
    )

    assert outcome.status is ConnectionStatus.VERIFIED
    assert outcome.network_checked is True
    assert outcome.network_reachable is True
    assert outcome.verification_method == "guard_ai_demo_health"


def test_guard_demo_verifier_rejects_non_allowlisted_host() -> None:
    def should_not_run(_request: httpx.Request) -> httpx.Response:
        raise AssertionError("unsafe endpoint must not receive a request")

    outcome = asyncio.run(
        verify_connection_record(
            _record(
                connector="guard_demo",
                endpoint="https://example.com/api/v1/demo",
            ),
            transport=httpx.MockTransport(should_not_run),
        )
    )

    assert outcome.status is ConnectionStatus.FAILED
    assert outcome.configuration_valid is False
    assert outcome.network_checked is False
    assert outcome.error == "unsafe_guard_ai_demo_endpoint"
