"""Configuration for the secure MCP resource server."""

from __future__ import annotations

import os
from dataclasses import dataclass


def _csv_env(name: str, default: str) -> tuple[str, ...]:
    return tuple(item.strip() for item in os.getenv(name, default).split(",") if item.strip())


@dataclass(frozen=True)
class MCPSettings:
    issuer_url: str = os.getenv("GUARD_MCP_ISSUER_URL", "https://issuer.guard-ai.demo")
    resource_url: str = os.getenv("GUARD_MCP_RESOURCE_URL", "https://guard-ai.demo/mcp")
    public_key_file: str = os.getenv(
        "GUARD_MCP_JWT_PUBLIC_KEY_FILE", "/run/guard-ai/tokens/issuer-public.pem"
    )
    jwt_algorithms: tuple[str, ...] = _csv_env("GUARD_MCP_JWT_ALGORITHMS", "ES256")
    allowed_hosts: tuple[str, ...] = _csv_env(
        "GUARD_MCP_ALLOWED_HOSTS", "guard-ai.demo,localhost,127.0.0.1,testserver"
    )
    allowed_origins: tuple[str, ...] = _csv_env(
        "GUARD_MCP_ALLOWED_ORIGINS", "https://guard-ai.demo"
    )
    expected_tls_version: str = os.getenv("GUARD_MCP_TLS_VERSION", "TLSv1.3")
    expected_tls_group: str = os.getenv("GUARD_MCP_TLS_GROUP", "X25519MLKEM768")
    max_request_body_size: int = int(os.getenv("GUARD_MCP_MAX_BODY_BYTES", "1048576"))
    request_lifetime_seconds: int = int(os.getenv("GUARD_MCP_REQUEST_LIFETIME_SECONDS", "60"))
    clock_skew_seconds: int = int(os.getenv("GUARD_MCP_CLOCK_SKEW_SECONDS", "10"))
    replay_ttl_seconds: int = int(os.getenv("GUARD_MCP_REPLAY_TTL_SECONDS", "300"))
    revoked_certificate_serials: tuple[str, ...] = _csv_env(
        "GUARD_MCP_REVOKED_CERTIFICATE_SERIALS", ""
    )


settings = MCPSettings()
