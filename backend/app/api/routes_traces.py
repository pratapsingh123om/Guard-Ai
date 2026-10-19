"""Operator endpoints for recent Guard-AI security traces."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Security
from fastapi.security import HTTPAuthorizationCredentials

from backend.app.api.dependencies import admin_bearer, require_admin
from backend.app.observability.traces import TraceRecord, trace_store


router = APIRouter(prefix="/traces", tags=["traces"])


async def _authorize(
    credentials: HTTPAuthorizationCredentials | None = Security(admin_bearer()),
) -> None:
    await require_admin(credentials)


@router.get("", response_model=list[TraceRecord], dependencies=[Depends(_authorize)])
async def list_traces(
    limit: int = Query(default=50, ge=1, le=200),
    status: str | None = Query(default=None, max_length=40),
) -> list[TraceRecord]:
    return trace_store.list(limit=limit, status=status)


@router.get(
    "/{trace_id}",
    response_model=TraceRecord,
    dependencies=[Depends(_authorize)],
)
async def get_trace(trace_id: UUID) -> TraceRecord:
    result = trace_store.get(trace_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Trace not found.")
    return result
