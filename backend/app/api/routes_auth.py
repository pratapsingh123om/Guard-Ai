"""Public auth bootstrap and signed-in identity endpoints."""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict, Field

from backend.app.api.dependencies import require_user
from backend.app.security.auth import (
    AuthPrincipal,
    guest_quota,
    issue_personal_token,
    supabase_browser_config,
)


router = APIRouter(prefix="/auth", tags=["authentication"])


class AuthConfigResponse(BaseModel):
    configured: bool
    supabase_url: str | None = None
    supabase_publishable_key: str | None = None
    google_enabled: bool = True
    guest_enabled: bool = True


class PrincipalResponse(BaseModel):
    subject: str
    email: str | None
    is_anonymous: bool
    auth_method: str
    scopes: list[str]
    guest_requests_remaining: int | None = None


class PersonalTokenCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    expires_in_hours: int = Field(default=24, ge=1, le=720)


class PersonalTokenResponse(BaseModel):
    token: str
    token_type: str = "Bearer"
    expires_at: datetime
    scopes: list[str]


def _principal_response(principal: AuthPrincipal) -> PrincipalResponse:
    return PrincipalResponse(
        subject=principal.subject,
        email=principal.email,
        is_anonymous=principal.is_anonymous,
        auth_method=principal.auth_method,
        scopes=sorted(principal.scopes),
        guest_requests_remaining=(
            guest_quota.remaining(principal.subject)
            if principal.is_anonymous
            else None
        ),
    )


@router.get("/config", response_model=AuthConfigResponse)
async def get_auth_config() -> AuthConfigResponse:
    config = supabase_browser_config()
    if config is None:
        return AuthConfigResponse(configured=False)
    url, publishable_key = config
    return AuthConfigResponse(
        configured=True,
        supabase_url=url,
        supabase_publishable_key=publishable_key,
    )


@router.get("/me", response_model=PrincipalResponse)
async def get_current_identity(
    principal: AuthPrincipal = Depends(require_user),
) -> PrincipalResponse:
    return _principal_response(principal)


@router.post("/tokens", response_model=PersonalTokenResponse)
async def create_personal_token(
    request: PersonalTokenCreate,
    principal: AuthPrincipal = Depends(require_user),
) -> PersonalTokenResponse:
    token, expires_at = issue_personal_token(
        principal,
        expires_in_hours=request.expires_in_hours,
    )
    return PersonalTokenResponse(
        token=token,
        expires_at=expires_at,
        scopes=sorted(principal.scopes),
    )
