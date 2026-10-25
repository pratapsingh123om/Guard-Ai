"""Management endpoints for external AI, data, API, and MCP connections."""

from __future__ import annotations

import os
from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel, Field, SecretStr

from backend.app.api.dependencies import require_legacy_admin, require_scope
from backend.app.demo.database import ensure_demo_database
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
from backend.app.security.auth import AuthPrincipal


router = APIRouter(prefix="/connections", tags=["connections"])


class EnvironmentImportResponse(BaseModel):
    imported: list[ConnectionResponse] = Field(default_factory=list)
    existing: list[ConnectionResponse] = Field(default_factory=list)
    unavailable: list[str] = Field(default_factory=list)


@router.get("/catalog", response_model=list[ConnectorDefinition])
async def list_connector_types() -> list[ConnectorDefinition]:
    """Return non-secret connector metadata used to build setup forms."""

    return list(CONNECTOR_CATALOG.values())


@router.get("", response_model=list[ConnectionResponse])
async def list_connections(
    principal: AuthPrincipal = Depends(require_scope("connections:read")),
) -> list[ConnectionResponse]:
    return connection_store.list(owner_id=principal.owner_id)


@router.post(
    "",
    response_model=ConnectionResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_connection(
    request: ConnectionCreate,
    principal: AuthPrincipal = Depends(require_scope("connections:write")),
) -> ConnectionResponse:
    try:
        return connection_store.create(request, owner_id=principal.owner_id)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except OverflowError as exc:
        raise HTTPException(status_code=507, detail=str(exc)) from exc


@router.post(
    "/import-env",
    response_model=EnvironmentImportResponse,
)
async def import_environment_connections(
    principal: AuthPrincipal = Depends(require_legacy_admin),
) -> EnvironmentImportResponse:
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

    sqlite_demo = ensure_demo_database()
    if sqlite_demo is not None and sqlite_demo.is_file():
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
        existing = connection_store.get_response_by_name(
            candidate.name,
            owner_id=principal.owner_id,
        )
        if existing is not None:
            result.existing.append(existing)
            continue
        try:
            result.imported.append(
                connection_store.create(candidate, owner_id=principal.owner_id)
            )
        except (ValueError, OverflowError) as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
    return result


@router.get(
    "/{connection_id}",
    response_model=ConnectionResponse,
)
async def get_connection(
    connection_id: UUID,
    principal: AuthPrincipal = Depends(require_scope("connections:read")),
) -> ConnectionResponse:
    result = connection_store.get_response(connection_id, owner_id=principal.owner_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Connection not found.")
    return result


@router.post(
    "/{connection_id}/test",
    response_model=ConnectionTestResponse,
)
async def test_connection(
    connection_id: UUID,
    principal: AuthPrincipal = Depends(require_scope("connections:write")),
) -> ConnectionTestResponse:
    """Run a connector-specific, allowlisted, non-mutating verification."""

    record = connection_store.get(connection_id, owner_id=principal.owner_id)
    if record is None:
        raise HTTPException(status_code=404, detail="Connection not found.")

    checked_at = datetime.now(timezone.utc)
    outcome = await verify_connection_record(record)
    connection_store.mark_tested(
        connection_id,
        status=outcome.status,
        error=outcome.error,
        owner_id=principal.owner_id,
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
)
async def delete_connection(
    connection_id: UUID,
    principal: AuthPrincipal = Depends(require_scope("connections:write")),
) -> Response:
    if not connection_store.delete(connection_id, owner_id=principal.owner_id):
        raise HTTPException(status_code=404, detail="Connection not found.")
    return Response(status_code=status.HTTP_204_NO_CONTENT)
