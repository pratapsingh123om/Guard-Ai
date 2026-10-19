"""Deterministic, connector-specific connection verifiers."""

from __future__ import annotations

import os
import re
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import unquote, urlsplit

import httpx

from backend.app.integrations.models import ConnectionStatus
from backend.app.integrations.store import ConnectionRecord


_HTTP_TIMEOUT = httpx.Timeout(10.0, connect=5.0)
_SUPABASE_HOST = re.compile(r"[a-z0-9]{15,40}\.supabase\.co", re.ASCII)


@dataclass(frozen=True)
class ConnectionTestOutcome:
    status: ConnectionStatus
    configuration_valid: bool
    network_checked: bool
    network_reachable: bool | None
    verification_method: str
    message: str
    error: str | None = None


def _sqlite_root() -> Path:
    configured = os.getenv("GUARD_SQLITE_ROOT", "demo/integration-data")
    return Path(configured).resolve()


def _verify_sqlite(record: ConnectionRecord) -> ConnectionTestOutcome:
    parsed = urlsplit(record.endpoint)
    relative_name = unquote(parsed.path).lstrip("/\\")
    if not relative_name or Path(relative_name).name != relative_name:
        return ConnectionTestOutcome(
            status=ConnectionStatus.FAILED,
            configuration_valid=False,
            network_checked=False,
            network_reachable=None,
            verification_method="sqlite_read_only",
            message="SQLite endpoint must contain a single database filename.",
            error="invalid_sqlite_filename",
        )

    root = _sqlite_root()
    candidate = (root / relative_name).resolve()
    try:
        candidate.relative_to(root)
    except ValueError:
        return ConnectionTestOutcome(
            status=ConnectionStatus.FAILED,
            configuration_valid=False,
            network_checked=False,
            network_reachable=None,
            verification_method="sqlite_read_only",
            message="SQLite path falls outside the configured demo-data directory.",
            error="sqlite_path_outside_root",
        )
    if not candidate.is_file():
        return ConnectionTestOutcome(
            status=ConnectionStatus.FAILED,
            configuration_valid=True,
            network_checked=False,
            network_reachable=None,
            verification_method="sqlite_read_only",
            message="SQLite database was not found under the configured demo-data directory.",
            error="sqlite_file_not_found",
        )

    try:
        uri = f"file:{candidate.as_posix()}?mode=ro"
        connection = sqlite3.connect(uri, uri=True, timeout=2.0)
        try:
            connection.execute("PRAGMA query_only = ON")
            row = connection.execute("SELECT 1").fetchone()
        finally:
            connection.close()
        if row != (1,):
            raise sqlite3.DatabaseError("unexpected validation result")
    except sqlite3.Error:
        return ConnectionTestOutcome(
            status=ConnectionStatus.FAILED,
            configuration_valid=True,
            network_checked=False,
            network_reachable=None,
            verification_method="sqlite_read_only",
            message="SQLite database could not be opened and queried in read-only mode.",
            error="sqlite_read_only_check_failed",
        )

    return ConnectionTestOutcome(
        status=ConnectionStatus.VERIFIED,
        configuration_valid=True,
        network_checked=False,
        network_reachable=None,
        verification_method="sqlite_read_only",
        message="SQLite database was opened in read-only mode and passed SELECT 1.",
    )


def _safe_https_endpoint(
    endpoint: str,
    *,
    hostname: str | None = None,
    hostname_pattern: re.Pattern[str] | None = None,
    allowed_paths: set[str],
) -> bool:
    try:
        parsed = urlsplit(endpoint)
        port = parsed.port
    except ValueError:
        return False

    host = (parsed.hostname or "").lower()
    return bool(
        parsed.scheme.lower() == "https"
        and host
        and port in {None, 443}
        and parsed.username is None
        and parsed.password is None
        and not parsed.query
        and not parsed.fragment
        and parsed.path in allowed_paths
        and (hostname is None or host == hostname)
        and (hostname_pattern is None or hostname_pattern.fullmatch(host))
    )


