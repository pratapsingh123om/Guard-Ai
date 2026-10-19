"""Short-lived replay protection for security-sensitive MCP tool calls."""

from __future__ import annotations

import threading
from datetime import datetime, timedelta, timezone


class ReplayRejected(ValueError):
    pass


class ReplayCache:
    def __init__(self, *, max_lifetime_seconds: int, clock_skew_seconds: int, ttl_seconds: int) -> None:
        self.max_lifetime = timedelta(seconds=max_lifetime_seconds)
        self.clock_skew = timedelta(seconds=clock_skew_seconds)
        self.ttl = timedelta(seconds=ttl_seconds)
        self._entries: dict[tuple[str, str], datetime] = {}
        self._lock = threading.Lock()

    def consume(
        self,
        *,
        agent_id: str,
        request_id: str,
        issued_at: datetime,
        expires_at: datetime,
        now: datetime | None = None,
    ) -> None:
        now = now or datetime.now(timezone.utc)
        if issued_at.tzinfo is None or expires_at.tzinfo is None:
            raise ReplayRejected("request timestamps must include a timezone")
        issued_at = issued_at.astimezone(timezone.utc)
        expires_at = expires_at.astimezone(timezone.utc)
        if expires_at <= issued_at:
            raise ReplayRejected("request expiry must be after issue time")
        if expires_at - issued_at > self.max_lifetime:
            raise ReplayRejected("request lifetime exceeds the configured maximum")
        if issued_at > now + self.clock_skew:
            raise ReplayRejected("request issue time is too far in the future")
        if expires_at < now - self.clock_skew:
            raise ReplayRejected("request has expired")

        key = (agent_id, request_id)
        with self._lock:
            cutoff = now - self.ttl
            self._entries = {entry: seen for entry, seen in self._entries.items() if seen >= cutoff}
            if key in self._entries:
                raise ReplayRejected("duplicate request ID")
            self._entries[key] = now
