"""Management endpoints for external AI, data, API, and MCP connections."""

from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response, Security, status
from fastapi.security import HTTPAuthorizationCredentials
from pydantic import BaseModel, Field, SecretStr

from backend.app.api.dependencies import admin_bearer, require_admin
from backend.app.integrations.models import (
    CONNECTOR_CATALOG,
    ConnectionCreate,
    ConnectionResponse,
    ConnectionStatus,
    ConnectionTestResponse,
    ConnectorDefinition,
)
from backend.app.integrations.store import connection_store
from backend.app.integrations.testers import verify_connection_record


router = APIRouter(prefix="/connections", tags=["connections"])


class EnvironmentImportResponse(BaseModel):
    imported: list[ConnectionResponse] = Field(default_factory=list)
    existing: list[ConnectionResponse] = Field(default_factory=list)
    unavailable: list[str] = Field(default_factory=list)


async def _authorize(
    credentials: HTTPAuthorizationCredentials | None = Security(admin_bearer()),
) -> None:
    await require_admin(credentials)


@router.get("/catalog", response_model=list[ConnectorDefinition])
async def list_connector_types() -> list[ConnectorDefinition]:
    """Return non-secret connector metadata used to build setup forms."""

    return list(CONNECTOR_CATALOG.values())


@router.get("", response_model=list[ConnectionResponse], dependencies=[Depends(_authorize)])
async def list_connections() -> list[ConnectionResponse]:
    return connection_store.list()


@router.post(
    "",
    response_model=ConnectionResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(_authorize)],
)
async def create_connection(request: ConnectionCreate) -> ConnectionResponse:
    try:
        return connection_store.create(request)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except OverflowError as exc:
        raise HTTPException(status_code=507, detail=str(exc)) from exc


@router.post(
    "/import-env",
    response_model=EnvironmentImportResponse,
    dependencies=[Depends(_authorize)],
)
async def import_environment_connections() -> EnvironmentImportResponse:
    """Import supported server-side environment integrations without exposing secrets."""

    candidates: list[ConnectionCreate] = []
    unavailable: list[str] = []

    openrouter_key = os.getenv("OPENROUTER_API_KEY") or os.getenv("OPENAI_API_KEY")
    if openrouter_key:
        model = os.getenv("OPENROUTER_MODEL") or os.getenv("LLM_MODEL")
        candidates.append(
            ConnectionCreate(
                name="OpenRouter (Environment)",
                category="ai_provider",
                connector="openrouter",
                endpoint=os.getenv("OPENROUTER_BASE_URL") or "https://openrouter.ai/api/v1",
                settings={"model": model} if model else {},
                credentials={"api_key": SecretStr(openrouter_key)},
            )
        )
    else:
        unavailable.append("openrouter")

    supabase_url = os.getenv("SUPABASE_URL")
    supabase_key = os.getenv("SUPABASE_PUBLISHABLE_KEY") or os.getenv(
        "SUPABASE_ANON_KEY"
    )
    if supabase_url and supabase_key:
        candidates.append(
            ConnectionCreate(
                name="Supabase (Environment)",
                category="database",
                connector="supabase",
                endpoint=supabase_url,
                credentials={"api_key": SecretStr(supabase_key)},
            )
        )
    else:
        unavailable.append("supabase")

    sqlite_root = Path(
        os.getenv("GUARD_SQLITE_ROOT", "demo/integration-data")
    ).resolve()
    sqlite_demo = sqlite_root / "guard-ai-demo.db"
    if sqlite_demo.is_file():
        candidates.append(
            ConnectionCreate(
                name="SQLite Demo",
                category="database",
                connector="sqlite",
                endpoint="sqlite:///guard-ai-demo.db",
            )
        )
    else:
        unavailable.append("sqlite")

    result = EnvironmentImportResponse(unavailable=unavailable)
    for candidate in candidates:
        existing = connection_store.get_response_by_name(candidate.name)
        if existing is not None:
            result.existing.append(existing)
            continue
        try:
            result.imported.append(connection_store.create(candidate))
        except (ValueError, OverflowError) as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
    return result


@router.get(
    "/{connection_id}",
    response_model=ConnectionResponse,
    dependencies=[Depends(_authorize)],
)
async def get_connection(connection_id: UUID) -> ConnectionResponse:
    result = connection_store.get_response(connection_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Connection not found.")
    return result


@router.post(
    "/{connection_id}/test",
    response_model=ConnectionTestResponse,
    dependencies=[Depends(_authorize)],
)
async def test_connection(connection_id: UUID) -> ConnectionTestResponse:
    """Run a connector-specific, allowlisted, non-mutating verification."""

    record = connection_store.get(connection_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Connection not found.")

    checked_at = datetime.now(timezone.utc)
    outcome = await verify_connection_record(record)
    connection_store.mark_tested(
        connection_id,
        status=outcome.status,
        error=outcome.error,
    )
    return ConnectionTestResponse(
        connection_id=connection_id,
        status=outcome.status,
        configuration_valid=outcome.configuration_valid,
        network_checked=outcome.network_checked,
        network_reachable=outcome.network_reachable,
        verification_method=outcome.verification_method,
        checked_at=checked_at,
        message=outcome.message,
    )


@router.delete(
    "/{connection_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(_authorize)],
)
async def delete_connection(connection_id: UUID) -> Response:
    if not connection_store.delete(connection_id):
        raise HTTPException(status_code=404, detail="Connection not found.")
    return Response(status_code=status.HTTP_204_NO_CONTENT)
