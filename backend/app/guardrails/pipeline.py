"""Runtime coordinator that enforces guardrails in side-effect-safe order."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Mapping, Sequence

from backend.app.guardrails.action import ActionRiskGuardrail
from backend.app.guardrails.base import GuardrailAction, GuardrailResult
from backend.app.guardrails.input import PromptInjectionGuardrail
from backend.app.guardrails.output import SensitiveDataGuardrail
from backend.app.guardrails.retrieval import DocumentSanitizer


class PipelineStatus(str, Enum):
    ALLOWED = "allowed"
    BLOCKED = "blocked"
    NEEDS_APPROVAL = "needs_approval"


@dataclass(frozen=True)
class PipelineDecision:
    status: PipelineStatus
    results: tuple[GuardrailResult, ...]
    sanitized_documents: tuple[str, ...]


class GuardrailPipeline:
    """A small provider-neutral pipeline that can wrap any agent runtime."""

    def __init__(
        self,
        input_guardrail: PromptInjectionGuardrail | None = None,
        document_guardrail: DocumentSanitizer | None = None,
        action_guardrail: ActionRiskGuardrail | None = None,
        output_guardrail: SensitiveDataGuardrail | None = None,
    ):
        self.input_guardrail = input_guardrail or PromptInjectionGuardrail()
        self.document_guardrail = document_guardrail or DocumentSanitizer(self.input_guardrail)
        self.action_guardrail = action_guardrail or ActionRiskGuardrail()
        self.output_guardrail = output_guardrail or SensitiveDataGuardrail()

    def inspect_before_agent(
        self,
        message: str,
        documents: Sequence[str] = (),
        proposed_actions: Sequence[Mapping[str, Any]] = (),
    ) -> PipelineDecision:
        """Run all checks that must finish before an agent can cause effects."""

        results: list[GuardrailResult] = []
        input_result = self.input_guardrail.check(message)
        results.append(input_result)
        if input_result.action is GuardrailAction.BLOCK:
            return PipelineDecision(PipelineStatus.BLOCKED, tuple(results), ())

        sanitized_documents: list[str] = []
        for document in documents:
            result = self.document_guardrail.check(document)
            results.append(result)
            sanitized_documents.append(result.transformed_content or "")

        status = PipelineStatus.ALLOWED
        for action in proposed_actions:
            result = self.action_guardrail.check(action)
            results.append(result)
            if result.action is GuardrailAction.BLOCK:
                status = PipelineStatus.BLOCKED
            elif result.action is GuardrailAction.REQUIRE_APPROVAL and status is not PipelineStatus.BLOCKED:
                status = PipelineStatus.NEEDS_APPROVAL

        return PipelineDecision(status, tuple(results), tuple(sanitized_documents))

    def inspect_output(self, response: str) -> GuardrailResult:
        return self.output_guardrail.check(response)
