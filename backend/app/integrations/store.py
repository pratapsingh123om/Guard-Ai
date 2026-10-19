"""Thread-safe, bounded in-memory connection storage.

The interface deliberately separates secret-bearing records from API response
models so credentials cannot be serialized accidentally. Production deployments
should replace this implementation with an encrypted secret-manager adapter.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

from backend.app.integrations.models import (
    ConnectionCreate,
    ConnectionResponse,
    ConnectionStatus,
)


@dataclass
class ConnectionRecord:
    id: UUID
    name: str
    category: Any
    connector: str
    endpoint: str
    settings: dict[str, Any]
    credentials: dict[str, str]
    status: ConnectionStatus
    created_at: datetime
    updated_at: datetime
    last_tested_at: datetime | None = None
    last_error: str | None = None

    def to_response(self) -> ConnectionResponse:
        return ConnectionResponse(
            id=self.id,
            name=self.name,
            category=self.category,
            connector=self.connector,
            endpoint=self.endpoint,
            settings=dict(self.settings),
            credential_fields=sorted(self.credentials),
            status=self.status,
            created_at=self.created_at,
            updated_at=self.updated_at,
            last_tested_at=self.last_tested_at,
            last_error=self.last_error,
        )


class ConnectionStore:
    def __init__(self, *, max_connections: int = 200) -> None:
        self.max_connections = max_connections
        self._records: dict[UUID, ConnectionRecord] = {}
        self._lock = threading.RLock()

    def create(self, value: ConnectionCreate) -> ConnectionResponse:
        now = datetime.now(timezone.utc)
        with self._lock:
            if len(self._records) >= self.max_connections:
                raise OverflowError("connection registry capacity reached")
            if any(record.name.casefold() == value.name.casefold() for record in self._records.values()):
                raise ValueError("a connection with this name already exists")
            record = ConnectionRecord(
                id=uuid4(),
                name=value.name,
                category=value.category,
                connector=value.connector,
                endpoint=value.endpoint or "",
                settings=dict(value.settings),
                credentials={
                    key: secret.get_secret_value() for key, secret in value.credentials.items()
                },
                status=ConnectionStatus.CONFIGURED,
                created_at=now,
                updated_at=now,
            )
            self._records[record.id] = record
            return record.to_response()

    def list(self) -> list[ConnectionResponse]:
        with self._lock:
            records = sorted(self._records.values(), key=lambda item: item.created_at)
            return [record.to_response() for record in records]

    def get(self, connection_id: UUID) -> ConnectionRecord | None:
        with self._lock:
            return self._records.get(connection_id)

    def get_response(self, connection_id: UUID) -> ConnectionResponse | None:
        with self._lock:
            record = self._records.get(connection_id)
            return record.to_response() if record else None

    def get_response_by_name(self, name: str) -> ConnectionResponse | None:
        with self._lock:
            for record in self._records.values():
                if record.name.casefold() == name.casefold():
                    return record.to_response()
        return None

    def mark_tested(
        self,
        connection_id: UUID,
        *,
        status: ConnectionStatus,
        error: str | None = None,
    ) -> ConnectionResponse | None:
        now = datetime.now(timezone.utc)
        with self._lock:
            record = self._records.get(connection_id)
            if record is None:
                return None
            record.status = status
            record.last_tested_at = now
            record.updated_at = now
            record.last_error = error
            return record.to_response()

    def delete(self, connection_id: UUID) -> bool:
        with self._lock:
            record = self._records.pop(connection_id, None)
            if record is not None:
                record.credentials.clear()
            return record is not None

    def clear(self) -> None:
        with self._lock:
            for record in self._records.values():
                record.credentials.clear()
            self._records.clear()


connection_store = ConnectionStore()
