"""Public, read-only demo service backed by deterministic synthetic SQLite data."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query

from backend.app.demo.database import (
    ensure_demo_database,
    read_demo_customers,
    read_demo_orders,
    read_demo_summary,
)


router = APIRouter(prefix="/demo", tags=["demo service"])


def _database_or_503() -> None:
    try:
        path = ensure_demo_database()
    except (OSError, RuntimeError):
        path = None
    if path is None:
        raise HTTPException(status_code=503, detail="Demo database is unavailable.")


@router.get("")
async def describe_demo_service() -> dict[str, Any]:
    return {
        "service": "guard-ai-demo",
        "description": "Synthetic read-only customer and order service for Guard-AI testing.",
        "database": "SQLite",
        "endpoints": ["/health", "/summary", "/customers", "/orders"],
    }


@router.get("/health")
async def demo_health() -> dict[str, Any]:
    _database_or_503()
    summary = read_demo_summary()
    return {
        "service": "guard-ai-demo",
        "status": "healthy",
        "database": "ready",
        "records": summary["customer_count"] + summary["order_count"],
    }


@router.get("/summary")
async def demo_summary() -> dict[str, Any]:
    _database_or_503()
    return {"service": "guard-ai-demo", "data": read_demo_summary()}


@router.get("/customers")
async def demo_customers(
    limit: int = Query(default=20, ge=1, le=100),
) -> dict[str, Any]:
    _database_or_503()
    items = read_demo_customers(limit=limit)
    return {"service": "guard-ai-demo", "count": len(items), "items": items}


@router.get("/orders")
async def demo_orders(
    limit: int = Query(default=20, ge=1, le=100),
) -> dict[str, Any]:
    _database_or_503()
    items = read_demo_orders(limit=limit)
    return {"service": "guard-ai-demo", "count": len(items), "items": items}
