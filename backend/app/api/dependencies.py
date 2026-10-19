"""Shared HTTP API dependencies."""

from __future__ import annotations

import os
import secrets

from fastapi import HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer


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


def admin_bearer() -> HTTPBearer:
    return _bearer
