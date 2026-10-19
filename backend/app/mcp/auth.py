"""JWT verification with audience, expiry, and mTLS certificate binding."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import jwt
from mcp.server.auth.provider import AccessToken, TokenVerifier

from backend.app.mcp.config import MCPSettings, settings
from backend.app.mcp.identity import get_tls_identity


logger = logging.getLogger(__name__)


class BoundJWTTokenVerifier(TokenVerifier):
    def __init__(self, config: MCPSettings = settings, public_key: str | bytes | None = None) -> None:
        self.config = config
        self._public_key = public_key

    def _load_public_key(self) -> str | bytes:
        if self._public_key is not None:
            return self._public_key
        return Path(self.config.public_key_file).read_bytes()

    async def verify_token(self, token: str) -> AccessToken | None:
        identity = get_tls_identity()
        if identity is None:
            return None

        try:
            claims: dict[str, Any] = jwt.decode(
                token,
                self._load_public_key(),
                algorithms=list(self.config.jwt_algorithms),
                audience=self.config.resource_url,
                issuer=self.config.issuer_url,
                options={"require": ["exp", "iat", "iss", "aud", "sub", "jti"]},
            )
            confirmation = claims.get("cnf") or {}
            if confirmation.get("x5t#S256") != identity.certificate_thumbprint:
                return None

            scope_value = claims.get("scope", "")
            scopes = scope_value.split() if isinstance(scope_value, str) else list(scope_value)
            client_id = str(claims.get("client_id") or claims["sub"])
            return AccessToken(
                token=token,
                client_id=client_id,
                scopes=scopes,
                expires_at=int(claims["exp"]),
                resource=self.config.resource_url,
                subject=str(claims["sub"]),
                claims=claims,
            )
        except (OSError, jwt.PyJWTError, TypeError, ValueError) as exc:
            logger.warning("MCP access token rejected: %s", type(exc).__name__)
            return None
