from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from mcp.server.auth.provider import AccessToken
from mcp.server.mcpserver.exceptions import ToolError

from backend.app.guardrails.pipeline import PipelineStatus
from backend.app.mcp.identity import TLSIdentity
from backend.app.mcp.replay import ReplayCache, ReplayRejected
from backend.app.mcp.tools import RequestMetadata, authorize_tool_call


def _request(request_id=None) -> RequestMetadata:
    now = datetime.now(timezone.utc)
    return RequestMetadata(
        request_id=request_id or uuid4(),
        issued_at=now,
        expires_at=now + timedelta(seconds=30),
    )


def _identity() -> TLSIdentity:
    return TLSIdentity(
        agent_id="spiffe://guard-ai.demo/agent/coordinator",
        certificate_thumbprint="thumbprint",
        certificate_serial="1234",
        tls_version="TLSv1.3",
        tls_group="X25519MLKEM768",
    )


def _token(scopes: list[str]) -> AccessToken:
    return AccessToken(
        token="redacted",
        client_id="coordinator-agent",
        subject="coordinator-agent",
        scopes=scopes,
        expires_at=None,
        resource="https://guard-ai.demo/mcp",
    )


def _cache() -> ReplayCache:
    return ReplayCache(max_lifetime_seconds=60, clock_skew_seconds=10, ttl_seconds=300)


def test_replay_cache_rejects_duplicate_request_id() -> None:
    cache = _cache()
    request = _request()
    values = {
        "agent_id": _identity().agent_id,
        "request_id": str(request.request_id),
        "issued_at": request.issued_at,
        "expires_at": request.expires_at,
    }

    cache.consume(**values)

    with pytest.raises(ReplayRejected, match="duplicate"):
        cache.consume(**values)


def test_expired_request_is_rejected() -> None:
    cache = _cache()
    now = datetime.now(timezone.utc)

    with pytest.raises(ReplayRejected, match="expired"):
        cache.consume(
            agent_id=_identity().agent_id,
            request_id=str(uuid4()),
            issued_at=now - timedelta(minutes=2),
            expires_at=now - timedelta(minutes=1),
            now=now,
        )


def test_read_tool_is_allowed_with_read_scope() -> None:
    decision = authorize_tool_call(
        tool_name="get_guard_status",
        arguments={},
        request=_request(),
        required_scope="mcp:read",
        token=_token(["mcp:read"]),
        identity=_identity(),
        cache=_cache(),
    )

    assert decision.status is PipelineStatus.ALLOWED


def test_write_tool_requires_approval_and_does_not_execute() -> None:
    decision = authorize_tool_call(
        tool_name="write_demo_note",
        arguments={"note_id": "one", "content_length": 4},
        request=_request(),
        required_scope="mcp:write",
        token=_token(["mcp:write"]),
        identity=_identity(),
        cache=_cache(),
    )

    assert decision.status is PipelineStatus.NEEDS_APPROVAL


def test_missing_scope_is_rejected_before_policy() -> None:
    with pytest.raises(ToolError, match="Missing required scope"):
        authorize_tool_call(
            tool_name="delete_demo_note",
            arguments={"note_id": "one"},
            request=_request(),
            required_scope="mcp:admin",
            token=_token(["mcp:read"]),
            identity=_identity(),
            cache=_cache(),
        )
