"""Runtime policy settings exposed to the operator dashboard."""

from __future__ import annotations

import threading
from datetime import datetime, timezone

from pydantic import BaseModel, ConfigDict


class RuntimePolicy(BaseModel):
    model_config = ConfigDict(extra="forbid")

    block_prompt_injection: bool = True
    sanitize_retrieved_content: bool = True
    redact_sensitive_output: bool = True
    require_approval_for_risky_actions: bool = True


class RuntimePolicyUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    block_prompt_injection: bool | None = None
    sanitize_retrieved_content: bool | None = None
    redact_sensitive_output: bool | None = None
    require_approval_for_risky_actions: bool | None = None


class RuntimePolicySnapshot(BaseModel):
    revision: int
    updated_at: datetime
    policy: RuntimePolicy


class RuntimePolicyStore:
    def __init__(self) -> None:
        self._policy = RuntimePolicy()
        self._revision = 1
        self._updated_at = datetime.now(timezone.utc)
        self._lock = threading.RLock()

    def snapshot(self) -> RuntimePolicySnapshot:
        with self._lock:
            return RuntimePolicySnapshot(
                revision=self._revision,
                updated_at=self._updated_at,
                policy=self._policy.model_copy(deep=True),
            )

    def update(self, update: RuntimePolicyUpdate) -> RuntimePolicySnapshot:
        values = update.model_dump(exclude_none=True)
        with self._lock:
            if values:
                self._policy = self._policy.model_copy(update=values)
                self._revision += 1
                self._updated_at = datetime.now(timezone.utc)
            return self.snapshot()

    def reset(self) -> None:
        with self._lock:
            self._policy = RuntimePolicy()
            self._revision = 1
            self._updated_at = datetime.now(timezone.utc)


runtime_policy_store = RuntimePolicyStore()
