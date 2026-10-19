"""Guard-AI MCP tools and their shared authorization boundary."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID

from mcp.server.auth.middleware.auth_context import get_access_token
from mcp.server.auth.provider import AccessToken
from mcp.server.mcpserver.exceptions import ToolError
from pydantic import BaseModel, field_validator

from backend.app.guardrails.pipeline import GuardrailPipeline, PipelineDecision, PipelineStatus
from backend.app.mcp.config import settings
from backend.app.mcp.identity import TLSIdentity, get_tls_identity
from backend.app.mcp.replay import ReplayCache, ReplayRejected


logger = logging.getLogger("guard_ai.security")
pipeline = GuardrailPipeline()
replay_cache = ReplayCache(
    max_lifetime_seconds=settings.request_lifetime_seconds,
    clock_skew_seconds=settings.clock_skew_seconds,
    ttl_seconds=settings.replay_ttl_seconds,
)


class RequestMetadata(BaseModel):
    request_id: UUID
    issued_at: datetime
    expires_at: datetime

    @field_validator("issued_at", "expires_at")
    @classmethod
    def require_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError("timestamp must include a timezone")
        return value


@dataclass(frozen=True)
class ToolSecurityDecision:
    status: PipelineStatus
    pipeline_decision: PipelineDecision
    agent_id: str
    token_subject: str


def _audit(event: str, **fields: Any) -> None:
    payload = {"event": event, **fields}
    logger.info(json.dumps(payload, sort_keys=True, default=str))


def authorize_tool_call(
    *,
    tool_name: str,
    arguments: dict[str, Any],
    request: RequestMetadata,
    required_scope: str,
    token: AccessToken | None = None,
    identity: TLSIdentity | None = None,
    cache: ReplayCache = replay_cache,
) -> ToolSecurityDecision:
    token = token or get_access_token()
    identity = identity or get_tls_identity()
    if token is None or identity is None:
        raise ToolError("Authenticated TLS and bearer-token identities are required.")
    if required_scope not in token.scopes:
        _audit(
            "tool_authorization_denied",
            request_id=request.request_id,
            agent_id=identity.agent_id,
            oauth_subject=token.subject,
            tool=tool_name,
            reason="insufficient_scope",
        )
        raise ToolError(f"Missing required scope: {required_scope}")

    try:
        cache.consume(
            agent_id=identity.agent_id,
            request_id=str(request.request_id),
            issued_at=request.issued_at,
            expires_at=request.expires_at,
        )
    except ReplayRejected as exc:
        _audit(
            "tool_authorization_denied",
            request_id=request.request_id,
            agent_id=identity.agent_id,
            oauth_subject=token.subject,
            tool=tool_name,
            reason="replay_or_expiry",
        )
        raise ToolError(str(exc)) from exc

    decision = pipeline.inspect_before_agent(
        message=f"Authenticated agent requests MCP tool {tool_name}.",
        proposed_actions=[{"tool": tool_name, "arguments": arguments}],
    )
    _audit(
        "tool_authorization_decision",
        request_id=request.request_id,
        agent_id=identity.agent_id,
        certificate_serial=identity.certificate_serial,
        oauth_subject=token.subject,
        oauth_client_id=token.client_id,
        tls_version=identity.tls_version,
        tls_group=identity.tls_group,
        tool=tool_name,
        required_scope=required_scope,
        policy_status=decision.status.value,
    )
    return ToolSecurityDecision(
        status=decision.status,
        pipeline_decision=decision,
        agent_id=identity.agent_id,
        token_subject=token.subject or token.client_id,
    )


def register_tools(mcp_server: Any) -> None:
    @mcp_server.tool()
    async def get_guard_status(request: RequestMetadata) -> dict[str, Any]:
        """Return non-sensitive Guard-AI status for an authenticated agent."""
        security = authorize_tool_call(
            tool_name="get_guard_status",
            arguments={},
            request=request,
            required_scope="mcp:read",
        )
        return {
            "status": "healthy",
            "agent_id": security.agent_id,
            "transport": {
                "tls_version": settings.expected_tls_version,
                "key_exchange_group": settings.expected_tls_group,
                "pqc_key_exchange": True,
            },
        }

    @mcp_server.tool()
    async def inspect_text(text: str, request: RequestMetadata) -> dict[str, Any]:
        """Inspect text with Guard-AI without invoking an external model."""
        authorize_tool_call(
            tool_name="inspect_text",
            arguments={"text_length": len(text)},
            request=request,
            required_scope="mcp:read",
        )
        input_decision = pipeline.inspect_before_agent(message=text)
        if input_decision.status is PipelineStatus.BLOCKED:
            return {
                "status": "blocked",
                "guardrails": [result.to_dict() for result in input_decision.results],
            }
        output = pipeline.inspect_output(text)
        return {
            "status": "allowed",
            "output": output.transformed_content or text,
            "guardrails": [
                *[result.to_dict() for result in input_decision.results],
                output.to_dict(),
            ],
        }

    @mcp_server.tool()
    async def write_demo_note(note_id: str, content: str, request: RequestMetadata) -> dict[str, Any]:
        """Propose an ephemeral write; the demo never executes it without approval."""
        security = authorize_tool_call(
            tool_name="write_demo_note",
            arguments={"note_id": note_id, "content_length": len(content)},
            request=request,
            required_scope="mcp:write",
        )
        if security.status is PipelineStatus.NEEDS_APPROVAL:
            return {
                "status": "approval_required",
                "executed": False,
                "tool": "write_demo_note",
                "note_id": note_id,
            }
        raise ToolError("Write policy unexpectedly allowed an unapproved side effect.")

    @mcp_server.tool()
    async def delete_demo_note(note_id: str, request: RequestMetadata) -> dict[str, Any]:
        """Propose a destructive demo action; it is never executed automatically."""
        security = authorize_tool_call(
            tool_name="delete_demo_note",
            arguments={"note_id": note_id},
            request=request,
            required_scope="mcp:admin",
        )
        return {
            "status": security.status.value,
            "executed": False,
            "tool": "delete_demo_note",
            "note_id": note_id,
        }
