"""Supabase session, Guard-AI API token, and legacy admin authentication."""

from __future__ import annotations

import os
import secrets
import threading
import asyncio
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from functools import lru_cache
from typing import Any
from urllib.parse import urlsplit
from uuid import uuid4

import jwt
import httpx
from fastapi import HTTPException, status
from jwt import InvalidTokenError, PyJWKClient, PyJWKClientError


MANAGEMENT_SCOPES = frozenset(
    {
        "chat:invoke",
        "connections:read",
        "connections:write",
        "policies:read",
        "policies:write",
        "traces:read",
    }
)
ADMIN_SCOPES = MANAGEMENT_SCOPES | {"connections:import-env"}
GUEST_SCOPES = frozenset({"chat:invoke"})
PERSONAL_TOKEN_PREFIX = "gai_"
PERSONAL_TOKEN_ISSUER = "guard-ai"
PERSONAL_TOKEN_AUDIENCE = "guard-ai-api"


@dataclass(frozen=True)
class AuthPrincipal:
    subject: str
    owner_id: str
    email: str | None
    is_anonymous: bool
    auth_method: str
    scopes: frozenset[str]

    def has_scope(self, scope: str) -> bool:
        return scope in self.scopes


class GuestQuota:
    """Small process-local quota for the public demo.

    This intentionally limits accidental abuse in the demo. Distributed production
    deployments should replace it with a shared rate-limit store.
    """

    def __init__(self) -> None:
        self._counts: dict[str, int] = {}
        self._lock = threading.RLock()

    @staticmethod
    def limit() -> int:
        try:
            return max(1, min(int(os.getenv("GUARD_GUEST_REQUEST_LIMIT", "10")), 100))
        except ValueError:
            return 10

    def remaining(self, subject: str) -> int:
        with self._lock:
            return max(0, self.limit() - self._counts.get(subject, 0))

    def consume(self, subject: str) -> int:
        with self._lock:
            used = self._counts.get(subject, 0)
            if used >= self.limit():
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail="Guest trial limit reached. Sign in with Google to continue.",
                )
            self._counts[subject] = used + 1
            return self.limit() - self._counts[subject]

    def clear(self) -> None:
        with self._lock:
            self._counts.clear()


guest_quota = GuestQuota()


def supabase_browser_config() -> tuple[str, str] | None:
    url = os.getenv("SUPABASE_URL", "").strip().rstrip("/")
    key = (
        os.getenv("SUPABASE_PUBLISHABLE_KEY", "").strip()
        or os.getenv("SUPABASE_ANON_KEY", "").strip()
    )
    if not url or not key:
        return None
    parsed = urlsplit(url)
    if parsed.scheme not in {"https", "http"} or not parsed.netloc:
        return None
    if parsed.scheme == "http" and parsed.hostname not in {"localhost", "127.0.0.1"}:
        return None
    return url, key


@lru_cache(maxsize=4)
def _jwks_client(jwks_url: str) -> PyJWKClient:
    return PyJWKClient(jwks_url, cache_jwk_set=True, lifespan=300)


def _decode_asymmetric_supabase_token(
    token: str,
    *,
    issuer: str,
) -> dict[str, Any]:
    jwks_url = f"{issuer}/.well-known/jwks.json"
    signing_key = _jwks_client(jwks_url).get_signing_key_from_jwt(token)
    return jwt.decode(
        token,
        signing_key.key,
        algorithms=["RS256", "ES256", "EdDSA"],
        audience="authenticated",
        issuer=issuer,
        options={"require": ["exp", "iat", "sub", "aud"]},
    )


