"""Operator endpoints for recent Guard-AI security traces."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query

from backend.app.api.dependencies import require_scope
from backend.app.observability.traces import TraceRecord, trace_store
from backend.app.security.auth import AuthPrincipal


router = APIRouter(prefix="/traces", tags=["traces"])


@router.get("", response_model=list[TraceRecord])
async def list_traces(
    limit: int = Query(default=50, ge=1, le=200),
    status: str | None = Query(default=None, max_length=40),
    principal: AuthPrincipal = Depends(require_scope("traces:read")),
) -> list[TraceRecord]:
    return trace_store.list(
        limit=limit,
        status=status,
        owner_id=principal.owner_id,
    )


@router.get(
    "/{trace_id}",
    response_model=TraceRecord,
)
async def get_trace(
    trace_id: UUID,
    principal: AuthPrincipal = Depends(require_scope("traces:read")),
) -> TraceRecord:
    result = trace_store.get(trace_id, owner_id=principal.owner_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Trace not found.")
    return result
