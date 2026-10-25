"""Shared HTTP API dependencies."""

from __future__ import annotations

import os
import secrets

from fastapi import HTTPException, Security, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from backend.app.security.auth import AuthPrincipal, authenticate_bearer


_bearer = HTTPBearer(auto_error=False)


async def require_admin(
    credentials: HTTPAuthorizationCredentials | None = None,
) -> None:
    """Require an operator token for secret-bearing management APIs."""

    # FastAPI injects Security dependencies only when they are declared with
    # Depends/Security by the router. Keeping token lookup per request also
    # permits safe rotation without restarting the process.
    expected = os.getenv("GUARD_ADMIN_TOKEN", "")
    if len(expected) < 32:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                "Management API is disabled until GUARD_ADMIN_TOKEN is configured "
                "with at least 32 characters."
            ),
        )
    if (
        credentials is None
        or credentials.scheme.casefold() != "bearer"
        or not secrets.compare_digest(credentials.credentials, expected)
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="A valid Guard-AI operator token is required.",
            headers={"WWW-Authenticate": "Bearer"},
        )


async def require_user(
    credentials: HTTPAuthorizationCredentials | None = Security(_bearer),
) -> AuthPrincipal:
    if credentials is None or credentials.scheme.casefold() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Sign in or provide a valid Guard-AI bearer token.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return await authenticate_bearer(credentials.credentials)


async def require_management_user(
    principal: AuthPrincipal = Security(require_user),
) -> AuthPrincipal:
    if principal.is_anonymous:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Guest trials can use the playground only. Sign in with Google to manage services.",
        )
    return principal


def require_scope(scope: str):
    async def dependency(
        principal: AuthPrincipal = Security(require_management_user),
    ) -> AuthPrincipal:
        if not principal.has_scope(scope):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"The bearer token is missing the required scope: {scope}",
            )
        return principal

    return dependency


async def require_legacy_admin(
    principal: AuthPrincipal = Security(require_user),
) -> AuthPrincipal:
    if principal.auth_method != "legacy_admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the server operator may import server-side environment secrets.",
        )
    return principal


def admin_bearer() -> HTTPBearer:
    return _bearer