def _failed_configuration(method: str, provider: str) -> ConnectionTestOutcome:
    return ConnectionTestOutcome(
        status=ConnectionStatus.FAILED,
        configuration_valid=False,
        network_checked=False,
        network_reachable=None,
        verification_method=method,
        message=f"{provider} endpoint is outside the verifier allowlist.",
        error=f"unsafe_{provider.lower()}_endpoint",
    )


async def _run_http_check(
    *,
    provider: str,
    method: str,
    url: str,
    headers: dict[str, str],
    transport: httpx.AsyncBaseTransport | None,
) -> ConnectionTestOutcome:
    try:
        async with httpx.AsyncClient(
            timeout=_HTTP_TIMEOUT,
            follow_redirects=False,
            trust_env=False,
            transport=transport,
        ) as client:
            response = await client.get(url, headers=headers)
    except httpx.RequestError:
        return ConnectionTestOutcome(
            status=ConnectionStatus.FAILED,
            configuration_valid=True,
            network_checked=True,
            network_reachable=False,
            verification_method=method,
            message=f"{provider} could not be reached within the verification timeout.",
            error=f"{provider.lower()}_network_unreachable",
        )

    if response.status_code == 200:
        return ConnectionTestOutcome(
            status=ConnectionStatus.VERIFIED,
            configuration_valid=True,
            network_checked=True,
            network_reachable=True,
            verification_method=method,
            message=f"{provider} accepted the configured credential using a read-only check.",
        )

    if response.status_code in {401, 403}:
        message = f"{provider} rejected the configured credential."
        error = f"{provider.lower()}_authentication_failed"
    else:
        message = f"{provider} returned an unexpected status during verification."
        error = f"{provider.lower()}_unexpected_status"
    return ConnectionTestOutcome(
        status=ConnectionStatus.FAILED,
        configuration_valid=True,
        network_checked=True,
        network_reachable=True,
        verification_method=method,
        message=message,
        error=error,
    )


async def _verify_openrouter(
    record: ConnectionRecord,
    *,
    transport: httpx.AsyncBaseTransport | None,
) -> ConnectionTestOutcome:
    method = "openrouter_current_key"
    if not _safe_https_endpoint(
        record.endpoint,
        hostname="openrouter.ai",
        allowed_paths={"/api/v1", "/api/v1/"},
    ):
        return _failed_configuration(method, "OpenRouter")

    return await _run_http_check(
        provider="OpenRouter",
        method=method,
        url=f"{record.endpoint.rstrip('/')}/key",
        headers={"Authorization": f"Bearer {record.credentials['api_key']}"},
        transport=transport,
    )


async def _verify_supabase(
    record: ConnectionRecord,
    *,
    transport: httpx.AsyncBaseTransport | None,
) -> ConnectionTestOutcome:
    method = "supabase_auth_health"
    if not _safe_https_endpoint(
        record.endpoint,
        hostname_pattern=_SUPABASE_HOST,
        allowed_paths={"", "/"},
    ):
        return _failed_configuration(method, "Supabase")

    return await _run_http_check(
        provider="Supabase",
        method=method,
        url=f"{record.endpoint.rstrip('/')}/auth/v1/health",
        # Supabase's current publishable keys are sent only in the apikey
        # header. This is also compatible with legacy anon keys.
        headers={"apikey": record.credentials["api_key"]},
        transport=transport,
    )


async def verify_connection_record(
    record: ConnectionRecord,
    *,
    transport: httpx.AsyncBaseTransport | None = None,
) -> ConnectionTestOutcome:
    if record.connector == "sqlite":
        return _verify_sqlite(record)
    if record.connector == "openrouter":
        return await _verify_openrouter(record, transport=transport)
    if record.connector == "supabase":
        return await _verify_supabase(record, transport=transport)

    return ConnectionTestOutcome(
        status=ConnectionStatus.CONFIGURED,
        configuration_valid=True,
        network_checked=False,
        network_reachable=None,
        verification_method="configuration_only",
        message=(
            "Configuration is valid. Network reachability was not tested because "
            "this connector does not yet have an SSRF-safe verifier."
        ),
    )
