"""Runtime and transport policy management endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from backend.app.api.dependencies import require_scope
from backend.app.mcp.config import settings as mcp_settings
from backend.app.policy.runtime import (
    RuntimePolicySnapshot,
    RuntimePolicyUpdate,
    runtime_policy_store,
)
from backend.app.security.auth import AuthPrincipal


class TransportPolicy(BaseModel):
    tls_version: str
    key_exchange_group: str
    hybrid_pqc_required: bool
    mutual_tls_required: bool
    certificate_bound_tokens: bool


class PolicyResponse(BaseModel):
    runtime: RuntimePolicySnapshot
    transport: TransportPolicy


router = APIRouter(prefix="/policies", tags=["policies"])


def _response(owner_id: str) -> PolicyResponse:
    return PolicyResponse(
        runtime=runtime_policy_store.snapshot(owner_id),
        transport=TransportPolicy(
            tls_version=mcp_settings.expected_tls_version,
            key_exchange_group=mcp_settings.expected_tls_group,
            hybrid_pqc_required=True,
            mutual_tls_required=True,
            certificate_bound_tokens=True,
        ),
    )


@router.get("", response_model=PolicyResponse)
async def get_policies(
    principal: AuthPrincipal = Depends(require_scope("policies:read")),
) -> PolicyResponse:
    return _response(principal.owner_id)


@router.put("", response_model=PolicyResponse)
async def update_policies(
    request: RuntimePolicyUpdate,
    principal: AuthPrincipal = Depends(require_scope("policies:write")),
) -> PolicyResponse:
    runtime_policy_store.update(request, principal.owner_id)
    return _response(principal.owner_id)
