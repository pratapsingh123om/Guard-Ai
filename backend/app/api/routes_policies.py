"""Runtime and transport policy management endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Security
from fastapi.security import HTTPAuthorizationCredentials
from pydantic import BaseModel

from backend.app.api.dependencies import admin_bearer, require_admin
from backend.app.mcp.config import settings as mcp_settings
from backend.app.policy.runtime import (
    RuntimePolicySnapshot,
    RuntimePolicyUpdate,
    runtime_policy_store,
)


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


async def _authorize(
    credentials: HTTPAuthorizationCredentials | None = Security(admin_bearer()),
) -> None:
    await require_admin(credentials)


def _response() -> PolicyResponse:
    return PolicyResponse(
        runtime=runtime_policy_store.snapshot(),
        transport=TransportPolicy(
            tls_version=mcp_settings.expected_tls_version,
            key_exchange_group=mcp_settings.expected_tls_group,
            hybrid_pqc_required=True,
            mutual_tls_required=True,
            certificate_bound_tokens=True,
        ),
    )


@router.get("", response_model=PolicyResponse, dependencies=[Depends(_authorize)])
async def get_policies() -> PolicyResponse:
    return _response()


@router.put("", response_model=PolicyResponse, dependencies=[Depends(_authorize)])
async def update_policies(request: RuntimePolicyUpdate) -> PolicyResponse:
    runtime_policy_store.update(request)
    return _response()