async def _decode_supabase_token(token: str) -> dict[str, Any]:
    config = supabase_browser_config()
    if config is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Supabase authentication is not configured on this server.",
        )
    url, publishable_key = config
    issuer = f"{url}/auth/v1"
    try:
        header = jwt.get_unverified_header(token)
        if header.get("alg") == "HS256":
            async with httpx.AsyncClient(
                timeout=httpx.Timeout(10.0, connect=5.0),
                trust_env=False,
                follow_redirects=False,
            ) as client:
                response = await client.get(
                    f"{issuer}/user",
                    headers={
                        "apikey": publishable_key,
                        "Authorization": f"Bearer {token}",
                    },
                )
            if response.status_code != 200:
                raise InvalidTokenError("Supabase Auth rejected the access token")
            user = response.json()
            subject = user.get("id")
            if not isinstance(subject, str) or not subject:
                raise InvalidTokenError("Supabase Auth returned an invalid user")
            return {
                "sub": subject,
                "email": user.get("email"),
                "is_anonymous": user.get("is_anonymous") is True,
            }
        return await asyncio.to_thread(
            _decode_asymmetric_supabase_token,
            token,
            issuer=issuer,
        )
    except (InvalidTokenError, PyJWKClientError, ValueError, httpx.HTTPError) as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="The Supabase session is invalid or expired.",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc


def _personal_token_secret(*, required: bool = True) -> str | None:
    value = os.getenv("GUARD_API_TOKEN_SECRET", "")
    if len(value) >= 32:
        return value
    if required:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                "Personal API tokens are disabled until GUARD_API_TOKEN_SECRET "
                "is configured with at least 32 characters."
            ),
        )
    return None


def issue_personal_token(
    principal: AuthPrincipal,
    *,
    expires_in_hours: int = 24,
) -> tuple[str, datetime]:
    if principal.auth_method != "supabase" or principal.is_anonymous:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Sign in with Google before creating a personal Guard-AI token.",
        )
    secret = _personal_token_secret()
    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(hours=max(1, min(expires_in_hours, 24 * 30)))
    payload = {
        "iss": PERSONAL_TOKEN_ISSUER,
        "aud": PERSONAL_TOKEN_AUDIENCE,
        "sub": principal.subject,
        "email": principal.email,
        "scopes": sorted(MANAGEMENT_SCOPES),
        "iat": now,
        "exp": expires_at,
        "jti": str(uuid4()),
    }
    encoded = jwt.encode(payload, secret, algorithm="HS256")
    return f"{PERSONAL_TOKEN_PREFIX}{encoded}", expires_at


def _principal_from_personal_token(token: str) -> AuthPrincipal:
    secret = _personal_token_secret()
    try:
        claims = jwt.decode(
            token.removeprefix(PERSONAL_TOKEN_PREFIX),
            secret,
            algorithms=["HS256"],
            audience=PERSONAL_TOKEN_AUDIENCE,
            issuer=PERSONAL_TOKEN_ISSUER,
            options={"require": ["exp", "iat", "sub", "aud", "iss"]},
        )
    except InvalidTokenError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="The Guard-AI API token is invalid or expired.",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc
    subject = str(claims["sub"])
    claimed_scopes = claims.get("scopes")
    scopes = (
        frozenset(str(value) for value in claimed_scopes)
        if isinstance(claimed_scopes, list)
        else frozenset()
    )
    return AuthPrincipal(
        subject=subject,
        owner_id=f"supabase:{subject}",
        email=claims.get("email") if isinstance(claims.get("email"), str) else None,
        is_anonymous=False,
        auth_method="guard_token",
        scopes=scopes & MANAGEMENT_SCOPES,
    )


async def authenticate_bearer(token: str) -> AuthPrincipal:
    admin_token = os.getenv("GUARD_ADMIN_TOKEN", "")
    if len(admin_token) >= 32 and secrets.compare_digest(token, admin_token):
        return AuthPrincipal(
            subject="legacy-admin",
            owner_id="legacy-admin",
            email=None,
            is_anonymous=False,
            auth_method="legacy_admin",
            scopes=ADMIN_SCOPES,
        )
    if token.startswith(PERSONAL_TOKEN_PREFIX):
        return _principal_from_personal_token(token)

    if token.count(".") != 2:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="The bearer token is invalid.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    claims = await _decode_supabase_token(token)
    subject = str(claims["sub"])
    is_anonymous = claims.get("is_anonymous") is True
    email = claims.get("email") if isinstance(claims.get("email"), str) else None
    return AuthPrincipal(
        subject=subject,
        owner_id=f"supabase:{subject}",
        email=email,
        is_anonymous=is_anonymous,
        auth_method="supabase",
        scopes=GUEST_SCOPES if is_anonymous else MANAGEMENT_SCOPES,
    )
