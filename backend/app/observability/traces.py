"""Secret-safe, bounded in-memory security traces."""

from __future__ import annotations

import threading
from collections import deque
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class TraceEvent(BaseModel):
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    stage: str
    guardrail: str
    status: str
    severity: str
    detail: str
    matched_rules: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class TraceRecord(BaseModel):
    trace_id: UUID
    started_at: datetime
    completed_at: datetime
    status: str
    ai_connection_id: UUID | None = None
    data_connection_ids: list[UUID] = Field(default_factory=list)
    events: list[TraceEvent]


class TraceStore:
    def __init__(self, *, capacity: int = 500) -> None:
        self._records: deque[TraceRecord] = deque(maxlen=capacity)
        self._lock = threading.RLock()

    def add(self, record: TraceRecord) -> None:
        with self._lock:
            self._records.append(record.model_copy(deep=True))

    def list(self, *, limit: int, status: str | None = None) -> list[TraceRecord]:
        with self._lock:
            records = list(reversed(self._records))
        if status is not None:
            records = [record for record in records if record.status == status]
        return [record.model_copy(deep=True) for record in records[:limit]]

    def get(self, trace_id: UUID) -> TraceRecord | None:
        with self._lock:
            for record in self._records:
                if record.trace_id == trace_id:
                    return record.model_copy(deep=True)
        return None

    def clear(self) -> None:
        with self._lock:
            self._records.clear()


trace_store = TraceStore()
