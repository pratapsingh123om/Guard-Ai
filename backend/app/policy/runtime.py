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
        self._states: dict[str, RuntimePolicySnapshot] = {}
        self._lock = threading.RLock()

    def snapshot(self, owner_id: str = "legacy-admin") -> RuntimePolicySnapshot:
        with self._lock:
            state = self._states.get(owner_id)
            if state is None:
                state = RuntimePolicySnapshot(
                    revision=1,
                    updated_at=datetime.now(timezone.utc),
                    policy=RuntimePolicy(),
                )
                self._states[owner_id] = state
            return state.model_copy(deep=True)

    def update(
        self,
        update: RuntimePolicyUpdate,
        owner_id: str = "legacy-admin",
    ) -> RuntimePolicySnapshot:
        values = update.model_dump(exclude_none=True)
        with self._lock:
            state = self.snapshot(owner_id)
            if values:
                state = RuntimePolicySnapshot(
                    revision=state.revision + 1,
                    updated_at=datetime.now(timezone.utc),
                    policy=state.policy.model_copy(update=values),
                )
                self._states[owner_id] = state
            return state.model_copy(deep=True)

    def reset(self) -> None:
        with self._lock:
            self._states.clear()


runtime_policy_store = RuntimePolicyStore()
