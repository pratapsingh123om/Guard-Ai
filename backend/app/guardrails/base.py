"""Shared types for runtime guardrails and the adversarial eval harness."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any


class GuardrailAction(str, Enum):
    ALLOW = "allow"
    FLAG = "flag"
    BLOCK = "block"
    SANITIZE = "sanitize"
    REDACT = "redact"
    REQUIRE_APPROVAL = "require_approval"


class Severity(str, Enum):
    INFO = "info"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass(frozen=True)
class GuardrailResult:
    """The stable result contract returned by every guardrail.

    ``passed`` means no policy violation was detected. A guardrail may still
    transform otherwise-safe content (for example, wrapping retrieved text in
    an untrusted-data boundary).
    """

    guardrail: str
    category: str
    passed: bool
    action: GuardrailAction
    reason: str
    severity: Severity = Severity.INFO
    score: float = 0.0
    matched_rules: tuple[str, ...] = ()
    transformed_content: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["action"] = self.action.value
        payload["severity"] = self.severity.value
        payload["matched_rules"] = list(self.matched_rules)
        return payload


class Guardrail(ABC):
    """A provider-agnostic guardrail interface."""

    name: str
    category: str

    @abstractmethod
    def check(self, context: Any) -> GuardrailResult:
        """Inspect context and return a deterministic policy decision."""
